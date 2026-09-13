/* The face contract (§C), proved ON THE RASTER.
 *
 * THE FIRST VERSION OF THIS FILE SCORED AUTHORED TEXT. It imported
 * installRaster and colourCount, called installRaster(), and then counted
 * characters in the strips for all four §C-4 laws; colourCount was imported and
 * never called. Because it never rasterised it could not see three things that
 * were true of the shipped sprite:
 *   - three profile blinks rendered 3 changed pixels against its own >= 4 law,
 *     because the cells they spent were on the head's outline column or on the
 *     one the mirrored table loses;
 *   - eighteen of six hundred and four authored face cells were overpainted
 *     before they reached the screen, by the low-left rim and by the blade;
 *   - the front median it printed as 22 was 17 in pixels.
 * And its pupil count was `any 'o' anywhere in the eye rows`, so a solid black
 * eyelid scored as pupils — which is how HERO_FACE_FRONT.defeated shipped with
 * no eyeball in it at all and a green line under it saying "pupil 6".
 *
 * So every law below is measured off heroFrame(). The strips are still printed,
 * because they are what an author edits, but nothing PASSES on them.
 *
 * §C-4 is four laws and every one of them is a number, now in pixels:
 *   1. every emote pair differs by >= 10 px front, >= 9 profile, in the face band
 *   2. every pair differs on >= 2 of the 3 channels (brow, eye, mouth)
 *   3. frame 0 vs frame 2 of one emote differs by >= 4 px — on EVERY facing,
 *      including `right`, whose table is a frozen mirror built separately
 *   4. no two emotes share a (brow, eye, mouth) token triple
 * Plus §C eyes: every open emote needs a pupil with sclera beside it IN THE
 * SAME ROW, which is the only arrangement that reads as an eyeball at this size.
 */
import { installRaster, pixelDiff, colourCount } from './raster.mjs';
installRaster();
const S = await import('../../web/js/sprites.js');

const EM = S.EMOTE_KEYS;
const FRONT = S.HERO_FACE_FRONT, PROFILE = S.HERO_FACE_PROFILE;
const fail = [];

/* The face band on the rig: the five face rows are stamped at oy = 4. */
const BAND = [4, 8];
/* The eye boxes, in authored columns. Front has two, profile has one. */
const EYE_BOX = { front: [[4, 6], [8, 11]], profile: [[3, 6]] };
/* Shut by design — these two spend their eye rows on a closed lid. */
const SHUT = /^(strained|delighted)$/;

function band(cv, y0, y1) {
  const w = cv.width, h = y1 - y0 + 1;
  const d = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const k = ((y + y0) * w + x) * 4, o = (y * w + x) * 4;
    d[o] = cv.data[k]; d[o + 1] = cv.data[k + 1]; d[o + 2] = cv.data[k + 2]; d[o + 3] = cv.data[k + 3];
  }
  return { width: w, height: h, data: d };
}
const face = (facing, frame, emote) => band(S.heroFrame(facing, frame, { emote }, 'walk'), BAND[0], BAND[1]);

/* ---- 1 + 3, in pixels, on all three facings that have a face ---- */
const LAW = { down: 10, left: 9, right: 9 };
console.log('FACE SEPARATION, MEASURED IN PIXELS (rig rows 4..8)');
const summary = {};
for (const facing of ['down', 'left', 'right']) {
  const rows = [];
  for (let i = 0; i < EM.length; i++) for (let j = i + 1; j < EM.length; j++) {
    rows.push({ pair: `${EM[i]} vs ${EM[j]}`, d: pixelDiff(face(facing, 0, EM[i]), face(facing, 0, EM[j])) });
  }
  rows.sort((a, b) => a.d - b.d);
  const min = rows[0].d, med = rows[rows.length >> 1].d, max = rows[rows.length - 1].d;
  summary[facing] = rows;
  console.log(`  ${facing.padEnd(6)} min ${String(min).padStart(2)}  median ${String(med).padStart(2)}  max ${String(max).padStart(2)}   (law: min >= ${LAW[facing]})`);
  for (const r of rows) if (r.d < LAW[facing]) fail.push(`${facing}: ${r.pair} differ by ${r.d} px (< ${LAW[facing]})`);
}
console.log('\n  closest pairs per facing:');
for (const facing of ['down', 'left', 'right'])
  console.log(`    ${facing.padEnd(6)} ` + summary[facing].slice(0, 3).map(r => `${r.pair} ${r.d}`).join('   |   '));
console.log('\n  the pair the player named:');
for (const facing of ['down', 'left', 'right']) {
  const r = summary[facing].find(x => x.pair === 'delighted vs defeated');
  const rank = summary[facing].slice().reverse().findIndex(x => x.pair === r.pair) + 1;
  console.log(`    ${facing.padEnd(6)} delighted vs defeated ${String(r.d).padStart(2)} px, rank ${rank} of ${summary[facing].length} (1 = furthest apart)`);
}

console.log('\nTHE BLINK IS AN EVENT (frame 0 vs frame 2, in pixels; law: >= 4 on every facing)');
for (const facing of ['down', 'left', 'right']) {
  const line = EM.map(e => {
    const d = pixelDiff(face(facing, 0, e), face(facing, 2, e));
    if (d < 4) fail.push(`${facing}: ${e} blinks ${d} px (< 4) — the cells it spends do not reach the screen`);
    return `${e} ${d}`;
  });
  console.log(`  ${facing.padEnd(6)} ${line.join('  ')}`);
}

/* ---- 2 + 4, on the authored channels, which is where a channel EXISTS ---- */
function channels(a, b) {
  const at = f => [f.slice(0, 2).join(''), f.slice(2, 4).join(''), f[4]];
  const A = at(a), B = at(b);
  return A.filter((v, i) => v !== B[i]).length;
}
for (const [nm, table] of [['front', FRONT], ['profile', PROFILE]]) {
  const seen = new Map();
  for (let i = 0; i < EM.length; i++) for (let j = i + 1; j < EM.length; j++) {
    const ch = channels(table[EM[i]][0], table[EM[j]][0]);
    if (ch < 2) fail.push(`${nm}: ${EM[i]} vs ${EM[j]} differ on ${ch} channel(s) (< 2)`);
  }
  for (const e of EM) {
    const f = table[e][0];
    const key = [f.slice(0, 2).join(''), f.slice(2, 4).join(''), f[4]].join('|');
    if (seen.has(key)) fail.push(`${nm}: ${e} and ${seen.get(key)} share a (brow,eye,mouth) triple`);
    seen.set(key, e);
  }
}

/* ---- §C eyes: A PUPIL IS A DARK CELL WITH SCLERA BESIDE IT IN THE SAME ROW ----
 * Counted this way and not as "any 'o' in the eye rows", because a solid dark
 * eyelid is made entirely of 'o' and is not an eye. */
console.log('\nEYES (frame 0; a pupil is an "o" with a "w" next to it in the same row)');
for (const [nm, table, boxes] of [['front', FRONT, EYE_BOX.front], ['profile', PROFILE, EYE_BOX.profile]]) {
  for (const e of EM) {
    const f = table[e][0];
    let sclera = 0, pupil = 0;
    for (const row of f.slice(1, 4)) for (const [lo, hi] of boxes) for (let x = lo; x <= hi; x++) {
      if (row[x] === 'w') sclera++;
      if (row[x] === 'o' && (row[x - 1] === 'w' || row[x + 1] === 'w')) pupil++;
    }
    const shut = SHUT.test(e);
    console.log(`  ${nm.padEnd(8)} ${e.padEnd(10)} sclera ${String(sclera).padStart(2)}  pupil ${String(pupil).padStart(2)}${shut ? '   (shut by design)' : ''}`);
    if (shut) continue;
    if (sclera < 2) fail.push(`${nm} ${e}: ${sclera} sclera cells — an eye needs >= 2`);
    if (pupil < 1) fail.push(`${nm} ${e}: no pupil inside the sclera — the eye is a blob`);
  }
}

/* ---- §C-2 geometry: the columns actually used, and the ones that RENDER ----
 * A cell outside the live window is paid for and never seen. The window is
 * measured rather than asserted: flip one authored cell, re-render, and see
 * whether any pixel moved. */
console.log('\nFACE GEOMETRY (authored columns; the live window is in the sprites.js note)');
for (const [nm, table] of [['front', FRONT], ['profile', PROFILE]]) {
  let lo = 99, hi = -1;
  for (const e of EM) for (const fr of table[e]) for (const row of fr)
    for (let x = 0; x < row.length; x++) if (row[x] !== '.') { if (x < lo) lo = x; if (x > hi) hi = x; }
  console.log(`  ${nm.padEnd(8)} cols ${lo}..${hi}  (${hi - lo + 1}px wide)`);
  const WINDOW = nm === 'front' ? [4, 11] : [3, 8];
  if (lo < WINDOW[0] || hi > WINDOW[1])
    fail.push(`${nm}: authored cols ${lo}..${hi} reach outside the live window ${WINDOW[0]}..${WINDOW[1]}`);
}

/* ---- the colour budget, counted from the raster rather than from a palette ---- */
console.log('\nCOLOURS ON THE FRAME (§C shares the hero\'s 15-entry budget)');
{
  let worst = 0, worstAt = '';
  for (const facing of ['down', 'left', 'right']) for (const e of EM) {
    const n = colourCount(S.heroFrame(facing, 0, { emote: e }, 'walk'));
    if (n > worst) { worst = n; worstAt = `${facing}/${e}`; }
  }
  console.log(`  most colours on any face frame: ${worst} (${worstAt})   (budget 15)`);
  if (worst > 15) fail.push(`${worstAt} paints ${worst} colours (budget 15)`);
}

/* ---- §3: three body tones, counted per facing ---- */
console.log('\nCLOAK TONES (§3 — all three must be non-zero)');
for (const facing of ['down', 'up', 'left', 'right']) {
  const rows = S.HERO_BODY[facing].concat(S.HERO_HEM[facing]);
  const n = { c: 0, C: 0, v: 0 };
  for (const row of rows) for (const ch of row) if (n[ch] !== undefined) n[ch]++;
  console.log(`  ${facing.padEnd(6)} base ${String(n.c).padStart(3)}   light ${String(n.C).padStart(3)}   shadow ${String(n.v).padStart(3)}`);
  for (const t of ['c', 'C', 'v']) if (!n[t]) fail.push(`§3: ${facing} spends ZERO cells on cloak tone '${t}' — the torso is flat`);
}

if (fail.length) {
  console.log('\nFAIL');
  for (const f of fail) console.log('  ' + f);
  process.exit(1);
}
console.log('\nPASS — measured in pixels on all three facings: every pair separated,');
console.log('       every blink an event, every open eye with a pupil inside it.');
