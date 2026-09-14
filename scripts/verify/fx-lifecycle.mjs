/* Offline: real sprite pixels for dissolve sampling, then an instrumented
 * render clock for promise completion. No server or game save is involved. */
import assert from 'node:assert/strict';
import { installRaster } from './raster.mjs';
import { installStub, REC } from './stub.mjs';
installRaster();
const B = await import('../../web/js/bosses.js');
const { BattleFX } = await import('../../web/js/fx.js');
let dissolves = 0, maxDissolveParticles = 0;
for (const id of B.BOSS_ARCHETYPES) for (let phase = 0; phase < B.BOSS_PHASE_COUNT; phase++) {
  for (let frame = 0; frame < B.BOSS_FRAME_COUNT; frame++) {
    const image = B.bossSprite(id, undefined, frame, { phase });
    const scale = B.bossStageScale(id);
    const stage = new BattleFX(null);
    stage.scene = { boss: true, enemy: { sprite: id }, drift: 0 };
    stage.lastBossBlit = { x: 37, y: 19, w: image.width * scale, h: image.height * scale, frame, phase, beat: 0 };
    await stage.dissolve();
    const opaque = image.data.reduce((n, v, i) => n + (i % 4 === 3 && v >= 40 ? 1 : 0), 0);
    const expected = Math.ceil(opaque / Math.max(1, Math.ceil(opaque / 384)));
    assert.equal(stage.particles.length, expected, `${id} ${phase}/${frame}: sampled count`);
    assert.ok(stage.particles.length <= 384);
    for (const particle of stage.particles) {
      const x = (particle.x - 37) / scale, y = (particle.y - 19) / scale;
      assert.ok(Number.isInteger(x) && Number.isInteger(y), 'native integer particle anchor');
      assert.equal(particle.size, scale);
      assert.ok(x >= 0 && x < image.width && y >= 0 && y < image.height);
      const offset = (y * image.width + x) * 4;
      assert.ok(image.data[offset + 3] >= 40, 'particle comes from opaque art');
      assert.equal(particle.colour, `rgb(${image.data[offset]},${image.data[offset + 1]},${image.data[offset + 2]})`);
    }
    maxDissolveParticles = Math.max(maxDissolveParticles, stage.particles.length);
    stage._update(1.2);
    assert.equal(stage.particles.length, 0, 'dissolve particles expire');
    stage.clearEffects(); stage.setReducedMotion(true);
    await stage.dissolve();
    assert.equal(stage.particles.length, 0, 'reduced motion omits dissolve particles');
    dissolves++;
  }
}

installStub();
globalThis.requestAnimationFrame = () => 0;
globalThis.cancelAnimationFrame = () => {};
globalThis.addEventListener = () => {};
globalThis.removeEventListener = () => {};
const calls = [
  ['cast', s => s.cast()],
  ['trials', s => s.resolveTrials([{ passed: true }, { passed: false }, { passed: true, crit: true }])],
  ...['ORACLE', 'REVEAL_PATH', 'VISION', 'PSEUDOSIGHT', 'CODE_FRAGMENT', 'PHOENIX'].map(id => [id, s => s.castSpell(id)]),
  ...['FIRE', 'COLD', 'POISON', 'BRUTE', 'LIGHTNING', 'VOID', 'NEUTRAL'].map(element => [element, s => s.elemental({ element, kind: 'OPPOSED', multiplier: 1.5, damage: 4 })]),
  ['technique1', s => s.technique({ tier: 1 })],
  ['technique9', s => s.technique({ tier: 9, name: 'Demonstration', rank: 'IX', crit: true })],
  ['victory', s => s.victory({ rank: 'S', xp: 120, xpFrom: .2, xpTo: .8, loot: { name: 'Demonstration' }, levelUp: true })],
  ['defeat', s => s.defeat({ passed: 2, total: 3 })],
  ['intro', s => s.bossIntro({ name: 'Demonstration', taunt: 'A visible test.', phases: 6 })],
  ['phase', s => s.bossPhaseTurn({ phase: 2, phases: 6, art_phase: 2, herald: 'Demonstration', tell: 'A visible test.' })],
  ['dissolve', s => s.dissolve()],
];
function makeStage(reducedMotion) {
  const s = new BattleFX(null, { reducedMotion });
  s.setScene({ region: { id: 'null_kings_castle', biome: 'castle', palette: 'castle' },
    enemy: { name: 'Demonstration', sprite: 'the_interviewer', boss: true, hp: 12, hp_max: 12 }, pattern: 'HASH_MAP' });
  s.el = {}; s.running = true;
  s.canvas = document.createElement('canvas'); s.canvas.width = 512; s.canvas.height = 448;
  s.ctx = s.canvas.getContext('2d'); s.px = 2;
  return s;
}
let completed = 0, tornDown = 0;
for (const reduced of [false, true]) for (const [name, action] of calls) {
  const stage = makeStage(reduced);
  let done = false;
  const promise = Promise.resolve(action(stage)).then(() => { done = true; });
  for (let tick = 1; tick <= 800 && !done; tick++) {
    stage._frame(tick * 25);
    await Promise.resolve();
  }
  assert.ok(done, `${name}, reduced=${reduced}: render-clock promise did not resolve`);
  await promise;
  assert.equal(stage.pending.size, 0); assert.equal(stage.timers.length, 0);
  if (reduced) assert.equal(stage.shakeMag, 0, 'reduced motion has no stage shake');
  stage.destroy(); stage.destroy(); completed++;
  const interrupted = makeStage(reduced);
  const interruptedPromise = Promise.resolve(action(interrupted));
  interrupted.destroy();
  await interruptedPromise;
  assert.equal(interrupted.pending.size, 0); assert.equal(interrupted.timers.length, 0);
  assert.equal(interrupted.el, null); tornDown++;
}
// A stopped render loop still releases queued waits through its wall-clock backstop.
const stopped = makeStage(true);
const pending = stopped._wait(.01); stopped.stop(); await pending;
assert.equal(stopped.pending.size, 0); assert.equal(stopped.timers.length, 0); stopped.destroy();
assert.equal(REC.nullImage.length, 0);
assert.equal(REC.badPaint.length, 0);
assert.deepEqual(REC.nonFinite.filter(r => !(r.op === 'fillText' && r.argIndex === 0)), []);
console.log(JSON.stringify({ ok: true, dissolves, maxDissolveParticles, reducedDissolveParticles: 0,
  renderClockCompletions: completed, interruptedCompletions: tornDown, stoppedBackstop: true,
  capScope: 'new particles emitted by each dissolve; other overlapping effects have separate particles' }));
