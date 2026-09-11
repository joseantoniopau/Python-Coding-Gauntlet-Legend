import { installStub, REC, newCtx } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const L = await import('../../web/js/lootart.js');
const ctx = newCtx(320, 240);
const alloc = () => REC.allocTotal;

// Worst case the UI can actually produce: every item in the catalogue on screen,
// animated, redrawn every frame.
L.clearLootArtCache();
const draw = (frames) => { for (let i = 0; i < frames; i++) for (const it of V.items) L.drawItem(ctx, it, 8, 8, { scale: 2, time: i * 16 }); };
let a = alloc(); draw(200); const cold = alloc() - a;
a = alloc(); draw(200); const warm = alloc() - a;
a = alloc(); draw(400); const warm2 = alloc() - a;
console.log('full catalogue (85 items) animated:');
console.log('  frames 1-200 allocs:', cold);
console.log('  frames 201-400 allocs:', warm);
console.log('  frames 401-800 allocs:', warm2);
console.log('  stats:', JSON.stringify(L.lootArtStats()));
const total = L.itemFrameCount ? V.items.reduce((s, it) => s + L.itemFrameCount(it), 0) : 0;
console.log('  total item frames in catalogue:', total, '(gridCache/spriteCache cap is 512 each)');
console.log('  VERDICT:', warm === 0 && warm2 === 0 ? 'no thrash, working set fits' : 'THRASHING ABOVE CAP');
