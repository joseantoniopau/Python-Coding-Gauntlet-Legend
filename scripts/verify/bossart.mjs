/* bossart.js, measured off the raster.
 *
 * stub.mjs answers "did it throw"; this uses raster.mjs, which composites into
 * a real RGBA buffer, so every number below is counted off pixels rather than
 * off the file's intentions.
 */
import { installRaster, colourCount, frameHash, pixelDiff, silhouetteDiff } from './raster.mjs';
installRaster();

const BA = await import('../../web/js/bossart.js');
const B = await import('../../web/js/bosses.js');

const W = (lk) => (lk.wide ? BA.ART_WIDE_W : BA.ART_W);
const shot = (cv) => cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);

const fail = [];
const note = (m) => fail.push(m);

/* ---------------- 1. self check, and glyph agreement with bosses.js -------- */
const self = BA.bossArtSelfCheck(B.BOSS_GLYPHS);
console.log('1. SELF CHECK');
console.log('   glyph table identical to bosses.BOSS_GLYPHS:', BA.ART_GLYPHS === B.BOSS_GLYPHS);
console.log('   ok:', self.ok, self.problems.length ? self.problems : '');
if (!self.ok) note('self check: ' + self.problems.join('; '));

/* ---------------- 2. the roster ------------------------------------------- */
const looks = BA.allLooks();
console.log('\n2. ROSTER');
console.log('   stats:', JSON.stringify(BA.bossArtStats()));
console.log('   looks:', looks.length, '=', BA.NAMED_IDS.length, 'named +',
  BA.APEX_IDS.length, 'apexes + 1 final');
const byElement = {};
for (const l of looks) byElement[l.element] = (byElement[l.element] || 0) + 1;
console.log('   by element:', JSON.stringify(byElement));

/* ---------------- 3. colour budget, counted off rendered pixels ----------- */
console.log('\n3. COLOUR BUDGET (counted off the raster, 15 + transparent)');
let worst = { n: 0, who: '' };
let frames = 0;
const perLook = [];
for (const lk of looks) {
  let hi = 0, lo = 99;
  for (let ph = 0; ph < 3; ph++) {
    for (let f = 0; f < 5; f++) {
      for (let b = 0; b < (f <= 1 ? 6 : 1); b++) {
        const cv = BA.lookSprite(lk, { frame: f, beat: b, phase: ph });
        const n = colourCount(cv);
        frames++;
        if (n > hi) hi = n;
        if (n < lo) lo = n;
        if (n > worst.n) worst = { n, who: `${lk.id} f${f} b${b} p${ph}` };
        if (n > 15) note(`OVER BUDGET ${lk.id} f${f} b${b} p${ph}: ${n} colours`);
      }
    }
  }
  perLook.push([lk.id, lo, hi]);
}
console.log('   frames swept:', frames);
console.log('   worst frame:', worst.n, 'colours  (' + worst.who + ')');
console.log('   min/max per look:');
for (const [id, lo, hi] of perLook) console.log('    ', id.padEnd(26), lo + '-' + hi);

/* ---------------- 4. the element verbs actually move pixels --------------- */
console.log('\n4. THE SIX VERBS (pixels the element pass touched, on one body)');
const plain = ['.'.repeat(40)].concat(
  Array.from({ length: 40 }, (_, y) => {
    const hw = 12 - Math.abs(y - 20) * 0.2 | 0;
    const row = new Array(40).fill('.');
    for (let x = 20 - hw; x <= 20 + hw; x++) row[x] = 'B';
    return row.join('');
  }));
for (const el of ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID', 'NEUTRAL']) {
  const fake = { id: 'probe_' + el, element: el, core: [20, 20] };
  const out = BA.dressGrid(plain, fake, { frame: 0, beat: 0, phase: 0 });
  const before = plain.join('').split('').filter(c => c !== '.').length;
  const after = out.join('').split('').filter(c => c !== '.').length;
  console.log('   ', el.padEnd(10), BA.LAST_DRESS.verb.padEnd(7),
    'touched', String(BA.LAST_DRESS.touched).padStart(4),
    ' body px', before, '->', after,
    ' delta', (after - before >= 0 ? '+' : '') + (after - before));
  if (el !== 'NEUTRAL' && BA.LAST_DRESS.touched === 0) note(`verb for ${el} did nothing`);
  if (el === 'NEUTRAL' && after !== before) note('NEUTRAL is not the control group');
  const stray = BA.strayGlyphs(out);
  if (stray.length) note(`${el} emitted glyphs outside the table: ${stray}`);
}

/* ---------------- 5. silhouettes are different ---------------------------- */
console.log('\n5. SILHOUETTE DISTINCTNESS');
function litArea(cv) {
  const d = shot(cv).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i]) n++;
  return n;
}
// The seventeen apexes, pairwise, colour discarded.
const apex = BA.APEX_IDS.map(id => BA.bossLook(id));
const bufs = apex.map(lk => shot(BA.lookSprite(lk, { frame: 0, beat: 0, phase: 0 })));
let minPair = { n: 1e9, a: '', b: '' };
let identical = 0;
for (let i = 0; i < apex.length; i++) {
  for (let j = i + 1; j < apex.length; j++) {
    const n = silhouetteDiff(bufs[i], bufs[j]);
    if (n === 0) { identical++; note(`apexes ${apex[i].id} and ${apex[j].id} are the same shape`); }
    if (n < minPair.n) minPair = { n, a: apex[i].id, b: apex[j].id };
  }
}
console.log('   apex pairs compared:', (apex.length * (apex.length - 1)) / 2);
console.log('   identical pairs:', identical);
console.log('   closest pair:', minPair.n, 'px differ  (' + minPair.a + ' vs ' + minPair.b + ')');
console.log('   lit area per apex:');
for (const lk of apex) {
  console.log('    ', lk.id.padEnd(26), lk.element.padEnd(10),
    String(litArea(BA.lookSprite(lk, { frame: 0, beat: 0, phase: 0 }))).padStart(5), 'px');
}

/* ---------------- 5b. THE TWO SCALES ------------------------------------- */
/* The brief's first two claims are about two different sizes: the boss standing
 * on the overworld at marker scale, and the same boss at battle scale. They are
 * the same grid here, so "the same creature" is true by construction; what has
 * to be MEASURED is whether the thing still reads at the small size, because a
 * silhouette that only separates at 64px is a silhouette that does not exist on
 * the map. Both numbers below are colour-discarded. */
console.log('\n5b. THE TWO SCALES (same grid, knocked down; colour discarded)');
const silBits = (lk, box) => BA.lookSilhouette(lk, { frame: 0, box }).join('');
const bitDiff = (a, b) => {
  let n = 0;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) n++;
  return n;
};
for (const [label, set] of [['the seventeen apexes', BA.APEX_IDS], ['the fourteen named', BA.NAMED_IDS]]) {
  const ls = set.map(id => BA.bossLook(id));
  for (const box of [16, 24, 48]) {
    const bits = ls.map(lk => silBits(lk, box));
    let same = 0, min = 1e9, pair = '';
    for (let i = 0; i < bits.length; i++) {
      for (let j = i + 1; j < bits.length; j++) {
        const d = bitDiff(bits[i], bits[j]);
        if (d === 0) same++;
        if (d < min) { min = d; pair = ls[i].id + ' vs ' + ls[j].id; }
      }
    }
    const area = bits.map(b => b.split('#').length - 1);
    console.log('   ', label.padEnd(22), String(box).padStart(2) + 'px box:',
      'identical pairs', same,
      ' closest', String(min).padStart(3), 'of', box * box, 'cells (' + pair + ')',
      ' lit', Math.min(...area) + '-' + Math.max(...area));
    if (same) note(`${label} at ${box}px: ${same} identical pairs`);
    /* Ten of two hundred and fifty six. A marker on the overworld map is read at
     * a glance and at a distance, and two shapes four cells apart are one shape
     * with a rendering artefact. This gate found the Serialization Lich and the
     * Interviewer sharing a silhouette, which is exactly the defect the brief's
     * fourth, unstated claim is about. */
    if (box === 16 && min < 10) note(`${label} at 16px: closest pair differs by only ${min} cells`);
  }
}

/* ---------------- 6. motion is real, not a brightness wobble -------------- */
console.log('\n6. MOTION (pixels changing between consecutive frames)');
console.log('   look                        idle beats 0->1   idle->windup   windup->attack');
for (const lk of looks) {
  const g = (f, b, p = 0) => shot(BA.lookSprite(lk, { frame: f, beat: b, phase: p }));
  const b01 = pixelDiff(g(0, 0), g(0, 1));
  const iw = pixelDiff(g(0, 0), g(2, 0));
  const wa = pixelDiff(g(2, 0), g(3, 0));
  console.log('   ', lk.id.padEnd(26), String(b01).padStart(6), String(iw).padStart(14), String(wa).padStart(14));
  if (iw === 0) note(`${lk.id}: wind-up is identical to idle`);
  if (wa === 0) note(`${lk.id}: attack is identical to wind-up`);
}

/* ---------------- 7. phases change the creature --------------------------- */
console.log('\n7. PHASES (silhouette px changing between phases)');
for (const lk of looks) {
  const a = shot(BA.lookSprite(lk, { frame: 0, beat: 0, phase: 0 }));
  const b = shot(BA.lookSprite(lk, { frame: 0, beat: 0, phase: 1 }));
  const c = shot(BA.lookSprite(lk, { frame: 0, beat: 0, phase: 2 }));
  const wc = pixelDiff(a, b), cc = pixelDiff(b, c);
  console.log('   ', lk.id.padEnd(26), 'whole->cracked', String(wc).padStart(5),
    ' cracked->core', String(cc).padStart(5),
    ' silhouette 0->2', String(silhouetteDiff(a, c)).padStart(5));
  if (wc === 0) note(`${lk.id}: phase two is the same picture as phase one`);
  if (cc === 0) note(`${lk.id}: phase three is the same picture as phase two`);
}
console.log('   (silhouette 0->2 is 0 for the NEUTRAL looks on purpose: elements.py');
console.log('    makes five regions neutral as a control group, and the control group');
console.log('    does not get an element pass. Their phases change colour, not shape.)');

/* ---------------- 8. determinism ------------------------------------------ */
console.log('\n8. DETERMINISM (cold rebuild must hash identically)');
let hashes = 0, drift = 0;
for (const lk of looks) {
  for (let ph = 0; ph < 3; ph++) {
    for (let f = 0; f < 5; f++) {
      const h1 = frameHash(shot(BA.lookSprite(lk, { frame: f, beat: 0, phase: ph })));
      BA.clearBossArtCache();
      const h2 = frameHash(shot(BA.lookSprite(lk, { frame: f, beat: 0, phase: ph })));
      hashes++;
      if (h1 !== h2) { drift++; note(`${lk.id} f${f} p${ph} is not deterministic`); }
    }
  }
}
console.log('   frames hashed cold and warm:', hashes, ' mismatches:', drift);
console.log('   source scan for Math.random / Date.now / performance.now:');
{
  const fs = await import('fs');
  const raw = fs.readFileSync(new URL('../../web/js/bossart.js', import.meta.url), 'utf8');
  // Strip comments first. The file's own header says "no Math.random and no
  // Date.now", and a scan that counts that sentence is a scan that can only
  // ever fail.
  const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  for (const bad of ['Math.random', 'Date.now', 'performance.now']) {
    const n = src.split(bad).length - 1;
    console.log('    ', bad.padEnd(16), n, '(prose stripped; raw file mentions it',
      raw.split(bad).length - 1, 'times)');
    if (n) note(`${bad} is CALLED in bossart.js`);
  }
}

/* ---------------- 9. steady state and the cap ----------------------------- */
console.log('\n9. CACHE');
import('./raster.mjs').then(() => {});
const { RASTER } = await import('./raster.mjs');
function redraw(set, phase, passes) {
  for (let r = 0; r < passes; r++) {
    for (const lk of set) {
      for (let f = 0; f < 5; f++) for (let b = 0; b < (f <= 1 ? 6 : 1); b++) {
        BA.lookSprite(lk, { frame: f, beat: b, phase });
      }
    }
  }
}
// (a) what a FIGHT asks for: one creature, one phase, redrawn forever.
BA.clearBossArtCache();
RASTER.counting = true; RASTER.canvases = 0;
const one = [BA.bossLook('the_last_interpreter')];
const oneWarm = BA.warmLook(one[0], 0);
const oneCold = RASTER.canvases;
RASTER.canvases = 0;
redraw(one, 0, 240);
const oneSteady = RASTER.canvases;
console.log('   one boss, one phase: warmLook built', oneWarm, 'frames in', oneCold, 'canvases');
console.log('   240 redraws of it afterwards:', oneSteady, 'canvases');
if (oneSteady !== 0) note(`a settled fight is still allocating: ${oneSteady}`);

// (b) the widest legitimate call: the whole roster at one phase, which is what
// a codex screen or this harness asks for. The cap is sized for exactly this.
BA.clearBossArtCache();
RASTER.canvases = 0;
let warmed = 0;
for (const lk of looks) warmed += BA.warmLook(lk, 0);
const cold = RASTER.canvases;
RASTER.canvases = 0;
redraw(looks, 0, 8);
const warm = RASTER.canvases;
RASTER.counting = false;
console.log('   whole roster, one phase: warmLook built', warmed, 'frames in', cold, 'canvases');
console.log('   eight more passes over the same set:', warm, 'canvases');
console.log('   cache size / cap:', BA.bossArtStats().cache, '/', BA.bossArtStats().cap);
if (warm !== 0) note(`whole-roster steady state still allocating: ${warm} canvases`);

/* ---------------- 10. the fallback does not lie --------------------------- */
console.log('\n10. FALLBACK');
const probes = [
  ['__no_such_boss__', {}],
  ['', {}],
  [null, {}],
  ['titan', {}],
  ['titan', { region: 'sliding_window_marsh' }],
  ['a_hunter_that_does_not_exist_yet', { region: 'stack_queue_mines' }],
  ['dp_ruins', {}],
  ['hash_titan', {}],
  ['interpreter', {}],
];
for (const [id, o] of probes) {
  const lk = BA.bossLook(id, o);
  const cv = BA.lookSprite(lk, { frame: 0 });
  console.log('   ', String(id).padEnd(34), JSON.stringify(o).padEnd(34),
    '->', lk.id.padEnd(24), lk.element.padEnd(10),
    'fallback=' + lk.fallback, cv.width + 'x' + cv.height);
  if (!cv || !cv.width) note(`fallback for ${id} produced no image`);
}
{
  const junk = BA.bossLook('__no_such_boss__');
  if (BA.NAMED_IDS.includes(junk.id)) note('an unknown id rendered as a named boss');
  const inRegion = BA.bossLook('__also_unknown__', { region: 'stack_queue_mines' });
  if (inRegion.element !== 'FIRE') note('region fallback lost its element');
  if (BA.NAMED_IDS.includes(inRegion.id)) note('region fallback claimed a named boss');
  console.log('   an unknown id in a fire region gets element:', inRegion.element,
    ' named-boss impersonation:', BA.NAMED_IDS.includes(inRegion.id));
}

/* ---------------- 11. hunters.py, when it lands --------------------------- */
console.log('\n11. HUNTERS INGEST (gauntlet/hunters.py is not in the tree)');
const before = BA.bossArtStats().total;
const taken = BA.ingestHunters([
  { id: 'hunter_emberwyrm', name: 'The Emberwyrm', region: 'stack_queue_mines' },
  { id: 'hunter_rimewalker', name: 'The Rimewalker', region: 'twin_pointer_pass' },
  { id: 'hunter_nothing', name: 'The Nothing', region: 'not_a_region' },
  null, 'garbage', { id: '' },
]);
console.log('   rows offered: 6   taken:', taken, '  looks', before, '->', BA.bossArtStats().total);
for (const id of ['hunter_emberwyrm', 'hunter_rimewalker']) {
  const lk = BA.bossLook(id);
  const cv = BA.lookSprite(lk, { frame: 0 });
  console.log('   ', id.padEnd(22), '->', lk.name.padEnd(18), lk.element.padEnd(10),
    'fallback=' + lk.fallback, cv.width + 'x' + cv.height);
  if (lk.fallback) note(`${id} was ingested but still reads as a fallback`);
}
if (BA.bossLook('hunter_nothing').id !== 'unknown') note('a region-less hunter row was guessed at');

/* ---------------- 12. the last interpreter -------------------------------- */
console.log('\n12. THE LAST INTERPRETER');
{
  const lk = BA.bossLook('the_last_interpreter');
  console.log('   wide:', lk.wide, ' box:', W(lk) + 'x' + BA.ART_H, ' rim refused:', !BA.wantsRim(lk));
  const g0 = BA.lookGrid(lk, { frame: 0, beat: 0, phase: 0 });
  const g2 = BA.lookGrid(lk, { frame: 0, beat: 0, phase: 2 });
  // Does it leave its own box? Count filled pixels on the frame edges.
  const edge = (g) => {
    let n = 0;
    for (let x = 0; x < g[0].length; x++) if (g[g.length - 1][x] !== '.') n++;
    for (let y = 0; y < g.length; y++) { if (g[y][0] !== '.') n++; }
    return n;
  };
  console.log('   pixels touching the frame edge (bottom + left):', edge(g0),
    '  — every other boss in the file:',
    BA.APEX_IDS.slice(0, 3).map(id => edge(BA.lookGrid(BA.bossLook(id), { frame: 0 }))).join(', '));
  // The indentation, measured: the column each scale seam starts at.
  // Seam rows are COIL.top + 2 and every third row after it. Measured from row
  // 29 down, which is clear of the head, the hat and the staff —
  // above that the leftmost pixel in a row belongs to the wizard rather than to
  // the snake, and an indent measured off the wrong edge is not an indent.
  const seamsAt = (g) => {
    const out = [];
    for (let y = 29; y < 64; y += 3) {
      const row = g[y];
      const l = row.search(/[^.]/);
      const d = row.indexOf('d');
      if (l >= 0 && d > l) out.push(d - l);
    }
    return out;
  };
  const seams = seamsAt(g0);
  const seams2 = seamsAt(g2);
  const g1 = BA.lookGrid(lk, { frame: 0, beat: 0, phase: 1 });
  console.log('   scale-seam indent, columns in from the body\'s own left edge:');
  console.log('     phase 0 (the block, properly nested):', seams.join(' '));
  console.log('     phase 1 (a tab among the spaces):    ', seamsAt(g1).join(' '));
  console.log('     phase 2 (the block ended):           ', seams2.join(' '));
  const flat = seams2.length > 2 && seams2.every(v => v === seams2[0]);
  const varied = new Set(seams).size > 1;
  console.log('   phase 0 is actually nested (more than one level):', varied);
  if (!varied) note('the interpreter phase 0 indentation is flat');
  console.log('   phase 2 collapsed to one margin:', flat);
  if (!flat) note('the interpreter did not collapse its indentation at phase 2');
  // The prompt is the brightest thing in the frame.
  const cv = BA.lookSprite(lk, { frame: 3, beat: 0, phase: 0 });
  const d = shot(cv).data;
  const hist = new Map();
  let best = -1, bestKey = '';
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue;
    const lum = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
    const k = `${d[i]},${d[i + 1]},${d[i + 2]}`;
    hist.set(k, (hist.get(k) || 0) + 1);
    if (lum > best) { best = lum; bestKey = k; }
  }
  console.log('   brightest colour in the frame:', bestKey, ' luminance', best.toFixed(1),
    ' pixels of it:', hist.get(bestKey));
  console.log('   distinct colours:', hist.size);
  if (bestKey !== '255,255,255') note('the prompt is not the brightest thing in the frame');
  // And that white is spent on this and nothing else in the roster.
  let elsewhere = 0;
  for (const other of looks) {
    if (other.id === lk.id) continue;
    for (let f = 0; f < 5; f++) for (let ph = 0; ph < 3; ph++) {
      const dd = shot(BA.lookSprite(other, { frame: f, beat: 0, phase: ph })).data;
      for (let i = 0; i < dd.length; i += 4) {
        if (dd[i + 3] && dd[i] === 255 && dd[i + 1] === 255 && dd[i + 2] === 255) { elsewhere++; break; }
      }
    }
  }
  console.log('   pure white (#ffffff) pixels anywhere else in the roster:', elsewhere);
  if (elsewhere) note('pure white is not exclusive to the prompt');
}

/* ---------------- 13. named bosses read apart ----------------------------- */
console.log('\n13. THE FOURTEEN, AND WHAT EACH ONE ARGUES');
for (const id of BA.NAMED_IDS) {
  const d = BA.describe(id);
  console.log('   ', d.id.padEnd(20), d.element.padEnd(10), d.verb.padEnd(7), d.region.padEnd(22));
  console.log('       ', d.note);
}

/* ---------------- 14. co-import ------------------------------------------- */
console.log('\n14. CO-IMPORT (bossart alongside everything main.js loads)');
{
  const sprites = await import('../../web/js/sprites.js');
  const palette = await import('../../web/js/palette.js');
  const pixel = await import('../../web/js/pixel.js');
  const probes = [
    ['sprites.bossSprite', typeof sprites.bossSprite],
    ['bosses.bossSprite', typeof B.bossSprite],
    ['bossart.lookSprite', typeof BA.lookSprite],
    ['sprites.BOSS_MOTION', typeof sprites.BOSS_MOTION],
    ['bosses.BOSS_MOTION', typeof B.BOSS_MOTION],
    ['bossart.lookMotion', typeof BA.lookMotion],
    ['pixel.bossSprite', typeof pixel.bossSprite],
  ];
  for (const [k, t] of probes) {
    console.log('   ', k.padEnd(22), t);
    if (t === 'undefined') note('missing ' + k);
  }
  // Nothing in bossart shadows or re-exports anything from the other two.
  const clashes = Object.keys(BA).filter(k => k in sprites || k in B);
  console.log('   names bossart shares with sprites.js or bosses.js:',
    clashes.length ? clashes : '(none)');
  if (clashes.length) note('bossart shadows: ' + clashes.join(', '));
  console.log('   bossart uses palette.RAMPS:', typeof palette.RAMPS === 'object',
    ' MAX_COLOURS:', palette.MAX_COLOURS);
}

/* ---------------- verdict ------------------------------------------------- */
console.log('\n================ VERDICT ================');
console.log(fail.length ? 'FAILURES (' + fail.length + '):' : 'no failures');
for (const f of fail.slice(0, 30)) console.log('  -', f);
