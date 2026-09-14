/* Regional architecture contracts. Pixels come from the real tile painters;
 * this does not replace a browser review of the composed map. */
import assert from 'node:assert/strict';
import { installRaster, colourCount, frameHash, silhouetteDiff } from './raster.mjs';
installRaster();
const { buildingSprite, terrainSet, createScene, TERRAIN, isSolid } =
  await import('../../web/js/tiles.js');

const biomes = ['village', 'grass', 'forest', 'deepforest', 'canopy', 'swamp',
  'cave', 'mine', 'mountain', 'highland', 'citadel', 'ruins', 'wastes',
  'dungeon', 'tower', 'arena', 'castle'];
let samples = 0, maxColours = 0;
for (const biome of biomes) for (const palette of ['spring', 'slate', 'void']) {
  for (let variant = 0; variant < 4; variant++) {
    const stages = [];
    for (let tier = 0; tier < 4; tier++) {
      const sprite = buildingSprite(palette, 1709, tier, variant, biome);
      assert.equal(sprite.width, 40, `${biome}: width changes collision alignment`);
      assert.equal(sprite.height, 36, `${biome}: height changes draw anchor`);
      assert.equal(sprite.footY, 34, `${biome}: ground anchor moved`);
      const count = colourCount(sprite);
      assert.ok(count <= 15, `${biome}/${variant}/${tier}: ${count} colours`);
      maxColours = Math.max(maxColours, count);
      assert.equal(frameHash(sprite), frameHash(buildingSprite(palette, 1709, tier, variant, biome)),
        `${biome}/${variant}/${tier}: non-deterministic building`);
      for (const [x, y] of sprite.windows) {
        assert.ok(x >= 0 && x < 40 && y >= 0 && y < 34, 'window light anchor outside facade');
        const rgba = Array.from(sprite.data.slice((y * 40 + x) * 4, (y * 40 + x) * 4 + 4));
        assert.deepEqual(rgba, [255, 244, 200, 255], `${biome}/${variant}/${tier}: light anchor is not a lit window`);
      }
      if (tier < 2) assert.equal(sprite.windows.length, 0, 'abandoned building emits occupied window lights');
      else assert.ok(sprite.windows.length > 0, 'restored building has no occupied windows');
      stages.push(frameHash(sprite)); samples++;
    }
    assert.equal(new Set(stages).size, 4, `${biome}/${variant}: restoration stages repeat`);
  }
}

// Same seed and palette: geometry must carry place, without relying on tint.
for (const [a, b] of [['village', 'citadel'], ['forest', 'mine'], ['mountain', 'swamp'],
  ['castle', 'tower'], ['ruins', 'highland'], ['cave', 'canopy'], ['arena', 'wastes']]) {
  assert.ok(silhouetteDiff(buildingSprite('spring', 43, 3, 0, a),
    buildingSprite('spring', 43, 3, 0, b)) >= 30, `${a}/${b}: architecture is only a palette swap`);
}

// Exercise the actual scene path, its caller's biome, cached tiles and tier cap.
const grid = Array.from({ length: 8 }, () => Array(10).fill(TERRAIN.GRASS));
grid[3][3] = grid[3][4] = TERRAIN.BUILDING;
const before = JSON.stringify(grid);
for (const biome of biomes) {
  const opts = { regionId: 'regional-art-contract', palette: 'spring', biome, tier: 3,
    grid, decorDensity: 0, floraDensity: 0, detailDensity: 0 };
  const scene = createScene(opts);
  assert.equal(scene.set, terrainSet(opts.regionId, opts.palette, opts.tier, biome), 'tile cache miss');
  const building = scene.objects.find(o => o.kind === 'building');
  assert.ok(building, `${biome}: no building in scene`);
  assert.equal(frameHash(building.img), frameHash(buildingSprite(scene.set.P.raw,
    scene.set.seed + 263, 3, building.variant, biome)), `${biome}: scene dropped biome`);
  const damaged = terrainSet(`regional-damaged-${biome}`, 'spring', 1, biome);
  assert.equal(frameHash(damaged.building[3][0]), frameHash(damaged.building[1][0]), 'tier cap lost');
}
assert.equal(JSON.stringify(grid), before, 'art pass mutated terrain grid');
assert.equal(isSolid(TERRAIN.BUILDING), true);
assert.equal(isSolid(TERRAIN.GRASS), false);
// Quiet terrain allows characters and interactables to carry the contrast.
// Measure the raster, including blades/chips above the shared mottle painter.
const groundQuietness = {};
for (const biome of ['village', 'grass', 'forest', 'cave', 'mountain', 'wastes']) {
  const { ground } = terrainSet('art-density', 'spring', 3, biome);
  let dominant = 0, isolated = 0;
  for (const canvas of ground) {
    const colours = new Map();
    const colour = (x, y) => {
      const i = (y * 16 + x) * 4;
      assert.equal(canvas.data[i + 3], 255, `${biome}: transparent terrain`);
      return (canvas.data[i] << 16) | (canvas.data[i + 1] << 8) | canvas.data[i + 2];
    };
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const c = colour(x, y);
      colours.set(c, (colours.get(c) || 0) + 1);
      if (x > 0 && y > 0 && x < 15 && y < 15 &&
        [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].every(([xx, yy]) => colour(xx, yy) !== c)) isolated++;
    }
    dominant += Math.max(...colours.values()) / 256;
  }
  dominant /= ground.length;
  assert.ok(dominant >= 0.70, `${biome}: detail covers the broad ground plane`);
  assert.ok(isolated < 60, `${biome}: isolated high-frequency speckles returned`);
  groundQuietness[biome] = { dominant: +dominant.toFixed(3), isolated };
}
console.log(JSON.stringify({ samples, maxColours, biomes: biomes.length,
  geometryPairs: 7, anchors: '40x36 / footY 34', deterministic: true, sceneWiring: true,
  groundQuietness }, null, 2));
