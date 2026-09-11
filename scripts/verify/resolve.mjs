import { installStub } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const B = await import('../../web/js/bosses.js');
console.log('id'.padEnd(22), 'sprite'.padEnd(14), '-> art');
const used = {};
for (const b of V.bosses) { const k = B.bossArtKey(b); (used[k] ??= []).push(b.id); console.log(b.id.padEnd(22), b.sprite.padEnd(14), '->', k); }
console.log('\narchetypes with no boss:', B.BOSS_ARCHETYPES.filter(a => !used[a]));
console.log('archetypes shared by >1 boss:');
for (const [k, v] of Object.entries(used)) if (v.length > 1) console.log('  ', k, v);
