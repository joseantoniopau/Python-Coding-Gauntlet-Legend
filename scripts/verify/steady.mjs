// Does spellfx reach a steady state with zero allocation, and does the
// whole-battle working set stay under CACHE_MAX (512)?
import { installStub, REC, newCtx } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const S  = await import('../../web/js/spellfx.js');
const FX = await import('../../web/js/fx.js');
const ctx = newCtx(192, 128);
const kinds = [...V.spells, ...Object.values(FX.DAMAGE_KIND)];

function play(kind, reduced) {
  const e = S.createEffect(kind, { x: 184, y: 175, reducedMotion: reduced, seed: 9 });
  for (let i = 0; i < Math.ceil(e.duration / 0.016) + 5; i++) { e.step(0.016); e.draw(ctx); }
  e.cancel();
}
const alloc = () => REC.allocTotal;

S.clearCache();
let a0 = alloc(); for (const k of kinds) { play(k, false); play(k, true); } const pass1 = alloc() - a0;
let a1 = alloc(); for (const k of kinds) { play(k, false); play(k, true); } const pass2 = alloc() - a1;
let a2 = alloc(); for (let r = 0; r < 5; r++) for (const k of kinds) { play(k, false); play(k, true); } const pass3to7 = alloc() - a2;

// Full-battle working set: warmCache everything, then measure cache size.
S.clearCache();
const warmed = S.warmCache(kinds);
let a3 = alloc(); for (const k of kinds) { play(k, false); play(k, true); } const afterWarm = alloc() - a3;

console.log(JSON.stringify({
  CACHE_MAX: 512,
  coldPass1_allocs: pass1,
  pass2_allocs: pass2,
  passes3to7_allocs: pass3to7,
  warmCache_entriesAdded: warmed,
  allocsAfterWarmCache: afterWarm,
  verdict: (pass2 === 0 && pass3to7 === 0) ? 'steady state reached, zero allocation' : 'STILL ALLOCATING',
  workingSetUnderCap: warmed < 512,
}, null, 1));
