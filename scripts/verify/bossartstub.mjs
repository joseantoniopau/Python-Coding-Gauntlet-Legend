/* bossart.js through the INSTRUMENTED stub.
 *
 * bossart.mjs rasterises, which answers questions about pixels. It cannot
 * answer the four that stub.mjs exists for, and one of them is the dangerous
 * one here: a palette lookup that misses yields undefined, assigning undefined
 * to fillStyle is a no-op in the browser, and the pixels stay transparent. A
 * rasterising harness sees a hole and has no way to know it was not authored.
 * This one catches it at the assignment.
 */
import { installStub, REC, newCtx, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();

const BA = await import('../../web/js/bossart.js');
const B = await import('../../web/js/bosses.js');

const ctx = newCtx(640, 360);
const fail = [];
const run = (label, fn) => {
  setWhere(label);
  try { return fn(); } catch (e) { fail.push(`THROW ${label}: ${e.constructor.name}: ${e.message}`); }
};

console.log('bossart.js under stub.mjs');
/* The ladder goes across too, not just the glyph table: ART_W/ART_H/
 * ART_WIDE_W/ART_FINAL_W/ART_FINAL_H against bosses.js's five. That second
 * argument is the whole reason bossArtSelfCheck grew one, and all three
 * harnesses were calling it with one argument, so the check never ran. */
const selfCheck = BA.bossArtSelfCheck(B.BOSS_GLYPHS,
  { w: B.BOSS_W, h: B.BOSS_H, wide: B.BOSS_WIDE_W, finalW: B.FINAL_BOSS_W, finalH: B.FINAL_BOSS_H });
console.log('  self check vs bosses.BOSS_GLYPHS + the ladder:', JSON.stringify(selfCheck));
if (!selfCheck.ok) fail.push('self check: ' + selfCheck.problems.join('; '));

/* Every look, every frame, every phase, every beat, plus the metadata calls. */
let built = 0;
for (const lk of BA.allLooks()) {
  for (let ph = 0; ph < 3; ph++) {
    for (let f = 0; f < 5; f++) {
      for (let b = 0; b < (f <= 1 ? 6 : 1); b++) {
        const img = run(`lookSprite(${lk.id},f${f},b${b},p${ph})`,
          () => BA.lookSprite(lk, { frame: f, beat: b, phase: ph }));
        if (!img || !img.width || !img.height) fail.push(`${lk.id} f${f} b${b} p${ph}: no image`);
        else built++;
      }
    }
  }
  run(`lookMotion(${lk.id})`, () => BA.lookMotion(lk));
  run(`lookLighting(${lk.id})`, () => BA.lookLighting(lk));
  run(`describe(${lk.id})`, () => BA.describe(lk));
  run(`lookSilhouette(${lk.id})`, () => BA.lookSilhouette(lk));
  run(`lookPalette(${lk.id})`, () => BA.lookPalette(lk, 2));
  run(`elementPalette(${lk.id})`, () => BA.elementPalette(B.bossPalette(lk.colour, lk.accent, 1), lk, 1));
}
console.log('  frames built:', built);

/* Garbage in. Every one of these must produce a canvas rather than an
 * exception, because an unknown boss id reaches this module from a save file
 * written by a version of the game that no longer exists. */
for (const junk of ['', null, undefined, '__nope__', 0, 1, {}, [], 'titan', 'dp_ruins',
  'hunter_not_yet_written', 'THE_INTERVIEWER', '../../etc/passwd']) {
  const lk = run(`bossLook(${String(junk)})`, () => BA.bossLook(junk));
  const img = run(`lookSprite(${String(junk)})`, () => BA.lookSprite(junk));
  if (!img || !img.width) fail.push(`junk ${String(junk)} produced no image`);
  if (lk && BA.NAMED_IDS.includes(lk.id) && !['titan', 'THE_INTERVIEWER'].includes(junk)) {
    fail.push(`junk ${String(junk)} resolved to the named boss ${lk.id}`);
  }
}
/* elementPalette must reassign slots and never add one: a theme pass may change
 * what a boss is made of and may not change what it costs. */
{
  let added = 0, changed = 0, checked = 0;
  for (const lk of BA.allLooks()) {
    for (let ph = 0; ph < 3; ph++) {
      const base = B.bossPalette(lk.colour, lk.accent, ph);
      const out = BA.elementPalette(base, lk, ph);
      checked++;
      for (const k of Object.keys(out)) if (!(k in base)) { added++; fail.push(`elementPalette added slot '${k}' for ${lk.id}`); }
      for (const k of Object.keys(base)) if (out[k] !== base[k]) changed++;
      for (const k of Object.keys(out)) if (!out[k]) fail.push(`elementPalette left '${k}' undefined for ${lk.id}`);
    }
  }
  console.log('  elementPalette over', checked, 'look/phase pairs: slots ADDED', added,
    ' slots reassigned', changed);
}

run('dressGrid(null)', () => BA.dressGrid(null, null, {}));
run('dressGrid([])', () => BA.dressGrid([], BA.bossLook('x'), {}));
run('motifsFor(null)', () => BA.motifsFor(null));
run('wantsRim(null)', () => BA.wantsRim(null));
run('ingestHunters(null)', () => BA.ingestHunters(null));
run('ingestHunters(junk)', () => BA.ingestHunters([1, 'a', null, {}, { id: 'z' }]));
run('strayGlyphs(null)', () => BA.strayGlyphs(null));

/* Allocation inside a render loop. warmLook builds the working set, then the
 * loop draws it 600 times and must not create a canvas. */
const set = BA.allLooks().slice(0, 4);
BA.clearBossArtCache();
for (const lk of set) BA.warmLook(lk, 0);
enterLoop('bossart render loop');
for (let i = 0; i < 600; i++) {
  for (const lk of set) {
    const p = BA.lookMotion(lk);
    const img = BA.lookSprite(lk, { frame: i % 2, beat: i % 6, phase: 0 });
    ctx.drawImage(img, 100, 100, img.width, img.height);
    if (!p) fail.push('no motion');
  }
}
exitLoop();

const snap = snapshot();
console.log('  stub snapshot:', JSON.stringify(snap));
console.log('  nullImage  :', REC.nullImage.length, REC.nullImage.slice(0, 3));
console.log('  nonFinite  :', REC.nonFinite.length, REC.nonFinite.slice(0, 3));
console.log('  badPaint   :', REC.badPaint.length, REC.badPaint.slice(0, 3));
console.log('  allocInLoop:', REC.allocInLoop.length, REC.allocInLoop.slice(0, 3));
for (const k of ['nullImage', 'nonFinite', 'badPaint', 'allocInLoop']) {
  if (REC[k].length) fail.push(`${k}: ${REC[k].length}`);
}

console.log('\n  VERDICT:', fail.length ? 'FAILURES' : 'clean');
for (const f of fail.slice(0, 20)) console.log('   -', f);
/* Same as bossart.mjs: a verdict nothing reports to the shell is a verdict
 * nobody acts on. */
process.exitCode = fail.length ? 1 : 0;
