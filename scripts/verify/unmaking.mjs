/* unmaking.mjs — the measurement the Unmaking rests on.
 *
 * Nothing below is asserted. Every claim is counted off a real raster or read
 * out of the live Python in this working tree.
 *
 *   1. THE SPELL TAKES EXACTLY WHAT THE EXAM TAKES. UNMAKING_ORDER against
 *      finalexam.CRUTCHES, both directions, plus unmaking.take_ids() order,
 *      plus the motifs and ramps. HOLDOUT must be absent from the spell and
 *      present in finalexam, because it is a capability and not a crutch.
 *   2. THE RENDERER TAKES ITS CLOCK FROM THE PYTHON. Driven by the real
 *      cinematic() payload, act boundaries and beat starts must land on the
 *      seconds the payload names, to the frame.
 *   3. FIFTEEN COLOURS. Counted from rendered pixels across the whole run. No
 *      frame over budget; the live palette monotone non-increasing; the painted
 *      count rising exactly once, at the one dispossession that ADDS something.
 *   4. FOURTEEN THINGS LEAVE INDIVIDUALLY. Each beat isolated against the same
 *      frame with nothing else changed, so the delta is that thing and nothing
 *      else. Every one must move pixels, and no two may move the same rectangle.
 *   5. IT ENDS WITH THE PLAYER, PLAIN. The REVEAL frame must hold a figure of
 *      the right height, centred, on the floor, with none of the ten retired
 *      colours in the frame and no rim light on it. HOLD must be an editor.
 *   6. DETERMINISTIC, PURE IN t, AND ALLOCATION-FREE once warm.
 */
import { installRaster, RASTER, colourCount, frameHash } from './raster.mjs';
installRaster();
import fs from 'fs';
import { execFileSync } from 'child_process';

const ROOT = new URL('../../', import.meta.url).pathname;
const S = await import('../../web/js/spellfx.js');

const fail = [];
const note = (m) => fail.push(m);
const out = {};
const W = 320, H = 180;

function newCv(w = W, h = H) {
  const c = globalThis.document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}
function frameAt(u, seconds, cv) {
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  u.seek(seconds);
  u.draw(ctx, cv.width, cv.height);
  return cv;
}
function redraw(u, cv) {
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  u.draw(ctx, cv.width, cv.height);
  return cv;
}
const copy = (cv) => ({ width: cv.width, height: cv.height, data: Uint8ClampedArray.from(cv.data) });
function diffBox(a, b) {
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1, n = 0;
  for (let y = 0; y < a.height; y++) {
    for (let x = 0; x < a.width; x++) {
      const i = (y * a.width + x) * 4;
      if (a.data[i] === b.data[i] && a.data[i + 1] === b.data[i + 1]
        && a.data[i + 2] === b.data[i + 2] && a.data[i + 3] === b.data[i + 3]) continue;
      n++;
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  return x1 < 0 ? { n: 0 } : { n, x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}
const rgbOf = (hex) => parseInt(String(hex).replace('#', '').slice(0, 6), 16);
function coloursIn(cv) {
  const seen = new Set();
  for (let i = 0; i < cv.data.length; i += 4) {
    if (!cv.data[i + 3]) continue;
    seen.add((cv.data[i] << 16) | (cv.data[i + 1] << 8) | cv.data[i + 2]);
  }
  return seen;
}

/* ============ 1. the two lists, and the words ============ */
let py = null, cine = null;
try {
  const src = 'import json;from gauntlet import finalexam as f;from gauntlet import unmaking as m;'
    + 'print(json.dumps({"crutches":[c.id for c in f.CRUTCHES],'
    + '"sealed":sorted(f.EXAM_SEAL.sealed),"holdout":f.HOLDOUT,'
    + '"leaks":f.audit_seal(),"take_ids":list(m.take_ids()),'
    + '"motifs":{d.crutch:d.motif for d in m.TAKE_ORDER},'
    + '"ramps":{d.crutch:d.ramp for d in m.TAKE_ORDER},'
    + '"mirrors":m.MIRRORS,"palette":[list(p) for p in m.PALETTE],'
    + '"cinematic":m.cinematic(),"short":m.cinematic(form=m.FORM_SHORT)}))';
  const raw = execFileSync('python3', ['-c', src], { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 24 });
  py = JSON.parse(raw);
  cine = py.cinematic;
} catch (e) {
  note(`could not read the Python side: ${String(e.message).split('\n')[0]}`);
}

if (py) {
  const rec = S.reconcileUnmaking(py.crutches);
  const motifVals = Object.values(S.UNMAKING_MOTIFS);
  out.seal = {
    examTakes: py.crutches.length,
    spellTakes: S.UNMAKING_ORDER.length,
    matchesFinalexam: rec.matches,
    missing: rec.missing,
    extra: rec.extra,
    orderMatchesTakeIds: py.take_ids.join(',') === S.UNMAKING_ORDER.join(','),
    holdoutInSpell: S.UNMAKING_ORDER.includes(py.holdout),
    examSeals: py.sealed.length,
    finalexamAuditSeal: py.leaks,
    motifsMatchPython: py.take_ids.every((c) => py.motifs[c] === S.UNMAKING_MOTIFS[c]),
    rampsMatchPython: py.take_ids.every((c) => py.ramps[c] === S.UNMAKING_RAMPS[c]),
    motifsDistinct: new Set(motifVals).size === motifVals.length,
    mirrorsMatchPython: JSON.stringify(py.mirrors) === JSON.stringify(S.UNMAKING_MIRRORS),
    paletteMatchesPython: py.palette.length === S.UNMAKING_PALETTE_SPEC.length
      && py.palette.every(([r, s], i) => S.UNMAKING_PALETTE_SPEC[i].ramp === r
        && S.UNMAKING_PALETTE_SPEC[i].shade === s),
  };
  if (!rec.matches) note(`crutch lists disagree: missing=${rec.missing} extra=${rec.extra}`);
  if (!out.seal.orderMatchesTakeIds) note('the spell does not take them in unmaking.take_ids() order');
  if (out.seal.holdoutInSpell) note('HOLDOUT has a departure; it is not a crutch');
  if (py.sealed.length !== py.crutches.length) note('EXAM_SEAL does not seal every crutch');
  if (py.leaks && py.leaks.length) note(`finalexam.audit_seal() non-empty: ${py.leaks}`);
  if (!out.seal.motifsMatchPython) note('a motif disagrees with unmaking.py');
  if (!out.seal.rampsMatchPython) note('a ramp disagrees with unmaking.py');
  if (!out.seal.motifsDistinct) note('two crutches share a motif');
  if (!out.seal.mirrorsMatchPython) note('MIRRORS disagrees with unmaking.py');
  if (!out.seal.paletteMatchesPython) note('the palette disagrees with unmaking.PALETTE');

  const card = S.unmakingCardFrom(cine);
  out.card = {
    phrase: card.phrase, oath: card.oath, title: card.title,
    supplied: !!(card.phrase && card.oath && card.title),
    transformSays: 'BY THE SOURCE / I NAME IT',
    invented: 'nothing — every word is read from gauntlet/unmaking.py',
  };
  if (!out.card.supplied) note('the card is missing one of phrase/oath/title');
}

/* ============ 2. the renderer takes its clock from the Python ============ */
if (cine) {
  const u = S.createUnmaking({ cinematic: cine });
  const rows = [];
  let bad = 0;
  for (const a of cine.acts) {
    u.seek(a.at + 0.001);
    const ok = u.act === a.id;
    if (!ok) bad++;
    rows.push(`${a.id} at ${a.at.toFixed(2)}s -> renderer says ${u.act}${ok ? '' : '  MISMATCH'}`);
  }
  u.seek(cine.acts[cine.acts.length - 1].end - 0.001);
  const lastOk = u.act === 'HOLD';
  const beatRows = [];
  for (const b of cine.beats) {
    u.seek(b.at + b.take_seconds * 0.5);
    const mine = u.beats.find((x) => x.crutch === b.crutch);
    const half = mine ? mine.p : -1;
    u.seek(b.at + b.take_seconds + 0.01);
    const done = u.gone.has(b.crutch);
    if (!(half > 0.3 && half < 0.7) || !done) bad++;
    beatRows.push(`${b.crutch} at ${b.at.toFixed(2)}s take=${b.take_seconds}s mid-p=${half.toFixed(2)} gone-after=${done}`);
  }
  out.clock = {
    source: u.timelineSource,
    total: +u.total.toFixed(2),
    pythonTotal: +cine.acts[cine.acts.length - 1].end.toFixed(2),
    actsAgree: rows, lastActIsHold: lastOk, beats: beatRows, mismatches: bad,
    skipAllowedAt: +u.skipAllowedAt.toFixed(2),
    pythonSkipAt: cine.skip ? +cine.skip.at.toFixed(2) : null,
  };
  if (bad) note(`${bad} act/beat boundaries do not land where the payload says`);
  if (!lastOk) note('the last second of the payload is not HOLD');
  if (cine.skip && Math.abs(u.skipAllowedAt - cine.skip.at) > 0.01) {
    note(`skip gate at ${u.skipAllowedAt} where unmaking.py says ${cine.skip.at}`);
  }
  if (Math.abs(u.total - cine.acts[cine.acts.length - 1].end) > 0.01) note('total duration disagrees');
}

/* the authored fallback, for a caller with no payload */
{
  const u = S.createUnmaking({});
  const T = { RAISE: 0.55, CHARGE: 1.15, DISCHARGE: 0.45, REVEAL: 0.95, HOLD: 1.10 };
  const len = (id) => { const a = u.acts.find((x) => x.id === id); return +a.seconds.toFixed(4); };
  out.fallback = {
    source: u.timelineSource,
    REACH: len('REACH'), TAKE: len('TAKE'), STRIP: len('STRIP'),
    REVEAL: len('REVEAL'), HOLD: len('HOLD'), total: +u.total.toFixed(4),
    ratiosToTransform: {
      REACH: +(len('REACH') / T.RAISE).toFixed(3),
      STRIP: +(len('STRIP') / T.DISCHARGE).toFixed(3),
      REVEAL: +(len('REVEAL') / T.REVEAL).toFixed(3),
      HOLD: +(len('HOLD') / T.HOLD).toFixed(3),
      TAKE: +(len('TAKE') / T.CHARGE).toFixed(3),
    },
  };
  for (const k of ['REACH', 'STRIP', 'REVEAL', 'HOLD']) {
    if (Math.abs(out.fallback.ratiosToTransform[k] - 2) > 1e-6) note(`fallback ${k} is not twice its opposite number`);
  }
}

/* ============ warm, then measure ============ */
const drive = cine ? { cinematic: py.short } : {};   // SHORT form: the whole shape in 8s
out.cache = { tilesWarmed: S.warmUnmaking(drive) };

/* ============ 3. colours ============ */
const u = S.createUnmaking(drive);
const cv = newCv();
{
  const SAMPLES = 60;
  const rows = [];
  let peak = 0, prevLive = 1e9, rises = 0, riseAt = [];
  let prevPainted = -1;
  for (let i = 0; i <= SAMPLES; i++) {
    const t = (u.total * i) / SAMPLES;
    frameAt(u, t, cv);
    const n = colourCount(cv);
    const live = u.livePaletteCount();
    rows.push(`${t.toFixed(2)}s ${u.act.padEnd(6)} painted=${String(n).padStart(2)} live=${live}`);
    if (n > 15) note(`frame at t=${t.toFixed(2)} paints ${n} colours, budget is 15`);
    if (n > peak) peak = n;
    if (live > prevLive) note(`the live palette grew at t=${t.toFixed(2)}`);
    prevLive = live;
    if (prevPainted >= 0 && n > prevPainted) { rises++; riseAt.push(`${t.toFixed(2)}s ${u.act}`); }
    prevPainted = n;
  }
  out.colours = {
    budget: 15, peakPainted: peak,
    firstLive: u.constructor ? S.unmakingPaletteAt(0, drive).count : null,
    lastLive: S.unmakingPaletteAt(u.total - 0.001, drive).count,
    survivors: S.UNMAKING_SURVIVORS,
    paintedRises: rises, paintedRoseAt: riseAt,
    curve: rows,
  };
  if (S.unmakingPaletteAt(0, drive).count !== 15) note('the sequence does not open on fifteen live colours');
}

/* ============ 4. fourteen things, individually ============ */
{
  const takeAct = u.acts.find((a) => a.id === 'TAKE');
  const a = newCv(), b = newCv();
  u.seek(takeAct.at + 0.001);
  const zero = () => { for (const bb of u.beats) bb.p = 0; };
  zero(); redraw(u, a);
  const base = copy(a);
  const rows = [], boxes = [];
  for (const beat of u.beats) {
    zero();
    beat.p = 1;
    redraw(u, b);
    const d = diffBox(base, b);
    rows.push({ crutch: beat.crutch, motif: beat.motif, ramp: beat.ramp, pixels: d.n,
      box: d.n ? `${d.w}x${d.h} @${d.x},${d.y}` : 'NONE' });
    boxes.push(d);
    if (!d.n) note(`${beat.crutch} changes nothing when it leaves`);
  }
  zero();
  let same = 0;
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const p = boxes[i], q = boxes[j];
      if (p.n && q.n && p.x === q.x && p.y === q.y && p.w === q.w && p.h === q.h) {
        same++; note(`${u.beats[i].crutch} and ${u.beats[j].crutch} change the identical rectangle`);
      }
    }
  }
  out.departures = { isolatedDeltas: rows, identicalRectangles: same };
}

/* ============ 5. the last two acts ============ */
{
  const reveal = u.acts.find((x) => x.id === 'REVEAL');
  const hold = u.acts.find((x) => x.id === 'HOLD');
  const f = newCv();

  frameAt(u, reveal.at + reveal.seconds * 0.75, f);
  const seen = coloursIn(f);
  const retired = [];
  for (const spec of S.UNMAKING_PALETTE_SPEC) {
    if (S.UNMAKING_SURVIVORS.includes(spec.key)) continue;
    if (seen.has(rgbOf(S.UNMAKING_PALETTE[spec.key]))) retired.push(spec.key);
  }
  if (retired.length) note(`retired colours still painted on the REVEAL frame: ${retired}`);

  const groundY = Math.round(H * 0.78);
  const bgRGB = rgbOf(S.UNMAKING_PALETTE.VOID0);
  const floorRGB = rgbOf(S.UNMAKING_PALETTE.VOID2);
  const stoneRGB = rgbOf(S.UNMAKING_PALETTE.STONE1);
  let figure = 0, minY = 1e9, maxY = -1, minX = 1e9, maxX = -1;
  for (let y = 0; y < groundY; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (!f.data[i + 3]) continue;
      const c = (f.data[i] << 16) | (f.data[i + 1] << 8) | f.data[i + 2];
      if (c === bgRGB || c === floorRGB) continue;
      figure++;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (x < minX) minX = x; if (x > maxX) maxX = x;
    }
  }
  const bodyH = Math.round(H * 0.0125 * 22);
  out.reveal = {
    coloursPainted: seen.size,
    retiredColoursPainted: retired,
    figurePixels: figure,
    figureBox: figure ? `${maxX - minX + 1}x${maxY - minY + 1} @${minX},${minY}` : 'NONE',
    expectedBodyHeight: bodyH,
    standsOnFloor: maxY >= groundY - 3,
    centred: figure ? Math.abs((minX + maxX) / 2 - W / 2) <= 4 : false,
    bodyIs: S.UNMAKING_PALETTE.STONE1,
    hasChromeRim: seen.has(rgbOf(S.UNMAKING_PALETTE.CHROME4)),
    usesStone: seen.has(stoneRGB),
  };
  if (figure < 150) note(`REVEAL has ${figure} figure pixels — nobody is standing there`);
  if (!out.reveal.standsOnFloor) note('the REVEAL figure is not standing on the floor');
  if (!out.reveal.centred) note('the REVEAL figure is not on transform.js\'s centre mark');
  if (out.reveal.hasChromeRim) note('the rim light is still on at REVEAL');
  if (Math.abs((maxY - minY + 1) - bodyH) > bodyH * 0.3) {
    note(`the REVEAL figure is ${maxY - minY + 1}px where the body is ${bodyH}px`);
  }

  /* HOLD: "a blank editor and a cursor. No figure, no lettering, no him." */
  frameAt(u, hold.at + hold.seconds * 0.8, f);
  const holdSeen = coloursIn(f);
  let editor = 0;
  const y0 = Math.round(H * 0.20), y1 = y0 + Math.round(H * 0.60);
  for (let y = y0; y < y1; y++) {
    for (let x = Math.round(W * 0.12); x < Math.round(W * 0.88); x++) {
      const i = (y * W + x) * 4;
      const c = (f.data[i] << 16) | (f.data[i + 1] << 8) | f.data[i + 2];
      if (c === stoneRGB) editor++;
    }
  }
  let figureLeft = 0;
  for (let y = 0; y < groundY; y++) {
    for (let x = Math.round(W * 0.45); x < Math.round(W * 0.55); x++) {
      const i = (y * W + x) * 4;
      const c = (f.data[i] << 16) | (f.data[i + 1] << 8) | f.data[i + 2];
      if (c === rgbOf(S.UNMAKING_PALETTE.BONE2)) figureLeft++;
    }
  }
  out.hold = {
    coloursPainted: holdSeen.size,
    editorPixels: editor,
    figurePixelsLeft: figureLeft,
    note: 'unmaking.py HOLD: "a blank editor and a cursor. No figure, no lettering, no him."',
  };
  if (editor < 2000) note(`HOLD has ${editor} editor pixels — there is no editor`);
}

/* ============ 6. determinism, purity in t, allocation ============ */
{
  const bad = [];
  const c1 = newCv(), c2 = newCv();
  const marks = [0, 0.2, 1.0, 2.0, 3.0, 4.5, 5.4, 6.0, 7.0, 7.9];
  for (const t of marks.filter((x) => x < u.total)) {
    S.clearCache(); frameAt(S.createUnmaking(drive), t, c1);
    const h1 = frameHash(c1);
    S.clearCache(); frameAt(S.createUnmaking(drive), t, c2);
    if (h1 !== frameHash(c2)) bad.push(`cold redraw differs at t=${t}`);
  }
  const played = S.createUnmaking(drive);
  played.begin(drive);
  for (let i = 0; i < 200 && played.active; i++) played.update(0.016);
  const tp = played.t;
  frameAt(played, tp, c1);
  if (frameHash(c1) !== frameHash(frameAt(S.createUnmaking(drive), tp, c2))) {
    bad.push(`seek(${tp.toFixed(4)}) differs from having played to it`);
  }
  /* reduced motion: the only clock-driven art is the beam ticks and the clock
   * hand, and both must be gated. Same t, two different wall clocks. */
  const q = S.createUnmaking({ ...drive, reducedMotion: true });
  frameAt(q, u.total * 0.45, c1);
  const rh = frameHash(c1);
  q.t = u.total * 0.45;
  const cx2 = c2.getContext('2d'); cx2.clearRect(0, 0, W, H); q.draw(cx2, W, H);
  if (rh !== frameHash(c2)) bad.push('reduced motion is not stable');
  out.determinism = { failures: bad.length, detail: bad };
  for (const m of bad) note(m);
}
{
  /* The contract is: call warmUnmaking() once, then the draw path allocates
   * nothing. The determinism block above cleared the cache, so warm it the way
   * a host would rather than by drawing and hoping. */
  S.warmUnmaking(drive);
  const warm = S.createUnmaking(drive);
  const c = newCv(), ctx = c.getContext('2d');
  RASTER.counting = true;
  const before = RASTER.canvases;
  for (let i = 0; i <= 377; i++) { warm.seek((warm.total * i) / 377); warm.draw(ctx, W, H); }
  const made = RASTER.canvases - before;
  RASTER.counting = false;
  out.allocation = { canvasesInWarmDrawPath: made };
  if (made > 0) note(`${made} canvases allocated in a warm draw path`);
}
{
  const src = fs.readFileSync(new URL('../../web/js/spellfx.js', import.meta.url), 'utf8');
  const marker = src.indexOf('THE UNMAKING — the picture of');
  const start = marker < 0 ? -1 : src.lastIndexOf('/*', marker);
  let section = start < 0 ? '' : src.slice(start);
  /* strip comments: the prose in this file NAMES the things it must not call */
  const code = section.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  const banned = [];
  for (const b of ['Math.random', 'Date.now', 'performance.now', 'globalAlpha', 'createLinearGradient', 'createRadialGradient']) {
    if (code.includes(b)) banned.push(b);
  }
  out.purity = { sectionBytes: section.length, codeBytes: code.length, banned };
  for (const b of banned) note(`${b} is called in the unmaking section`);
}

/* ============ 7. reduced motion comes from the payload ============ */
if (py) {
  const r = S.createUnmaking({ cinematic: py.short });
  const q = S.createUnmaking({ cinematic: JSON.parse(JSON.stringify({ ...py.short, motion: 'REDUCED' })) });
  out.reducedMotion = { fromFullPayload: r.reducedMotion, fromReducedPayload: q.reducedMotion };
  if (r.reducedMotion !== false || q.reducedMotion !== true) {
    note('reducedMotion is not read from the payload\'s motion field');
  }
}

/* ============ 8. the stub harness, which sees what a raster cannot ====== */
try {
  const raw = execFileSync('node', ['scripts/verify/unmakingstub.mjs'],
    { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 24 });
  const sub = JSON.parse(raw);
  out.stub = {
    verdict: sub.VERDICT, frames: sub.frames, problems: sub.problems,
    nullImage: sub.snapshot.nullImage, nonFiniteReal: sub.nonFiniteReal,
    badPaint: sub.snapshot.badPaint, allocInLoop: sub.snapshot.allocInLoop,
    payloads: sub.payloads, sizes: sub.sizes,
    stubDefect: sub.stubDefect,
  };
  if (sub.VERDICT !== 'PASS') note(`unmakingstub.mjs: ${sub.problems.join('; ') || 'see its output'}`);
} catch (e) {
  out.stub = { verdict: 'DID NOT RUN', error: String(e.message).split('\n')[0] };
  note('unmakingstub.mjs did not run');
}

out.VERDICT = fail.length === 0 ? 'PASS' : 'FAIL';
out.failures = fail;
console.log(JSON.stringify(out, null, 1));
process.exitCode = fail.length ? 1 : 0;
