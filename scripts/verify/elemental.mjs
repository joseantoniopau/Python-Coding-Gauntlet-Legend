/* The elemental layer, drawn. showResult wraps the whole animation in a
 * try/catch so the report always appears — which means a throw inside an
 * element's effect is invisible in the browser and shows up as "the fire one
 * does nothing". This drives every motion, every matchup and every status
 * through the instrumented canvas stub instead, where a nullish image, a
 * non-finite coordinate or a paint value that resolved to undefined is a
 * recorded failure rather than a silently transparent pixel. */
import { installStub, REC, newCtx, setWhere } from './stub.mjs';
installStub();
/* Two things BattleFX.mount touches that the shared stub does not model, added
 * here rather than in stub.mjs because every other verify script is happy
 * without them and a shared fixture is not the place for one module's needs. */
if (!document.head) document.head = document.createElement('head');
if (!globalThis.getComputedStyle) globalThis.getComputedStyle = () => ({ position: 'relative' });
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
}

const FX = await import('../../web/js/fx.js');

const fail = [];
const note = (m) => fail.push(m);

/* A stage with no DOM host: mount() needs one, so give it the stub's. */
const host = document.createElement('div');
document.body.appendChild(host);

function stage(reduced) {
  const s = new FX.BattleFX(host, { reducedMotion: reduced });
  s.setScene({
    region: { id: 'stringwood_labyrinth', biome: 'forest', palette: 'spring' },
    enemy: { name: 'Vaultling', sprite: 'vaultling', boss: false, hp: 6, hp_max: 6 },
    pattern: 'HASH_MAP',
  });
  return s;
}

const KINDS = ['OPPOSED', 'SECONDARY', 'WEAK_INTO', 'SAME', 'NEUTRAL'];
const MULT = { OPPOSED: 1.5, SECONDARY: 1.2, WEAK_INTO: 0.85, SAME: 0.65, NEUTRAL: 1.0 };
const IDS = Object.keys(FX.ELEMENT_FX);

/* 1. every element, every matchup, both sides, both motion settings */
let played = 0;
for (const reduced of [false, true]) {
  const s = stage(reduced);
  const ctx = s.ctx;
  for (const id of IDS) {
    for (const kind of KINDS) {
      for (const side of ['enemy', 'hero']) {
        setWhere(`elemental(${id},${kind},${side},rm=${reduced})`);
        try {
          s.elemental({ element: id, multiplier: MULT[kind], kind, damage: 4,
                        label: 'a counter', side, absorbed: 2, resisted: 0.2 });
        } catch (e) { note(`THROW elemental(${id},${kind},${side}): ${e.message}`); }
        // Drain the whole effect rather than one frame: the strobe, the hold
        // frame and the collapse all live at different points on the curve, and
        // a bolt that only ever draws at k=0 is a bolt nobody checked.
        for (let f = 0; f < 40; f++) {
          try { s._update(0.03); s._render(); } catch (e) {
            note(`THROW render(${id},${kind},f=${f}): ${e.message}`); break;
          }
        }
        played++;
      }
    }
  }
  /* 2. statuses ticking on both sides */
  for (const st of ['POISONED','BURNING','CHILLED','SHOCKED','STAGGERED','VOIDED','']) {
    for (const side of ['hero','enemy']) {
      setWhere(`statusTick(${st},${side})`);
      try { s.statusTick({ status: st, element: 'POISON', damage: 1, side, label: st }); }
      catch (e) { note(`THROW statusTick(${st},${side}): ${e.message}`); }
      for (let f = 0; f < 30; f++) { s._update(0.03); s._render(); }
    }
  }
  /* 3. a draught */
  setWhere('drink');
  try { s.drink({ colour: '#ff6a7a', amount: 7, name: 'Health' }); }
  catch (e) { note(`THROW drink: ${e.message}`); }
  for (let f = 0; f < 30; f++) { s._update(0.03); s._render(); }

  /* 4. the area wash, including the neutral case and rubbish input */
  for (const id of IDS.concat(['', 'NOT_AN_ELEMENT', null, undefined])) {
    setWhere(`setAffinity(${id})`);
    try { s.setAffinity(id, { hazard: 'SPORE' }); } catch (e) {
      note(`THROW setAffinity(${id}): ${e.message}`);
    }
    for (let f = 0; f < 6; f++) { s._update(0.03); s._render(); }
  }
  /* a neutral region must leave nothing behind */
  s.setAffinity('NEUTRAL');
  if (s.affinity !== '' || s.affinityTint !== 0) {
    note(`setAffinity(NEUTRAL) left affinity=${s.affinity} tint=${s.affinityTint}`);
  }
  s.destroy();
}

/* 5. no element may be only a colour. Two elements whose effect builders return
 *    the same shape would be one element with a paint tray, and the player
 *    would learn the wheel off the label instead of off the screen. */
const s2 = stage(false);
const shapes = new Map();
for (const id of IDS) {
  const fx = FX.elementFx(id);
  const eff = s2._elementEffect(fx.motion, {
    x: 100, y: 70, k: 0.7, colour: fx.colour, dark: fx.dark, shrugged: false });
  const key = String(eff.draw);
  if (shapes.has(key)) note(`${id} draws the same shape as ${shapes.get(key)}`);
  shapes.set(key, id);
  if (!(eff.dur > 0)) note(`${id} has a non-positive duration ${eff.dur}`);
}
/* and the scale must actually be a scale: k=1 has to outlast or outgrow k=0 */
for (const id of IDS) {
  const fx = FX.elementFx(id);
  const lo = s2._elementEffect(fx.motion, { x: 100, y: 70, k: 0, colour: fx.colour,
                                            dark: fx.dark, shrugged: true });
  const hi = s2._elementEffect(fx.motion, { x: 100, y: 70, k: 1, colour: fx.colour,
                                            dark: fx.dark, shrugged: false });
  if (!(hi.dur > lo.dur)) note(`${id}: a counter is not longer than a shrug (${lo.dur} -> ${hi.dur})`);
}
s2.destroy();

const problems = [
  ...fail,
  ...REC.nullImage.map(r => `null image at ${r.where}`),
  // The stub counts fillText's first argument as a coordinate, which it is not:
  // it is the string. Every other non-finite report is real.
  ...REC.nonFinite
    .filter(r => !(r.op === 'fillText' && r.argIndex === 0))
    .map(r => `non-finite ${r.op} arg ${r.argIndex}=${r.value} at ${r.where}`),
  ...REC.badPaint.map(r => `bad paint ${r.prop}=${r.value} at ${r.where}`),
  ...REC.allocInLoop.map(r => `canvas allocated inside the render loop at ${r.where}`),
];
console.log(`elemental: ${played} blows played, ${IDS.length} motions, ` +
            `${REC.drawCalls} draw calls, ${REC.allocTotal} canvases`);
if (problems.length) {
  console.log('FAIL');
  for (const p of problems.slice(0, 30)) console.log('  ' + p);
  process.exit(1);
}
console.log('OK');
