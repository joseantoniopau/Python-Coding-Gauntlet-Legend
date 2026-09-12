/* The seam between the Python bestiary and web/js/monsterart.js, measured.
 *
 * Same idea as petroster.mjs and the same instrument: installRaster() gives a
 * canvas that really rasterises, so every number below is counted off pixels
 * rather than off the module's own opinion of itself.
 *
 * What it puts a number on:
 *
 *   MIRROR      monsterart.js carries a copy of world.py REGIONS and
 *               elements.py BIOME_AFFINITY, because a browser module cannot
 *               import Python. A copy nobody checks is a bug with a delay on
 *               it, so both tables are read out of Python and diffed.
 *   SPRITE      every `sprite` string bestiary.py ships resolves through the
 *               table rather than falling off the end of it
 *   COLOUR      fifteen, counted off the raster, for every creature x every
 *               frame x every pose x every region palette
 *   SILHOUETTE  no two creatures a player can see side by side have the same
 *               16px outline, and the apex is bigger than every mob it hunts
 *               beside
 *   MOTION      every frame of every walk differs from the next in OUTLINE, not
 *               in brightness; every legless creature is off the floor in every
 *               frame of both poses
 *   DETERMINISM the same frame hashes the same warm, cold and rebuilt
 *   CACHE       a settled creature redrawn 240 times allocates no canvases
 */
import { installRaster, RASTER, frameHash, colourCount, silhouetteDiff } from './raster.mjs';
installRaster();
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const MA = await import('../../web/js/monsterart.js');

const fail = [];
const note = (m) => fail.push(m);
const out = {};

/* ---------------- the source of truth, from Python ---------------- */
let py = null;
const PROBE = [
  'import json,sys',
  'sys.path.insert(0,".")',
  'from gauntlet import world, elements, bestiary',
  'try:',
  '    from gauntlet import hunters',
  'except Exception:',
  '    hunters = None',
  'print(json.dumps({',
  '  "regions":[{"id":r["id"],"biome":r["biome"]} for r in world.REGIONS],',
  '  "biomeElement":dict(elements.BIOME_AFFINITY),',
  '  "sprites":sorted({e.sprite for e in bestiary.ENEMIES}),',
  '  "enemies":[{"id":e.id,"sprite":e.sprite,"colour":e.colour} for e in bestiary.ENEMIES],',
  '  "hunters":([{"id":a.id,"name":a.name,"region":a.region,"sprite":a.sprite,',
  '               "fallback":a.sprite_fallback} for a in hunters.APEXES] if hunters else []),',
  '}))',
].join('\n');
try {
  py = JSON.parse(execFileSync('python3', ['-c', PROBE], { cwd: ROOT, encoding: 'utf8' }));
} catch (e) { out.pythonError = String(e.message).split('\n')[0]; }

if (!py) {
  note('could not read gauntlet/ — the contract is unverifiable, not passing');
  console.log(JSON.stringify(out, null, 1));
  process.exit(1);
}

/* ---------------- MIRROR ---------------- */
{
  const drift = [];
  for (const r of py.regions) {
    if (MA.REGION_BIOME[r.id] !== r.biome) {
      drift.push(`region ${r.id}: python says biome ${r.biome}, monsterart says ${MA.REGION_BIOME[r.id]}`);
    }
  }
  for (const id of Object.keys(MA.REGION_BIOME)) {
    if (!py.regions.some(r => r.id === id)) drift.push(`monsterart has region ${id}, world.py does not`);
  }
  for (const [biome, el] of Object.entries(py.biomeElement)) {
    if (MA.BIOME_ELEMENT[biome] !== el) {
      drift.push(`biome ${biome}: python says ${el}, monsterart says ${MA.BIOME_ELEMENT[biome]}`);
    }
  }
  out.mirror = { regionsInPython: py.regions.length,
                 regionsInArt: Object.keys(MA.REGION_BIOME).length,
                 biomesInPython: Object.keys(py.biomeElement).length,
                 drift };
  if (drift.length) note(`the region/element mirror has drifted: ${drift.join('; ')}`);
}

/* ---------------- every region has a roster and an apex ---------------- */
{
  const missing = [];
  for (const r of py.regions) {
    const roster = MA.rosterFor(r.id);
    if (!roster || roster.length < 2) missing.push(`${r.id} has no roster`);
    for (const k of roster) if (!MA.MONSTERS[k]) missing.push(`${r.id} roster names ${k}, which is not drawn`);
    const apex = MA.apexKeyFor(r.id);
    if (!MA.MONSTERS[apex] || !MA.MONSTERS[apex].apex) missing.push(`${r.id} has no apex (got ${apex})`);
  }
  out.regions = { count: py.regions.length, apexes: MA.APEX_KEYS.length, missing };
  if (missing.length) note(`regions with nothing to fight: ${missing.join('; ')}`);
  if (MA.APEX_KEYS.length !== py.regions.length) {
    note(`${MA.APEX_KEYS.length} apexes for ${py.regions.length} regions`);
  }
}

/* ---------------- HUNTERS: seventeen names, seventeen bodies ---------------- */
{
  const rows = [], wrongRegion = [], notDistinct = [], unnamed = [];
  const seen = new Map();
  for (const h of (py.hunters || [])) {
    // the three spellings a caller might have: the sprite key, the id, the name
    const bySprite = MA.apexKeyFor({ region: h.region, sprite: h.sprite });
    const byIdAlone = MA.monsterKeyFor(h.id, { apex: true });
    const byNameAlone = MA.monsterKeyFor(h.name, { apex: true });
    const expected = MA.REGION_APEX[h.region];
    if (!expected) wrongRegion.push(`${h.id}: monsterart has no apex for region ${h.region}`);
    if (bySprite !== expected) wrongRegion.push(`${h.id}: region gives ${bySprite}, table says ${expected}`);
    if (byIdAlone !== expected) unnamed.push(`${h.id} alone -> ${byIdAlone}`);
    if (byNameAlone !== expected) unnamed.push(`"${h.name}" alone -> ${byNameAlone}`);
    if (seen.has(bySprite)) notDistinct.push(`${h.id} and ${seen.get(bySprite)} both draw ${bySprite}`);
    seen.set(bySprite, h.id);
    const img = MA.monsterFrame(h.sprite, 0, { region: h.region, apex: true });
    rows.push({ id: h.id, name: h.name, region: h.region, drawnAs: bySprite,
                box: `${img.width}x${img.height}`, colours: colourCount(img),
                artName: MA.APEX_NAMES[bySprite] });
  }
  out.hunters = { count: (py.hunters || []).length, rows, wrongRegion, notDistinct,
                  resolvedByNameAlone: unnamed,
                  namesDisagree: rows.filter(r => r.artName !== r.name)
                                     .map(r => `${r.id}: hunters.py "${r.name}", art "${r.artName}"`) };
  if (!py.hunters || !py.hunters.length) {
    out.hunters.note = 'gauntlet/hunters.py not importable — apexes checked by region only';
  }
  if (wrongRegion.length) note(`hunters that do not land on their own region's apex: ${wrongRegion.join('; ')}`);
  if (notDistinct.length) note(`two hunters drawing one body: ${notDistinct.join('; ')}`);
  if (unnamed.length) note(`hunter ids or names that do not resolve without a region: ${unnamed.join('; ')}`);
  if (out.hunters.namesDisagree.length) {
    note(`display names out of step with hunters.py: ${out.hunters.namesDisagree.join('; ')}`);
  }
}

/* ---------------- SPRITE: every key bestiary.py ships ---------------- */
{
  const fellThrough = [];
  const perRegionSample = {};
  for (const key of py.sprites) {
    if (!MA.monsterIsAuthored(key)) fellThrough.push(key);
  }
  // and the thing the whole file is for: the same bestiary key must NOT draw the
  // same creature in every region.
  const sameEverywhere = [];
  for (const key of py.sprites) {
    const drawn = new Set(py.regions.map(r => MA.monsterKeyFor(key, { region: r.id })));
    perRegionSample[key] = [...drawn];
    if (drawn.size === 1) sameEverywhere.push(`${key} -> ${[...drawn][0]} in all 17 regions`);
  }
  out.sprites = { bestiaryKeys: py.sprites.length, fellThrough,
                  distinctCreaturesPerKey: perRegionSample, sameEverywhere };
  if (fellThrough.length) {
    note(`bestiary.py ships ${fellThrough.length} sprite key(s) with no entry in `
       + `MONSTER_ALIAS, so they render as an unmarked body: ${fellThrough.join(', ')}`);
  }
  if (sameEverywhere.length) {
    note(`keys that draw the same creature in every region, which is the bug this `
       + `file exists to fix: ${sameEverywhere.join('; ')}`);
  }
}

/* ---------------- COLOUR: fifteen, off the raster ---------------- */
{
  const over = [];
  let worst = 0, worstAt = null, sweep = 0;
  const colours = ['', '#c43f4f', '#5fbf8f', '#e8a33d', '#8f6ad6'];
  for (const key of MA.MONSTER_KEYS) {
    const m = MA.MONSTERS[key];
    for (const pose of ['walk', 'idle']) {
      for (let f = 0; f < 4; f++) {
        for (const colour of colours) {
          const img = MA.monsterFrame(key, f, { colour, pose });
          const n = colourCount(img);
          sweep++;
          if (n > worst) { worst = n; worstAt = `${key}/${pose}/${f}/${colour || 'own'}`; }
          if (n > 15) over.push({ key, pose, f, colour, colours: n });
        }
      }
    }
  }
  out.colour = { framesSwept: sweep, worst, worstAt, over: over.slice(0, 12),
                 overCount: over.length };
  if (over.length) note(`${over.length} frame(s) over the fifteen-colour budget, worst ${worst} at ${worstAt}`);
}

/* ---------------- SILHOUETTE and MOTION, from the module's own stats ------- */
{
  const stats = MA.monsterArtStats();
  out.stats = {
    creatures: stats.creatures, mobs: stats.mobs, apexes: stats.apexes,
    gaits: stats.gaits, closestPairAnywhere: stats.closestPairAnywhere,
  };

  const identical = stats.perRegion.filter(r => r.pixelsOfOutlineThatDiffer === 0);
  const apexNotLarger = stats.perRegion.filter(r => !r.apexIsLarger);
  out.perRegion = stats.perRegion.map(r => ({
    region: r.region, element: r.element, cast: r.cast,
    closestPair: r.closestPair, outlinePixelsApart: r.pixelsOfOutlineThatDiffer,
    apex: r.apex, apexDrawn: `${r.apexDrawnPixels}px ${r.apexDrawnBox}`,
    largestMob: `${r.largestMob} ${r.largestMobDrawnPixels}px ${r.largestMobDrawnBox}`,
    apexTimesLarger: r.apexTimesLargerThanAnyMob,
  }));
  out.apexScale = {
    smallestMargin: Math.min(...stats.perRegion.map(r => r.apexTimesLargerThanAnyMob)),
    largestMargin: Math.max(...stats.perRegion.map(r => r.apexTimesLargerThanAnyMob)),
  };
  if (identical.length) {
    note(`regions where two creatures share one 16px outline: `
       + identical.map(r => `${r.region} ${r.closestPair.join('/')}`).join(', '));
  }
  if (apexNotLarger.length) {
    note(`apexes that do not out-read the biggest mob in their own region: `
       + apexNotLarger.map(r => `${r.region} ${r.apex} ${r.apexDrawnPixels}px vs `
                               + `${r.largestMob} ${r.largestMobDrawnPixels}px`).join(', '));
  }
  // "bigger" has to mean something. A third again is the floor: below that the
  // player is reading a health bar rather than a silhouette.
  const thin = stats.perRegion.filter(r => r.apexTimesLargerThanAnyMob < 1.25);
  if (thin.length) {
    note(`apexes less than a quarter again the size of their region's biggest mob: `
       + thin.map(r => `${r.region} ${r.apex} x${r.apexTimesLargerThanAnyMob}`).join(', '));
  }

  const dead = stats.rows.filter(r => r.outlineChangedPerWalkCycle === 0);
  const deadIdle = stats.rows.filter(r => r.cellsChangedPerIdleCycle === 0);
  const grounded = stats.rows.filter(r => r.legs === 0 && r.touchesFloor
                                          && r.role !== 'apex' && r.gait === 'hover');
  const groundedApex = stats.rows.filter(r => r.gait === 'hover' && r.touchesFloor);
  out.motion = {
    walkOutlineChange: {
      min: Math.min(...stats.rows.map(r => r.outlineChangedPerWalkCycle)),
      max: Math.max(...stats.rows.map(r => r.outlineChangedPerWalkCycle)),
    },
    idleCellChange: {
      min: Math.min(...stats.rows.map(r => r.cellsChangedPerIdleCycle)),
      max: Math.max(...stats.rows.map(r => r.cellsChangedPerIdleCycle)),
    },
    stillWalks: dead.map(r => r.monster),
    stillIdles: deadIdle.map(r => r.monster),
    hoverCreaturesTouchingTheFloor: groundedApex.map(r => r.monster),
  };
  if (dead.length) note(`creatures whose walk does not move the outline: ${dead.map(r => r.monster).join(', ')}`);
  if (deadIdle.length) note(`creatures whose idle does not move at all: ${deadIdle.map(r => r.monster).join(', ')}`);
  if (groundedApex.length) {
    note(`things with no legs that still touch the floor: ${groundedApex.map(r => r.monster).join(', ')}`);
  }
  out.rows = stats.rows;
}

/* ---------------- DETERMINISM ---------------- */
{
  const warm = [], cold = [];
  for (const key of MA.MONSTER_KEYS) {
    for (const pose of ['walk', 'idle']) {
      for (let f = 0; f < 4; f++) warm.push(frameHash(MA.monsterFrame(key, f, { pose })));
    }
  }
  MA.clearMonsterCache();
  for (const key of MA.MONSTER_KEYS) {
    for (const pose of ['walk', 'idle']) {
      for (let f = 0; f < 4; f++) cold.push(frameHash(MA.monsterFrame(key, f, { pose })));
    }
  }
  const diff = warm.filter((h, i) => h !== cold[i]).length;
  out.determinism = { framesHashed: warm.length, differingAfterRebuild: diff };
  if (diff) note(`${diff} frame(s) differ between a warm cache and a cold one`);
}

/* ---------------- CACHE ---------------- */
{
  MA.clearMonsterCache();
  MA.monsterFrame('bonepike', 0, {});     // settle
  RASTER.counting = true; RASTER.canvases = 0;
  for (let i = 0; i < 240; i++) MA.monsterFrame('bonepike', 0, {});
  const steady = RASTER.canvases;
  RASTER.canvases = 0;
  // the worst real load: one region's whole cast, four frames, two poses, twice
  for (let pass = 0; pass < 2; pass++) {
    for (const region of Object.keys(MA.REGION_BIOME)) {
      for (const k of MA.rosterFor(region).concat([MA.apexKeyFor(region)])) {
        for (const pose of ['walk', 'idle']) for (let f = 0; f < 4; f++) MA.monsterFrame(k, f, { pose });
      }
    }
  }
  const whole = RASTER.canvases;
  RASTER.counting = false;
  out.cache = { redrawsOfOneSettledFrame: 240, canvasesAllocated: steady,
                wholeWorldTwice: whole, stats: MA.monsterCacheStats() };
  if (steady) note(`a settled frame redrawn 240 times allocated ${steady} canvases`);
}

/* ---------------- FALL BACK, NEVER THROW ---------------- */
{
  const junk = ['', null, undefined, 0, '__no_such_monster__', 'Slime ',
                { sprite: 'nonsense' }, 'wisp', 'vault', 'PHOENIX'];
  const thrown = [];
  for (const j of junk) {
    for (const region of ['null_kings_castle', 'fields_of_syntax', '__nowhere__', undefined]) {
      try {
        const img = MA.monsterFrame(j, 3, { region, pose: 'idle' });
        if (!img || !img.width) thrown.push(`${JSON.stringify(j)}@${region} -> no image`);
        MA.monsterSilhouette(j, 1, { region });
        MA.monsterShadow(j, { region });
        MA.monsterMotion(j, { region });
        MA.apexKeyFor(region);
      } catch (e) { thrown.push(`${JSON.stringify(j)}@${region}: ${e.constructor.name}: ${e.message}`); }
    }
  }
  // and the fallback must not claim to be somebody
  const strayKey = MA.monsterKeyFor('__no_such_monster__', { region: 'fields_of_syntax' });
  out.fallback = {
    threw: thrown,
    unknownResolvesTo: strayKey,
    isReportedAsUnauthored: !MA.monsterIsAuthored('__no_such_monster__', { region: 'fields_of_syntax' }),
    unknownInTheCastle: MA.monsterKeyFor('__nope__', { region: 'null_kings_castle' }),
  };
  if (thrown.length) note(`threw on junk input: ${thrown.join('; ')}`);
  if (MA.MOB_KEYS.includes(strayKey)) {
    note(`an unknown key renders as ${strayKey}, which is a real creature — it must not`);
  }
}

/* ---------------- every real enemy row draws ---------------- */
{
  const broken = [];
  for (const e of py.enemies) {
    for (const r of py.regions) {
      const img = MA.monsterFrame(e.sprite, 0, { region: r.id, colour: e.colour });
      if (!img || !img.width) { broken.push(`${e.id}@${r.id}`); break; }
      if (colourCount(img) > 15) { broken.push(`${e.id}@${r.id} over budget`); break; }
    }
  }
  out.bestiary = { enemies: py.enemies.length, regions: py.regions.length,
                   combinationsDrawn: py.enemies.length * py.regions.length, broken };
  if (broken.length) note(`enemy rows that do not draw: ${broken.join(', ')}`);
}

out.failures = fail.length;
out.detail = fail;
console.log(JSON.stringify(out, null, 1));
process.exit(fail.length ? 1 : 0);
