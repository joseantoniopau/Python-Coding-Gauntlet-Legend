/* unmakingstub.mjs — the four failure classes a raster cannot see.
 *
 * raster.mjs answers "what got painted". stub.mjs answers the questions that
 * leave no pixels behind: a drawImage from a nullish or zero-size source, a
 * non-finite coordinate, a paint value that resolved to undefined (a missing
 * palette key renders transparent and silently), and a canvas allocated while a
 * render loop is running. The Unmaking is driven through both the real payload
 * and the authored fallback, at three canvas sizes, forwards and scrubbed, plus
 * the pathological dt values a real frame clock produces.
 *
 * Run on its own, or let unmaking.mjs fold it in — the two cannot share a
 * process, because they install different globals.
 */
import { installStub, REC, newCtx, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();
import { execFileSync } from 'child_process';

const ROOT = new URL('../../', import.meta.url).pathname;
const S = await import('../../web/js/spellfx.js');

let payloads = [{ label: 'fallback', opts: {} }];
try {
  const src = 'import json;from gauntlet import unmaking as m;'
    + 'print(json.dumps({"full":m.cinematic(),"short":m.cinematic(form=m.FORM_SHORT),'
    + '"reduced":m.cinematic(form=m.FORM_SHORT,motion=m.MOTION_REDUCED)}))';
  const py = JSON.parse(execFileSync('python3', ['-c', src], { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 24 }));
  payloads = payloads.concat([
    { label: 'cinematic FULL', opts: { cinematic: py.full } },
    { label: 'cinematic SHORT', opts: { cinematic: py.short } },
    { label: 'cinematic SHORT REDUCED', opts: { cinematic: py.reduced } },
  ]);
} catch (e) {
  payloads.push({ label: `python unavailable: ${String(e.message).split('\n')[0]}`, opts: {} });
}

const problems = [];
let frames = 0;
const sizes = [[320, 180], [960, 540], [240, 135]];

S.warmUnmaking({});
for (const { label, opts } of payloads) {
  setWhere(`${label} warm`);
  S.warmUnmaking(opts);
  for (const [w, h] of sizes) {
    const ctx = newCtx(w, h);
    const u = S.createUnmaking(opts);
    setWhere(`${label} ${w}x${h}`);
    enterLoop(`${label} ${w}x${h}`);
    /* scrubbed: every frame is a pure function of t, so this covers the whole
     * timeline without playing 115 seconds of it */
    for (let i = 0; i <= 400; i++) { u.seek((u.total * i) / 400); u.draw(ctx, w, h); frames++; }
    /* and played, the way a host drives it */
    u.begin(opts);
    for (let i = 0; i < 400 && u.active; i++) { u.update(0.016); u.draw(ctx, w, h); frames++; }
    exitLoop();
    u.cancel();
  }
}

/* dt values a real frame clock produces, including the ones it should not */
{
  const ctx = newCtx(320, 180);
  const u = S.createUnmaking({});
  u.begin({});
  setWhere('pathological dt');
  for (const dt of [0, -1, NaN, Infinity, 1e6, 100, 0.016]) {
    try { u.update(dt); u.draw(ctx, 320, 180); frames++; }
    catch (e) { problems.push(`update(${dt}) threw ${e.message}`); }
  }
  /* degenerate canvases and a missing context */
  for (const [w, h] of [[0, 0], [1, 1], [-5, 20]]) {
    try { u.draw(newCtx(Math.max(1, w), Math.max(1, h)), w, h); }
    catch (e) { problems.push(`draw(${w}x${h}) threw ${e.message}`); }
  }
  try { u.draw(null, 320, 180); } catch (e) { problems.push(`draw(null) threw ${e.message}`); }
}

/* a payload that is wrong in every way a server can be wrong */
for (const bad of [null, {}, { acts: [] }, { acts: [{ id: 'TAKE' }], beats: [{}] },
  { beats: [{ crutch: 'NOT_A_CRUTCH', at: 1 }] }, { spell: { phrase: 42 } }]) {
  try {
    const u = S.createUnmaking({ cinematic: bad });
    const ctx = newCtx(320, 180);
    setWhere('malformed payload');
    for (let i = 0; i <= 20; i++) { u.seek((u.total * i) / 20); u.draw(ctx, 320, 180); frames++; }
  } catch (e) { problems.push(`malformed payload threw ${e.message}`); }
}

/* stub.mjs's FINITE_ARGS declares `fillText: 3` and then checks args 0..2 for
 * finiteness — but argument 0 of fillText is the STRING. Every text draw in the
 * codebase trips it, including transform.js's chrome lettering. It is a defect
 * in the harness, not in the art, so those entries are separated out here and
 * counted rather than swept up: if anything else ever appears in that list it
 * must still fail. */
const textArg = (e) => e.op === 'fillText' && e.argIndex === 0;
const realNonFinite = REC.nonFinite.filter((e) => !textArg(e));
const stubTextArg = REC.nonFinite.length - realNonFinite.length;

const snap = snapshot();
const out = {
  payloads: payloads.map((p) => p.label),
  sizes: sizes.map(([w, h]) => `${w}x${h}`),
  frames,
  problems,
  snapshot: snap,
  nonFiniteReal: realNonFinite.length,
  nonFiniteStubTextArgFalsePositives: stubTextArg,
  stubDefect: 'stub.mjs FINITE_ARGS.fillText checks arg 0, which is the string. '
    + 'Harness defect, not an art defect; counted above and excluded from the verdict.',
  nullImage: REC.nullImage.slice(0, 5),
  nonFinite: realNonFinite.slice(0, 5),
  badPaint: REC.badPaint.slice(0, 5),
  allocInLoop: REC.allocInLoop.slice(0, 5),
};
out.VERDICT = (problems.length || snap.nullImage || realNonFinite.length
  || snap.badPaint || snap.allocInLoop) ? 'FAIL' : 'PASS';
console.log(JSON.stringify(out, null, 1));
process.exitCode = out.VERDICT === 'PASS' ? 0 : 1;
