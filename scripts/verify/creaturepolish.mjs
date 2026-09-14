/* Real raster checks for the creature polish pass. Optional --out <directory>
 * writes contact sheets for human inspection; pixel counts do not grade art. */
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { deflateSync } from 'node:zlib';
import { installRaster, colourCount, frameHash, pixelDiff } from './raster.mjs';
installRaster();
const S = await import('../../web/js/sprites.js');
const M = await import('../../web/js/monsterart.js');
const B = await import('../../web/js/bosses.js');

function crop(img, x0, y0, width, height) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const src = ((y + y0) * img.width + x + x0) * 4;
    data.set(img.data.subarray(src, src + 4), (y * width + x) * 4);
  }
  return { width, height, data };
}
let portraits = 0, monsters = 0, bosses = 0, maxColours = 0;
function inspect(img, label, w, h) {
  assert.equal(img.width, w, `${label} width`); assert.equal(img.height, h, `${label} height`);
  const colours = colourCount(img); maxColours = Math.max(maxColours, colours);
  assert.ok(colours >= 3 && colours <= 15, `${label}: ${colours} colours (3..15)`);
}
// The lower face excludes hats, costumes and the expressive eye strips. The
// former shared anatomy produced byte-identical crops for every human mentor.
const faces = new Map();
let nearestFace = Infinity;
for (const key of S.PORTRAIT_KEYS) {
  if (!['automaton_small', 'interviewer'].includes(key)) {
    const face = crop(S.portrait(key), 5, 10, 14, 8);
    for (const [other, previous] of faces) {
      const delta = pixelDiff(face, previous); nearestFace = Math.min(nearestFace, delta);
      assert.ok(delta >= 12, `${key}/${other}: lower face differs by only ${delta} pixels`);
    }
    faces.set(key, face);
  }
  for (const emote of S.EMOTE_KEYS) for (let frame = 0; frame < 2; frame++) {
    const img = S.portraitEmote(key, emote, frame);
    inspect(img, `${key}/${emote}/${frame}`, 24, 24); portraits++;
    assert.equal(img, S.portraitEmote(key, emote, frame), 'portrait warm cache');
  }
  for (const emote of S.EMOTE_KEYS) {
    assert.ok(pixelDiff(...S.portraitFrames(key, emote)) > 0, `${key}/${emote} has no acting event`);
  }
}
for (const [alias, key] of Object.entries(S.PORTRAIT_ALIAS)) {
  assert.equal(frameHash(S.portrait(alias)), frameHash(S.portrait(key)), `${alias} alias`);
}
for (const key of M.MONSTER_KEYS) for (const pose of ['idle', 'walk']) for (let frame = 0; frame < 4; frame++) {
  const img = M.monsterFrame(key, frame, { pose });
  inspect(img, `${key}/${pose}/${frame}`, M.monsterSize(key), M.monsterSize(key)); monsters++;
  const before = frameHash(img); M.clearMonsterCache();
  assert.equal(frameHash(M.monsterFrame(key, frame, { pose })), before, `${key} cold rebuild`);
}
// A living hydra is one connected animal. This catches a neck root detached
// by the independently posed head at an extreme, even though every call and
// colour count is valid. Diagonal pixel joins count as connected.
function components(img) {
  const seen = new Set(), groups = [];
  for (let i = 0; i < img.width * img.height; i++) {
    if (!img.data[i * 4 + 3] || seen.has(i)) continue;
    const pending = [i]; seen.add(i); let count = 0;
    while (pending.length) {
      const at = pending.pop(); count++;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const x = at % img.width + dx, y = Math.floor(at / img.width) + dy;
        const next = y * img.width + x;
        if (x < 0 || y < 0 || x >= img.width || y >= img.height || seen.has(next) || !img.data[next * 4 + 3]) continue;
        seen.add(next); pending.push(next);
      }
    }
    groups.push(count);
  }
  return groups.sort((a, b) => b - a);
}
for (let frame = 0; frame < 5; frame++) for (let beat = 0; beat < 6; beat++) {
  const img = B.bossSprite('hydra', undefined, frame, { phase: 0, beat });
  assert.equal(components(img).length, 1, `hydra neck detached at frame ${frame}, beat ${beat}`);
}
assert.equal(frameHash(S.portrait('__unknown_portrait__')), frameHash(S.portrait('scholar')), 'unknown mentor fallback');

for (const key of B.BOSS_ARCHETYPES) for (let phase = 0; phase < B.BOSS_PHASE_COUNT; phase++) {
  const size = B.bossSize(key), mapSize = B.bossMapSize(key);
  for (let frame = 0; frame < B.BOSS_FRAME_COUNT; frame++) {
    const img = B.bossSprite(key, undefined, frame, { phase });
    inspect(img, `${key}/${phase}/${frame}`, size.w, size.h); bosses++;
    const before = frameHash(img); B.clearBossCache();
    assert.equal(frameHash(B.bossSprite(key, undefined, frame, { phase })), before, `${key} cold rebuild`);
    inspect(B.bossMapSprite(key, undefined, frame, { phase }), `${key} map`, mapSize.w, mapSize.h);
  }
}
const report = { portraits, humanFaces: faces.size, nearestFace, monsters, bosses, maxColours, note: 'Raster contracts passed. Visual quality requires contact-sheet and in-game review.' };
console.log(JSON.stringify(report, null, 2));

// PNG encoding is deliberately local and dependency-free. The pixels come from
// the shipped sprite entry points; there is no second drawing implementation.
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
  const index = { report,
    portraits: sheet(S.PORTRAIT_KEYS, k => S.portrait(k), 7, 120, 112, 4, join(dir, 'portraits.png')),
    monsters: sheet(M.MONSTER_KEYS, k => M.monsterFrame(k), 8, 160, 160, 3, join(dir, 'monsters.png')),
    bosses: sheet(B.BOSS_ARCHETYPES, k => B.bossSprite(k), 4, 300, 280, 2, join(dir, 'bosses.png')),
    hydraPoses: sheet(Array.from({ length: 30 }, (_, i) => `${Math.floor(i / 5)}/${i % 5}`), k => { const [phase, frame] = k.split('/').map(Number); return B.bossSprite('hydra', undefined, frame, { phase }); }, 5, 216, 152, 2, join(dir, 'hydra-poses.png')),
    dragonPoses: sheet(Array.from({ length: 30 }, (_, i) => `${Math.floor(i / 5)}/${i % 5}`), k => { const [phase, frame] = k.split('/').map(Number); return B.bossSprite('dragon', undefined, frame, { phase }); }, 5, 216, 152, 2, join(dir, 'dragon-poses.png')),
    demonPoses: sheet(Array.from({ length: 30 }, (_, i) => `${Math.floor(i / 5)}/${i % 5}`), k => { const [phase, frame] = k.split('/').map(Number); return B.bossSprite('demon', undefined, frame, { phase }); }, 5, 152, 152, 2, join(dir, 'demon-poses.png')),
    behemothPoses: sheet(Array.from({ length: 30 }, (_, i) => `${Math.floor(i / 5)}/${i % 5}`), k => { const [phase, frame] = k.split('/').map(Number); return B.bossSprite('behemoth', undefined, frame, { phase }); }, 5, 152, 152, 2, join(dir, 'behemoth-poses.png')),
    bossFinalPhases: sheet(B.BOSS_ARCHETYPES, k => B.bossSprite(k, undefined, 0, { phase: 5 }), 4, 300, 280, 2, join(dir, 'boss-final-phases.png')),
    emotes: sheet(S.PORTRAIT_KEYS.flatMap(k => S.EMOTE_KEYS.map(e => `${k}/${e}`)), k => S.portraitEmote(...k.split('/')), 7, 104, 112, 4, join(dir, 'emotes.png')),
  };
  writeFileSync(join(dir, 'index.json'), JSON.stringify(index, null, 2) + '\n');
  console.log(`Contact sheets: ${dir}`);
}
