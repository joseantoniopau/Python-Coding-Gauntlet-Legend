// Determinism + reducedMotion. We cannot read pixels from the stub, so we
// fingerprint the ORDER and ARGUMENTS of every ctx call instead. Same key must
// produce an identical call trace; reducedMotion must produce a trace that does
// not vary with time.
import { installStub } from './stub.mjs';
installStub();
import fs from 'fs';
import crypto from 'crypto';

const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const B = await import('../../web/js/bosses.js');
const L = await import('../../web/js/lootart.js');
const S = await import('../../web/js/spellfx.js');
const SC = await import('../../web/js/battlescene.js');

// A recording context: every call and paint change appended to a log.
function recCtx() {
  const log = [];
  const h = {
    canvas: { width: 640, height: 360 },
    _f: '#000', _s: '#000',
    globalAlpha: 1, globalCompositeOperation: 'source-over', lineWidth: 1,
    imageSmoothingEnabled: false, font: '8px m', textAlign: 'left', textBaseline: 'top',
    lineCap: 'butt', lineJoin: 'miter', shadowBlur: 0, shadowColor: '#000',
    shadowOffsetX: 0, shadowOffsetY: 0, filter: 'none', miterLimit: 10, lineDashOffset: 0,
    get fillStyle() { return this._f; }, set fillStyle(v) { this._f = v; log.push('F' + v); },
    get strokeStyle() { return this._s; }, set strokeStyle(v) { this._s = v; log.push('S' + v); },
    drawImage(img, ...r) { log.push('I' + (img ? img.width + 'x' + img.height : 'null') + ':' + r.map(n => Math.round(n * 100) / 100).join(',')); },
    createLinearGradient() { return { addColorStop(o, c) { log.push('G' + o + c); } }; },
    createRadialGradient() { return { addColorStop(o, c) { log.push('G' + o + c); } }; },
    createPattern() { return {}; },
    measureText(t) { return { width: String(t).length * 6 }; },
    getImageData(x, y, w, h) { const W = Math.max(1, w | 0), H = Math.max(1, h | 0); return { width: W, height: H, data: new Uint8ClampedArray(W * H * 4) }; },
    putImageData() { log.push('P'); },
    log,
  };
  for (const m of ['beginPath','closePath','fill','stroke','save','restore','clip','moveTo','lineTo',
    'arc','arcTo','ellipse','rect','roundRect','quadraticCurveTo','bezierCurveTo','translate','scale',
    'rotate','transform','setTransform','resetTransform','fillRect','clearRect','strokeRect','fillText',
    'strokeText','setLineDash','getLineDash']) {
    h[m] = (...a) => log.push(m[0] + m.slice(-2) + a.map(n => typeof n === 'number' ? Math.round(n * 100) / 100 : String(n)).join(','));
  }
  return h;
}
const sig = (c) => crypto.createHash('sha1').update(c.log.join('|')).digest('hex').slice(0, 12);

function trace(fn) { const c = recCtx(); fn(c); return sig(c); }

const bad = [];

/* --- determinism: build twice from a cold cache, compare --- */
function coldTrace(fn) {
  B.clearBossCache(); L.clearLootArtCache(); S.clearCache();
  return trace(fn);
}
// bosses
for (const b of V.bosses) {
  const a = coldTrace(c => B.drawBoss(c, B.bossArtKey(b), 320, 300, { colour: b.colour, time: 1234, seed: 5 }));
  const z = coldTrace(c => B.drawBoss(c, B.bossArtKey(b), 320, 300, { colour: b.colour, time: 1234, seed: 5 }));
  if (a !== z) bad.push(`boss ${b.id} non-deterministic ${a} vs ${z}`);
}
// items
for (const it of V.items) {
  const a = coldTrace(c => L.drawItem(c, it, 10, 10, { scale: 2, time: 800 }));
  const z = coldTrace(c => L.drawItem(c, it, 10, 10, { scale: 2, time: 800 }));
  if (a !== z) bad.push(`item ${it.id} non-deterministic`);
}
// scenes (keyed)
for (const r of V.regions) {
  const mk = () => SC.createScene({ biome: r.biome, palette: r.palette, key: r.id });
  const a = trace(c => SC.drawScene(c, mk(), 2.5, null));
  const z = trace(c => SC.drawScene(c, mk(), 2.5, null));
  if (a !== z) bad.push(`scene ${r.id} non-deterministic`);
}
// spells
for (const sp of V.spells) {
  const a = coldTrace(c => { const e = S.createEffect(sp, { x: 100, y: 100, seed: 4 }); e && e.draw && e.draw(c, 0.4); });
  const z = coldTrace(c => { const e = S.createEffect(sp, { x: 100, y: 100, seed: 4 }); e && e.draw && e.draw(c, 0.4); });
  if (a !== z) bad.push(`spell ${sp} non-deterministic`);
}

/* --- reducedMotion: trace must not vary with time --- */
const rmBad = [];
for (const b of V.bosses.slice(0, 6)) {
  const t1 = trace(c => B.drawBoss(c, B.bossArtKey(b), 320, 300, { colour: b.colour, time: 0, reducedMotion: true }));
  const t2 = trace(c => B.drawBoss(c, B.bossArtKey(b), 320, 300, { colour: b.colour, time: 9999, reducedMotion: true }));
  if (t1 !== t2) rmBad.push(`boss ${b.id} moves under reducedMotion`);
}
for (const r of V.regions) {
  const s = SC.createScene({ biome: r.biome, palette: r.palette, key: r.id, reducedMotion: true });
  const t1 = trace(c => { SC.drawScene(c, s, 0, null); SC.drawForeground(c, s, 0, null); });
  const t2 = trace(c => { SC.drawScene(c, s, 12.75, null); SC.drawForeground(c, s, 12.75, null); });
  if (t1 !== t2) rmBad.push(`scene ${r.biome} moves under reducedMotion`);
}
{
  const cam = SC.createCamera({ reducedMotion: true });
  for (let i = 0; i < 60; i++) cam.update(0.016);
  if (Math.abs(cam.ox) > 0.001 || Math.abs(cam.oy) > 0.001) rmBad.push(`camera drifts under reducedMotion ox=${cam.ox} oy=${cam.oy}`);
}
{
  L.setReducedMotion(true);
  const it = V.items.find(i => i.rarity === 'LEGENDARY');
  const t1 = trace(c => L.drawItem(c, it, 0, 0, { scale: 2, time: 0 }));
  const t2 = trace(c => L.drawItem(c, it, 0, 0, { scale: 2, time: 5000 }));
  if (t1 !== t2) rmBad.push('legendary item animates under reducedMotion');
  L.setReducedMotion(false);
}

console.log(JSON.stringify({ determinism: { failures: bad.length, detail: bad.slice(0, 10) },
  reducedMotion: { failures: rmBad.length, detail: rmBad.slice(0, 10) } }, null, 1));
