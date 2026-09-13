/* deathstub.mjs — the four failure classes a raster cannot see.
 *
 * raster.mjs answers "what got painted". This answers the questions that leave
 * no pixels behind: a drawImage from a nullish or zero-size source, a
 * non-finite coordinate, a paint value that resolved to undefined (a missing
 * ramp step renders transparent and silently), and a canvas allocated while a
 * render loop is running.
 *
 * The death screen is driven the way a host drives it and the way a host gets
 * it wrong: every kit, every canvas size including degenerate ones, forwards
 * and scrubbed, reduced and not, with the alarm colour absent, garbage, and
 * real; and with the death report null, empty and hostile.
 *
 * Run on its own — it cannot share a process with death.mjs, because the two
 * install different globals.
 */
import { installStub, REC, newCtx, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();
import { execFileSync } from 'child_process';

const ROOT = new URL('../../', import.meta.url).pathname;
const D = await import('../../web/js/deathfx.js');
const A = await import('../../web/js/audio.js');

const problems = [];
let frames = 0;

const LOOKS = [
  ['bare', { weapon: 'sword', emote: 'neutral' }],
  ['plate', { weapon: 'sword', emote: 'neutral', cloak: '#52456e', tunic: '#7d6b90',
              metal: '#b0aabd', trim: '#a08a52', boot: '#715b45', skin: '#c08a62', hair: '#4a3a2c',
              _pieces: [{ piece: 'helmet', at: 75 }, { piece: 'chestplate', at: 75 }] }],
  ['none', null],
  ['garbage', { weapon: 42, emote: null, cloak: 'not-a-colour', metal: undefined }],
];
const COLOURS = [undefined, null, '', 'red', '#ff3b46', '#nope', 12345, '#ff6a7a'];
const SIZES = [[192, 128], [960, 540], [1440, 810], [240, 135], [1, 1]];

/* Warm first. A death screen that allocates on its first frame stutters on the
 * frame the player is paying the most attention to. */
for (const [, look] of LOOKS) D.warmDeath({ look });
D.warmDeath({});

for (const [name, look] of LOOKS) {
  for (const alarmColour of COLOURS) {
    for (const reduced of [false, true]) {
      for (const [w, h] of SIZES) {
        const ctx = newCtx(w, h);
        const label = `${name} ${String(alarmColour)} ${reduced ? 'reduced' : 'full'} ${w}x${h}`;
        setWhere(label);
        D.warmDeath({ look, alarmColour });
        const e = D.createDeath({ look, alarmColour, reduced });
        enterLoop(label);
        // scrubbed: every frame is a pure function of t, so this covers the
        // whole timeline without playing four seconds of it
        e.begin({});
        for (let i = 0; i <= 120; i++) { e.seek((e.total * i) / 120); e.draw(ctx, w, h); frames++; }
        // and played, the way a host drives it
        e.begin({});
        for (let i = 0; i < 300 && e.active; i++) { e.update(0.016); e.draw(ctx, w, h); frames++; }
        exitLoop();
        e.cancel();
      }
    }
  }
}

/* dt values a real frame clock produces, including the ones it should not */
{
  const ctx = newCtx(640, 360);
  const e = D.createDeath({ look: LOOKS[1][1] }).begin({});
  setWhere('pathological dt');
  for (const dt of [0, -1, NaN, Infinity, -Infinity, 1e6, 100, 0.016, undefined, null, '0.5', {}]) {
    try { e.update(dt); e.draw(ctx, 640, 360); frames++; }
    catch (err) { problems.push(`update(${String(dt)}) threw ${err.message}`); }
    if (!Number.isFinite(e.t)) problems.push(`update(${String(dt)}) put t at ${e.t}`);
  }
  setWhere('degenerate canvases');
  for (const [w, h] of [[0, 0], [1, 1], [-5, 20], [NaN, NaN], [Infinity, 10]]) {
    try { e.draw(newCtx(Math.max(1, w | 0 || 1), Math.max(1, h | 0 || 1)), w, h); frames++; }
    catch (err) { problems.push(`draw(${w}x${h}) threw ${err.message}`); }
  }
  try { e.draw(null, 640, 360); } catch (err) { problems.push(`draw(null) threw ${err.message}`); }
  try { e.draw(undefined); } catch (err) { problems.push(`draw(undefined) threw ${err.message}`); }
}

/* seek and skip from everywhere, including off both ends */
{
  setWhere('seek/skip');
  const ctx = newCtx(640, 360);
  for (const t of [-1e9, -1, 0, 1, 832, 833, 2370, 2371, 2883, 2884, 3908, 3909, 1e9, NaN, Infinity]) {
    const e = D.createDeath({ look: LOOKS[0][1], seen: 1 }).begin({});
    try {
      e.seek(t); e.draw(ctx, 640, 360); frames++;
      if (!Number.isFinite(e.t) || e.t < 0 || e.t > e.total) problems.push(`seek(${t}) -> t=${e.t}`);
      e.skip();
      if (e.t !== e.total || e.active) problems.push(`skip() after seek(${t}) left t=${e.t} active=${e.active}`);
      e.skip(); e.cancel(); e.cancel();     // idempotent
    } catch (err) { problems.push(`seek(${t}) threw ${err.message}`); }
  }
}

/* a report that is wrong in every way a server can be wrong */
{
  setWhere('reports');
  for (const rep of [null, undefined, {}, [], 7, 'no', { wake: null }, { wake: [] },
    { wake: { label: null, region: 0 } }, { cost: null }, { cost: { gold: NaN, items: -3, playtime: 12 } },
    { kept: { attempts: '1841', skills: null, mastery: 61, due: Infinity } },
    { wake: { label: '   ' }, cost: {}, kept: {} }]) {
    let out;
    try { out = D.deathLines(rep); }
    catch (err) { problems.push(`deathLines(${JSON.stringify(rep)}) threw ${err.message}`); continue; }
    const text = JSON.stringify(out);
    if (/undefined|NaN|null|Infinity|\[object/.test(text)) problems.push(`deathLines(${JSON.stringify(rep)}) leaked a raw value: ${text}`);
    if (!out.lines.some(l => l.id === 'kept')) problems.push(`deathLines(${JSON.stringify(rep)}) dropped the kept line`);
    if (!out.actions || !out.actions.length) problems.push(`deathLines(${JSON.stringify(rep)}) left no way out`);
    // LEARNING NEVER DEAD-ENDS: whatever the server said, there is a next step.
    if (!out.lines.length) problems.push(`deathLines(${JSON.stringify(rep)}) said nothing at all`);
  }
}

/* audio: the death sequence with no AudioContext at all, which is what a
 * browser before the first gesture actually looks like */
{
  setWhere('audio cold');
  A.audio.enabled = false;
  const h1 = A.audio.heartbeatStop();
  if (!h1 || h1.times.length !== 3) problems.push('heartbeatStop() with audio off did not return the timing table');
  try { h1.cancel(); h1.cancel(); } catch (err) { problems.push(`cancel() threw ${err.message}`); }
  if (A.audio.heartbeat(1) !== false) problems.push('heartbeat() claimed to play with audio off');
  for (const i of [-1, 0, 1, 2, 3, 99, NaN, undefined]) {
    const sh = A.audio.deathBeatShape(i);
    if (!Number.isFinite(sh.f) || !Number.isFinite(sh.gain) || !Number.isFinite(sh.stretch)) {
      problems.push(`deathBeatShape(${String(i)}) -> ${JSON.stringify(sh)}`);
    }
  }
}

/* the timing table this file draws against and the one audio.js sounds against
 * must be the same object, not two that happen to agree today */
if (D.DEATH_BEAT_AT !== A.DEATH_BEAT_AT || D.DEATH_BEAT_MS !== A.DEATH_BEAT_MS) {
  problems.push('deathfx.js and audio.js are holding two different beat tables');
}

const snap = snapshot();
console.log('deathfx.js driven through every kit, colour, motion setting and canvas size');
console.log('  frames drawn      :', frames);
console.log('  ctx calls         :', snap.ctxCalls);
console.log('  drawImage calls   :', snap.drawCalls);
console.log('  canvases allocated:', snap.allocTotal, `(${snap.allocInLoop} inside a render loop)`);
console.log('  nullish/zero-size drawImage sources:', snap.nullImage);
console.log('  non-finite coordinates            :', snap.nonFinite);
console.log('  paint values that resolved to junk:', snap.badPaint);
for (const k of ['nullImage', 'nonFinite', 'badPaint', 'allocInLoop']) {
  for (const row of REC[k].slice(0, 8)) problems.push(`${k}: ${JSON.stringify(row)}`);
}
console.log('  beat table shared with audio.js   :', D.DEATH_BEAT_AT === A.DEATH_BEAT_AT ? 'same object' : 'TWO COPIES');
console.log('  stats             :', JSON.stringify(D.deathStats()));
console.log('');
if (problems.length) {
  console.log(`FAIL (${problems.length})`);
  for (const p of problems.slice(0, 40)) console.log('  - ' + p);
  process.exitCode = 1;
} else {
  console.log('PASS — no nullish sources, no non-finite coordinates, no undefined paints,');
  console.log('       nothing allocated inside a loop, and no report shape can leave the');
  console.log('       player without a line to read and a way out.');
}
