/* Real rasters, including supported element overrides on every standalone rig.
 * No game server, save file, or screenshots are read or written. */
import assert from 'node:assert/strict';
import { installRaster, colourCount, frameHash } from './raster.mjs';
installRaster();
const B = await import('../../web/js/bosses.js');
const ids = [...new Set([...B.BOSS_ARCHETYPES, ...Object.keys(B.BOSS_ART_FOR_ID), 'the_last_interpreter'])];
const elements = ['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID', 'NEUTRAL'];
let samples = 0, maximum = 0;
for (const id of ids) for (const element of elements) {
  for (let phase = 0; phase < B.BOSS_PHASE_COUNT; phase++) {
    for (let frame = 0; frame < B.BOSS_FRAME_COUNT; frame++) {
      const forms = [B.bossSprite(id, undefined, frame, { phase, element })];
      if (frame < 2) forms.push(B.bossMapSprite(id, undefined, frame, { phase, element }));
      for (const canvas of forms) {
        const colours = colourCount(canvas);
        assert.ok(colours > 1 && colours <= 15,
          `${id}, ${element}, phase ${phase}, frame ${frame}, ${canvas.width}x${canvas.height}: ${colours} colours`);
        maximum = Math.max(maximum, colours); samples++;
      }
    }
  }
}
// The caller may supply a custom base tint. The same finished-grid rule applies.
for (const colour of ['#000000', '#ffffff', '#e04cf7', '#336699']) {
  for (const element of elements) {
    const options = { element, phase: 5 };
    const first = B.bossSprite('the_interviewer', colour, 0, options);
    const hash = frameHash(first);
    assert.ok(colourCount(first) <= 15);
    assert.equal(B.bossSprite('the_interviewer', colour, 0, options), first, 'cached sprite is reused');
    B.clearBossCache();
    assert.equal(frameHash(B.bossSprite('the_interviewer', colour, 0, options)), hash, 'cold cache is deterministic');
    samples++;
  }
}
console.log(JSON.stringify({ ok: true, identities: ids.length, elements: elements.length,
  phases: B.BOSS_PHASE_COUNT, samples, maximum, cachedReuse: true, coldDeterminism: true }));
