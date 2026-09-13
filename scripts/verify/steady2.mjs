import { installStub, REC, newCtx } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const B = await import('../../web/js/bosses.js');
const L = await import('../../web/js/lootart.js');
const SC = await import('../../web/js/battlescene.js');
const ctx = newCtx(192, 128);
const alloc = () => REC.allocTotal;

/* --- bosses: one boss, 600 frames of a real fight --- */
function bossFight(b, frames, withFlash) {
  const k = B.bossArtKey(b);
  for (let i = 0; i < frames; i++) {
    const t = i * 16;
    B.drawBoss(ctx, k, 184, 175, { colour: b.colour, time: t,
      flash: withFlash && i % 40 < 6 ? 0.9 : 0, seed: 3 });
  }
}
B.clearBossCache();
let a = alloc(); bossFight(V.bosses[0], 600, true);  const bossCold = alloc() - a;
a = alloc();     bossFight(V.bosses[0], 600, true);  const bossWarm = alloc() - a;
// all 14 bosses, cold then warm
B.clearBossCache();
a = alloc(); for (const b of V.bosses) bossFight(b, 120, true); const allCold = alloc() - a;
a = alloc(); for (const b of V.bosses) bossFight(b, 120, true); const allWarm = alloc() - a;

/* --- lootart: an inventory grid redrawn every frame --- */
const inv = V.items.slice(0, 40);
function invDraw(frames) {
  for (let i = 0; i < frames; i++) for (const it of inv) L.drawItem(ctx, it, 8, 8, { scale: 2, time: i * 16 });
}
L.clearLootArtCache();
a = alloc(); invDraw(120); const lootCold = alloc() - a;
a = alloc(); invDraw(120); const lootWarm = alloc() - a;
// loot drop + beam + burst + card, animated
L.clearLootArtCache();
const leg = V.items.find(i => i.rarity === 'LEGENDARY');
function dropAnim(frames) {
  for (let i = 0; i < frames; i++) {
    const t = i * 16;
    L.drawLootDrop(ctx, leg, 96, 100, { time: t });
    L.drawLootBeam(ctx, leg.rarity, 96, 100, { time: t });
    L.drawRarityBurst(ctx, leg.rarity, 96, 80, { time: t });
    L.drawLootCard(ctx, leg, 10, 10, { time: t });
  }
}
a = alloc(); dropAnim(240); const dropCold = alloc() - a;
a = alloc(); dropAnim(240); const dropWarm = alloc() - a;

/* --- battlescene: already measured, redo across all biomes --- */
const scenes = V.regions.map(r => SC.createScene({ biome: r.biome, palette: r.palette, key: r.id }));
a = alloc();
for (let i = 0; i < 200; i++) for (const s of scenes) { SC.drawScene(ctx, s, i * 0.016, null); SC.drawForeground(ctx, s, i * 0.016, null); }
const sceneDraw = alloc() - a;

console.log(JSON.stringify({
  bosses: { oneBossCold: bossCold, oneBossWarm: bossWarm, all14Cold: allCold, all14Warm: allWarm },
  lootart: { inventoryCold: lootCold, inventoryWarm: lootWarm, dropAnimCold: dropCold, dropAnimWarm: dropWarm },
  battlescene: { allocDuringDraw_3400frames: sceneDraw },
  verdict: {
    bosses: bossWarm === 0 && allWarm === 0 ? 'zero steady-state alloc' : 'ALLOCATES',
    lootart: lootWarm === 0 && dropWarm === 0 ? 'zero steady-state alloc' : 'ALLOCATES',
    battlescene: sceneDraw === 0 ? 'zero alloc in draw' : 'ALLOCATES',
  },
}, null, 1));
