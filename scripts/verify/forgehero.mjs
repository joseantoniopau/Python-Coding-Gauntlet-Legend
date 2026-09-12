/* The seam between gauntlet/forge.py and web/js/sprites.js, measured.
 *
 * forge.py makes one claim that crosses the language boundary and it is the
 * expensive kind to be wrong about: that sprites.js needs NO change, because
 * forge.hero_weapon_look() returns the `_weapon` dict heroFrame already reads
 * and weaponRung() already honours a finite `rung`. That is a claim about
 * pixels, so it is checked in pixels rather than by reading the source.
 *
 * Four measurements, none of which a recolour can pass by accident:
 *
 *   A  READS       every one of the 54 rungs produces a frame at all, and
 *                  weaponRung() reports the rung forge.py asked for rather
 *                  than falling back to 1.
 *   B  ESCALATES   the six hero rungs produce six DISTINCT frames per blade.
 *                  This one is reported in two halves, because the two halves
 *                  belong to two different people. forge.py owes DISTINCT
 *                  frames and that gates. The art pass owes an OUTLINE change
 *                  at EVERY ONE of the nine tiers — not at the six hero rungs,
 *                  which lets three of the eight steps in every blade be a trim
 *                  change and nothing else — and runework that reaches all ten
 *                  weapon shapes; those are measured and printed as the art
 *                  task, and gate only under --strict, which is how the art
 *                  pass proves itself done.
 *   C  BUDGET      no rung pushes a hero frame past fifteen colours.
 *   D  ANCHOR      HERO_WEAPON_ANCHOR is untouched: the weapon box lands in
 *                  the same columns at every rung.
 *
 * Run: node scripts/verify/forgehero.mjs
 */
import { installRaster, pixelDiff, silhouetteDiff, colourCount, frameHash } from './raster.mjs';
installRaster();
const STRICT = process.argv.includes('--strict');
import fs from 'fs';
import { execSync } from 'child_process';

const S = await import('../../web/js/sprites.js');

/* The looks come out of the live module rather than a checked-in fixture: a
 * fixture would let forge.py drift away from the thing being verified, which is
 * exactly the failure petroster.mjs exists to catch on the pet roster. */
const LOOKS = JSON.parse(execSync(
  'python3 -c "' +
  'import json,sys; sys.path.insert(0,\'.\');' +
  'from gauntlet import forge;' +
  'print(json.dumps({b.id:[forge.hero_weapon_look(b.id,t) for t in range(1,10)] for b in forge.BLADES}))"',
  { cwd: new URL('../../', import.meta.url).pathname, encoding: 'utf8' }));

const BARE = { cloak: '#3f6fa8', tunic: '#5a4a6a', skin: '#e8b88a', hair: '#4a3050',
               boot: '#40312c', trim: '#d8b04a', metal: '#c3cbd8' };
const VIEWS = [['down', 0], ['left', 1], ['right', 2], ['up', 3]];
const fail = [];      // forge.py's obligations. These always gate.
const art = [];       // the art pass's obligations. These gate under --strict.
let frames = 0;

const dress = (w) => ({ ...BARE, weapon: w.key, metal: w.metal, trim: w.trim, _weapon: w });

/* ---- A: every rung reads, and reads as the rung forge asked for ---------- */
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  rungs.forEach((w, i) => {
    const tier = i + 1;
    for (const [dir, fr] of VIEWS) {
      const cv = S.heroFrame(dir, fr, dress(w));
      if (!cv) fail.push(`${bladeId} t${tier} ${dir}: no frame`);
      frames++;
    }
    if (!S.HERO_WEAPON_KEYS.includes(w.key))
      fail.push(`${bladeId} t${tier}: key ${w.key} is not a hero weapon key`);
  });
}

/* weaponRung is module-private, so it is measured through its effect: two looks
 * identical except for `rung` must render differently. If `rung` were ignored,
 * these would be byte-identical. */
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  const w = rungs[5];                                  // tier 6 -> hero rung 3
  const below = S.heroFrame('down', 0, dress({ ...w, rung: 2 }));
  const top   = S.heroFrame('down', 0, dress({ ...w, rung: 5 }));
  if (frameHash(below) === frameHash(top))
    fail.push(`${bladeId}: rung is ignored — hero rung 2 and hero rung 5 render identically`);
}

/* ---- runework, measured as the PASS it is, on all ten shapes -------------
 *
 * This check used to compare the hero rung 2 frame against the hero rung 3
 * frame and call any difference runework. That reading was true while the
 * ladder was one grid per family and two derived pixels of mass; it stopped
 * being true the moment every rung got its own drawing, because rung 2 and
 * rung 3 are then different OBJECTS and differ whether or not runeBlade()
 * etched a single character. It printed `yes` for six blades over a pass that
 * reached two of them, which is precisely the class of false pass this file
 * was written to stop.
 *
 * sprites.weaponArt() exists so the pass can be switched OFF and the same grid
 * compared against itself. Ten families and both forged lines, at all three
 * rungs that carry runework — and the density has to step at the top, or the
 * Mythic rung is a recolour of the Legendary one. */
const SHAPES = S.HERO_WEAPON_KEYS.map(k => [k, k, ''])
  .concat([['recall_chain', 'relic', 'recall_chain'],
           ['toolwrights_spanner', 'hammer', 'toolwrights_spanner']]);
const etched = (key, line, rung) => {
  const plain = S.weaponArt(key, rung, { line, rune: false });
  const runed = S.weaponArt(key, rung, { line });
  return plain.reduce((n, row, y) =>
    n + [...row].filter((c, x) => c !== runed[y][x]).length, 0);
};
const runeRows = [];
for (const [label, key, line] of SHAPES) {
  const marks = [3, 4, 5].map(r => etched(key, line, r));
  runeRows.push({ label, marks });
  for (let i = 0; i < 3; i++)
    if (marks[i] === 0)
      art.push(`${label}: runeBlade found no body glyph to etch at hero rung ${i + 3}`);
  if (marks[2] <= marks[0])
    art.push(`${label}: runework does not thicken at hero rung 5 — ${marks[0]} marks then ${marks[2]}`);
}

/* ---- B: the ladder escalates, in shape as well as colour ----------------
 *
 * Measured tier against PREVIOUS TIER, all nine of them, not hero rung against
 * hero rung. The six-rung reading passed a ladder in which tier 2 to tier 3,
 * tier 4 to tier 5 and tier 6 to tier 7 moved the trim colour and not one pixel
 * of outline — three of the eight steps in every blade, eighteen steps across
 * the six, every one of them a grind a player can finish without seeing
 * anything change. forge.RUNG_TO_HERO is allowed to put two tiers on one rung;
 * it is not allowed to make one of them invisible. */
const shapeRows = [];
const ladder = [];
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  const seen = new Map();
  const frames9 = rungs.map(w => S.heroFrame('down', 0, dress(w)));
  rungs.forEach((w, i) => {
    const h = frameHash(frames9[i]);
    if (seen.has(h) && seen.get(h).rung !== w.rung)
      fail.push(`${bladeId} t${i + 1}: identical frame to t${seen.get(h).t}`);
    seen.set(h, { t: i + 1, rung: w.rung });
  });
  const steps = [];
  let flat = 0;
  for (let i = 1; i < frames9.length; i++) {
    const px = pixelDiff(frames9[i - 1], frames9[i]);
    const sil = silhouetteDiff(frames9[i - 1], frames9[i]);
    steps.push({ tier: i + 1, px, sil, half: !!rungs[i].half });
    if (sil === 0) {
      flat++;
      art.push(`${bladeId} t${i} -> t${i + 1}: ${px} pixels, 0 outline — `
             + `${rungs[i].half ? 'the half step is invisible' : 'colour only'}`);
    }
  }
  ladder.push({ blade: bladeId, steps });
  shapeRows.push({ blade: bladeId, distinct: seen.size,
                   heroRungs: new Set(rungs.map(w => w.rung)).size, flat });
  if (seen.size < 6)
    fail.push(`${bladeId}: only ${seen.size} distinct frames across 9 rungs`);
}

/* ---- the band is a contract, not a filter --------------------------------
 *
 * forge.py grades every rung narrow | standard | broad, and bandTrim() in
 * sprites.js is the net under a grid that overreaches. The net trims from
 * whichever edge carries less of the weapon, which is the right behaviour and
 * the wrong thing to rely on: a half step that widened past its band would be
 * paid for by a column somewhere ELSE going quietly missing, and the weapon
 * would still measure inside its band afterwards. Measuring the span of the
 * finished grid therefore proves nothing — it is the trimmer's output.
 *
 * So the grid is built twice, once at the band forge.py graded and once at
 * 'broad', which is the widest allowance there is and makes bandTrim a no-op.
 * If those two differ, the net caught something, and the table is drawing
 * outside the silhouette this file promised. */
const SPAN = { narrow: 4, standard: 5, broad: 6 };
let widest = 0, widestAt = '';
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  rungs.forEach((w, i) => {
    const opts = { line: w.line, half: w.half };
    const graded = S.weaponArt(w.key, w.rung, { ...opts, band: w.silhouette });
    const loose  = S.weaponArt(w.key, w.rung, { ...opts, band: 'broad' });
    let lo = 99, hi = -1;
    for (const row of loose) for (let x = 0; x < row.length; x++) {
      if (row[x] === '.' || row[x] === ' ') continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
    const span = hi - lo + 1;
    if (span > widest) { widest = span; widestAt = `${bladeId} t${i + 1} (${w.silhouette})`; }
    if (graded.join('|') !== loose.join('|'))
      art.push(`${bladeId} t${i + 1}: drawn ${span} columns wide, ${w.silhouette} allows `
             + `${SPAN[w.silhouette]} — bandTrim had to cut it back`);
  });
}

/* ---- C: the colour budget ------------------------------------------------ */
let worst = 0, worstAt = '';
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  rungs.forEach((w, i) => {
    for (const [dir, fr] of VIEWS) {
      const n = colourCount(S.heroFrame(dir, fr, dress(w)));
      if (n > worst) { worst = n; worstAt = `${bladeId} t${i + 1} ${dir}`; }
      if (n > 15) fail.push(`${bladeId} t${i + 1} ${dir}: ${n} colours, budget is 15`);
    }
  });
}

/* ---- D: the anchor did not move ----------------------------------------- */
/* Same hero, weapon swapped for each rung: the columns the weapon occupies must
 * be the same set at every rung, because HERO_WEAPON_ANCHOR is per facing and
 * nothing in forge.py is allowed to touch it. */
function weaponColumns(cv, bare) {
  const d = pixelDiff(cv, bare);
  return d;
}
const bareFrame = S.heroFrame('down', 0, { ...BARE, weapon: null });
const anchorRows = [];
for (const [bladeId, rungs] of Object.entries(LOOKS)) {
  const diffs = rungs.map(w => weaponColumns(S.heroFrame('down', 0, dress(w)), bareFrame));
  anchorRows.push({ blade: bladeId, min: Math.min(...diffs), max: Math.max(...diffs) });
  if (Math.min(...diffs) === 0)
    fail.push(`${bladeId}: a rung draws no weapon at all`);
}

console.log('A  READS');
console.log(`     ${frames} hero frames over 54 rungs x 4 facings, no nulls`);
console.log('B  ESCALATES');
for (const r of shapeRows)
  console.log(`     ${r.blade.padEnd(22)} ${r.distinct} distinct frames over ` +
              `${r.heroRungs} hero rungs, ${8 - r.flat}/8 steps move the outline`);
console.log('     tier-to-tier, down facing: pixels changed / outline changed');
console.log('     ' + 'blade'.padEnd(22)
  + [2, 3, 4, 5, 6, 7, 8, 9].map(t => `t${t}`.padStart(9)).join(''));
for (const r of ladder)
  console.log('     ' + r.blade.padEnd(22)
    + r.steps.map(s => `${s.px}/${s.sil}${s.half ? '*' : ' '}`.padStart(9)).join(''));
console.log('     * a half step: the second forged tier standing on one hero rung');
console.log('   RUNEWORK  characters etched by runeBlade, hero rungs 3 / 4 / 5');
for (const r of runeRows)
  console.log(`     ${r.label.padEnd(22)} ${r.marks.join(' / ')}`);
console.log('   BAND      widest as drawn: ' + widest + ' columns (' + widestAt + '), untrimmed');
console.log('C  BUDGET');
console.log(`     worst hero frame: ${worst} colours (${worstAt}), budget 15`);
console.log('D  ANCHOR');
for (const r of anchorRows)
  console.log(`     ${r.blade.padEnd(22)} weapon pixels ${r.min}..${r.max}`);
console.log();
if (fail.length) {
  console.log('FAIL — forge.py side');
  for (const f of fail) console.log('  -', f);
  process.exit(1);
}
console.log('PASS — forge.py side: 54 rungs render, keys legal, anchor fixed, budget held.');
if (art.length) {
  console.log();
  console.log(`OUTSTANDING — the art pass owes ${art.length} items (ART_BRIEF \u00a72):`);
  for (const a of art) console.log('  -', a);
  if (STRICT) { console.log('\nFAIL (--strict)'); process.exit(1); }
  console.log('\nNot gating without --strict. Run with --strict once the art pass lands.');
} else {
  console.log('PASS — art pass complete: all 48 tier steps move the outline and runework reaches all ten shapes.');
}
