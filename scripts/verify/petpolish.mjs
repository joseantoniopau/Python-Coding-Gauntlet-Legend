/* Companion raster contracts and contact sheets, from the shipped renderer.
 * Run with --out <directory> for visual review at native and 4x pixel scale. */
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { deflateSync } from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { installRaster, colourCount, frameHash, pixelDiff } from './raster.mjs';
installRaster();
const P = await import('../../web/js/petart.js');
const roster = JSON.parse(execFileSync('python3', ['-c',
  'import json;from gauntlet import pets,regalia;print(json.dumps(dict(colours=sorted(set(p["colour"] for p in pets.catalogue())),pieces=[dict(id=r.id,colour=r.colour) for r in regalia.REGALIA])))'],
  { cwd: fileURLToPath(new URL('../..', import.meta.url)), encoding: 'utf8' }));
const pieces = new Map(roster.pieces.map(r => [r.id, r]));
// Default materials plus every colour actually shipped by the live roster.
const colours = ['', ...roster.colours];
let frames = 0, maxColours = 0;
const stats = P.petArtStats();
assert.equal(stats.rows.find(r => r.animal === 'tortoise').shellPixelsMovedPerCycle, 0, 'tortoise shell bends during gait');
for (const key of P.PET_ANIMALS) {
  for (const colour of colours) for (const tier of P.PET_TIERS) for (const facing of P.PET_FACINGS) {
    for (const pose of ['walk', 'idle']) for (let frame = 0; frame < 4; frame++) {
      const opts = { tier, pose, colour }, img = P.petFrame(key, facing, frame, opts);
      assert.equal(img.width, 16); assert.equal(img.height, 16);
      assert.equal(img, P.petFrame(key, facing, frame, opts), `${key} warm cache`);
      const colours = colourCount(img); maxColours = Math.max(maxColours, colours); frames++;
      assert.ok(colours <= 15, `${key}/${tier}/${facing}/${pose}/${frame}: ${colours} colours`);
      const hash = frameHash(img); P.clearPetCache();
      assert.equal(frameHash(P.petFrame(key, facing, frame, opts)), hash, `${key} cold rebuild`);
      // Every slot is exercised on every body plan: a crest and a real worn
      // object must share the 15-colour budget, including negative-space poses.
      for (const id of P.PET_REGALIA_IDS) {
        const regalia = pieces.get(id) || id;
        const worn = P.petFrame(key, facing, frame, { ...opts, regalia });
        const n = colourCount(worn); maxColours = Math.max(maxColours, n); frames++;
        assert.ok(n <= 15, `${key}/${tier}/${facing}/${pose}/${frame}/${id}/${colour}: ${n} colours`);
      }
    }
  }
  for (const facing of P.PET_FACINGS) {
    const dead = P.petFrame(key, facing, 0, { dead: true });
    assert.ok(colourCount(dead) <= 5, `${key} fainted palette`);
    assert.ok(pixelDiff(dead, P.petFrame(key, facing, 0)) > 20, `${key} fainted pose read`);
  }
}
const report = { animals: P.PET_ANIMALS.length, tiers: P.PET_TIERS.length, rosterColours: roster.colours.length, frames, maxColours,
  note: 'Native raster, palette, cache and fainted-state contracts. Human review still judges visual quality.' };
console.log(JSON.stringify(report, null, 2));
function png(width, height, data, filename) {
  const crc = bytes => { let c = 0xffffffff; for (const v of bytes) { c ^= v; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; } return (c ^ 0xffffffff) >>> 0; };
  const chunk = (name, data) => { const type = Buffer.from(name), head = Buffer.alloc(4), tail = Buffer.alloc(4); head.writeUInt32BE(data.length); tail.writeUInt32BE(crc(Buffer.concat([type, data]))); return Buffer.concat([head, type, data, tail]); };
  const head = Buffer.alloc(13); head.writeUInt32BE(width); head.writeUInt32BE(height, 4); head[8] = 8; head[9] = 6;
  const rows = Buffer.alloc(height * (width * 4 + 1)), pixels = Buffer.from(data);
  for (let y = 0; y < height; y++) pixels.copy(rows, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  writeFileSync(filename, Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', head), chunk('IDAT', deflateSync(rows)), chunk('IEND', Buffer.alloc(0))]));
}
function sheet(keys, draw, columns, cellW, cellH, scale, filename) {
  const width = columns * cellW, height = Math.ceil(keys.length / columns) * cellH;
  const data = new Uint8Array(width * height * 4);
  for (let i = 0; i < width * height; i++) data.set([24, 25, 36, 255], i * 4);
  keys.forEach((key, index) => {
    const img = draw(key), ox = index % columns * cellW + Math.floor((cellW - img.width * scale) / 2);
    const oy = Math.floor(index / columns) * cellH + cellH - img.height * scale - 8;
    for (let y = 0; y < img.height; y++) for (let x = 0; x < img.width; x++) {
      const src = (y * img.width + x) * 4; if (!img.data[src + 3]) continue;
      for (let sy = 0; sy < scale; sy++) for (let sx = 0; sx < scale; sx++) {
        data.set(img.data.subarray(src, src + 4), ((oy + y * scale + sy) * width + ox + x * scale + sx) * 4);
      }
    }
  });
  png(width, height, data, filename);
  return keys.map((key, index) => ({ key, row: Math.floor(index / columns) + 1, column: index % columns + 1 }));
}
const outAt = process.argv.indexOf('--out');
if (outAt >= 0) {
  assert.ok(process.argv[outAt + 1], '--out needs a directory');
  const dir = resolve(process.argv[outAt + 1]); mkdirSync(dir, { recursive: true });
  const tierKeys = P.PET_ANIMALS.flatMap(k => P.PET_TIERS.map(tier => `${k}/${tier}`));
  const viewKeys = P.PET_ANIMALS.flatMap(k => P.PET_FACINGS.map(facing => `${k}/${facing}`));
  const drawTier = k => { const [animal, tier] = k.split('/'); return P.petFrame(animal, 'right', 0, { tier, pose: 'idle' }); };
  const drawView = k => { const [animal, facing] = k.split('/'); return P.petFrame(animal, facing, 0, { tier: 'COMMON', pose: 'idle' }); };
  const index = { report,
    tiers: sheet(tierKeys, drawTier, 7, 80, 80, 4, join(dir, 'pet-tiers.png')),
    facings: sheet(viewKeys, drawView, 4, 80, 80, 4, join(dir, 'pet-facings.png')),
    nativeTiers: sheet(tierKeys, drawTier, 7, 32, 32, 1, join(dir, 'pet-native.png')),
    gait: sheet(P.PET_ANIMALS.flatMap(k => ['walk', 'idle'].flatMap(pose => [0,1,2,3].map(f => `${k}/${pose}/${f}`))), k => {
      const [animal, pose, f] = k.split('/'); return P.petFrame(animal, 'right', Number(f), { pose, tier: 'COMMON' });
    }, 8, 80, 80, 4, join(dir, 'pet-motion.png')),
  };
  writeFileSync(join(dir, 'index.json'), JSON.stringify(index, null, 2) + '\n');
  console.log(`Contact sheets: ${dir}`);
}
