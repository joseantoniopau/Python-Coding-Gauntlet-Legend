import { installStub, REC, newCtx, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const S  = await import('../../web/js/spellfx.js');
const FX = await import('../../web/js/fx.js');
const ctx = newCtx(192, 128);

const e0 = S.createEffect('ORACLE', {});
console.log('effect shape:', Object.keys(e0).join(','));
console.log('methods:', ['step','draw','cancel','_draw'].map(m => m + '=' + typeof e0[m]).join(' '));

const probs = [];
const allKinds = [...V.spells, ...Object.values(FX.DAMAGE_KIND)];
let frames = 0;
for (const kind of allKinds) {
  for (const reduced of [false, true]) {
    const e = S.createEffect(kind, { x: 136, y: 100, reducedMotion: reduced, seed: 9 });
    if (!e) { probs.push('null effect ' + kind); continue; }
    const dur = e.duration;
    if (!Number.isFinite(dur) || dur <= 0) probs.push(`${kind} bad duration ${dur}`);
    setWhere(`spell ${kind} reduced=${reduced}`);
    enterLoop(`spell ${kind}`);
    // Drive it exactly as BattleFX does, past the end, at 60fps.
    for (let i = 0; i < Math.ceil(dur / 0.016) + 30; i++) { e.step(0.016); e.draw(ctx); frames++; }
    exitLoop();
    e.cancel();
    // and through the fx.js adapter
    const a = S.toFxEffect(S.createEffect(kind, { x: 136, y: 100, reducedMotion: reduced }));
    setWhere(`adapter ${kind}`);
    enterLoop(`adapter ${kind}`);
    for (let t = 0; t <= a.dur + 0.5; t += 0.016) { a.t = t; a.draw(ctx); frames++; }
    exitLoop();
  }
}
// pathological: zero dt, huge dt, negative dt
for (const kind of ['PHOENIX', 'crit']) {
  const e = S.createEffect(kind, { x: 100, y: 100 });
  setWhere('pathological ' + kind);
  for (const dt of [0, -1, 1e6, NaN, 100]) { try { e.step(dt); e.draw(ctx); } catch (err) { probs.push(`${kind} step(${dt}) threw ${err.message}`); } }
}
console.log(JSON.stringify({ frames, problems: probs, snap: snapshot(),
  nullImage: REC.nullImage.slice(0,8), nonFinite: REC.nonFinite.slice(0,8), badPaint: REC.badPaint.slice(0,8),
  allocInLoop: REC.allocInLoop.length, allocInLoopDetail: REC.allocInLoop.slice(0,5) }, null, 1));
