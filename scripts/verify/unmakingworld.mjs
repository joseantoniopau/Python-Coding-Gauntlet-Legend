/* The Unmaking, MOUNTED — the spell as it reaches a real overworld frame.
 *
 * scripts/verify/unmakingfx.mjs measures the module on its own: the beats, the
 * substitutions, the contour, the colour budget of a plate. It cannot measure
 * the half that lives in web/js/overworld.js, and that half is where the brief's
 * own sentence is actually kept — "a green lighting graphical on your sprite and
 * screen when he casts the last spell". A module nobody mounts renders nothing.
 *
 * So this drives an actual Overworld, with actual hero frames and an actual
 * companion following, and measures:
 *
 *   1  IT NEVER BLOCKS   the player walks, interacts and leaves the region
 *                        while being unmade, and the debug row says so too
 *   2  THE PER-STEP TABLE  what leaves, pixels changed on the hero, silhouette
 *                        cells changed — counted off the sprite the frame drew
 *   3  THE LAST FRAME    the plain hero: no gear tint, no rim, no arcs on the
 *                        sprite, no wash on the screen — and he STAYS plain,
 *                        which is the bug this harness was written for
 *   4  FIFTEEN COLOURS   off the rendered plate, worst frame named
 *   5  NOTHING ALLOCATES the whole sequence, companion included, at zero
 *                        canvases inside the draw loop
 *   6  NO SPELL, NO COST the frame is byte-identical with nothing being taken
 *   7  REDUCED MOTION    one still per beat, the stills differ, and the last
 *                        one has no green left in it
 */
import { installRaster, RASTER, colourCount, frameHash } from './raster.mjs';
installRaster();
import fs from 'fs';

globalThis.window.addEventListener = () => {};
globalThis.window.removeEventListener = () => {};
globalThis.performance = globalThis.performance || { now: () => 0 };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
const audioNode = () => new Proxy({}, {
  get(_, k) {
    if (k === 'value' || k === 'currentTime' || k === 'numberOfChannels'
        || k === 'length' || k === 'sampleRate') return 0;
    if (k === 'state') return 'running';
    if (k === 'destination' || k === 'gain' || k === 'frequency' || k === 'Q'
        || k === 'detune' || k === 'threshold' || k === 'ratio' || k === 'knee'
        || k === 'attack' || k === 'release' || k === 'pan' || k === 'delayTime'
        || k === 'playbackRate' || k === 'buffer' || k === 'type') return audioNode();
    if (typeof k === 'symbol') return undefined;
    return () => audioNode();
  },
  set() { return true; },
});
globalThis.AudioContext = function () { return audioNode(); };
globalThis.webkitAudioContext = globalThis.AudioContext;

const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const OW = await import('../../web/js/overworld.js');
const U = await import('../../web/js/unmakingfx.js');
const SPR = await import('../../web/js/sprites.js');

/* A smaller window than kingui.mjs uses on purpose: nothing measured here
 * depends on frame size, and this harness draws several thousand full
 * frames. Scale 2, which is what a small laptop actually gets. */
const T = 16, W = 480, H = 320, DT = 1 / 60, STEP = 1 / 30;
const REGION = V.regions[3];
const LOOK = { cloak: '#3c5fa8', tunic: '#8c3b4a', metal: '#c8d2e0', trim: '#a08a52',
               boot: '#715b45', skin: '#c08a62', hair: '#4a3a2c', weapon: 'sword' };
const PETS = [{ id: 'jaguar', name: 'ROSETTE', species: 'Jaguar', sprite: 'jaguar',
                colour: '#e8a33d', found: true, active: true }];
const fail = [];
const note = (m) => fail.push(m);
const out = {};

function makeCanvas() {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  cv.parentElement = { getBoundingClientRect: () => ({ width: W, height: H }) };
  return cv;
}
function build(state) {
  const ow = new OW.Overworld(makeCanvas());
  ow.stateSource = () => state;
  ow.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
  ow.load(REGION, REGION.tier || 2);
  ow.setEquipment(LOOK);
  ow.player.x = 20; ow.player.y = 16; ow.player.px = 320; ow.player.py = 256;
  return ow;
}

/* THE HERO, ALONE, painted the way the overworld's own hero entry paints him:
 * the plate the spell swapped in, then the arcs the spell puts on it. Cropping
 * him out of the composited frame instead would count the grass showing through
 * his transparent pixels as part of his palette, and the fifteen-colour rule is
 * a rule about a sprite. */
function heroSprite(ow, withArcs = true) {
  const p = ow.player;
  const facing = (p.facing === 'side') ? 'right' : p.facing;
  const frames = p.moving ? ow.hero[facing] : ow.hero.idle[facing];
  const fi = p.frame % frames.length;
  const img = frames[fi];
  const pose = p.moving ? 'walk' : 'idle';
  const u = ow.unmaking;
  const key = u ? ow._heroKey(facing, fi, pose) : '';
  const shown = u ? (u.heroImage(img, key, facing, fi, pose) || img) : img;
  const cv = document.createElement('canvas');
  cv.width = SPR.HERO_W; cv.height = SPR.HERO_H;
  const c = cv.getContext('2d');
  c.drawImage(shown, 0, 0);
  if (u && withArcs) u.drawSprite(c, shown, 0, 0, key);
  return cv;
}
const pixelDiff = (a, b) => {
  let n = 0;
  for (let i = 0; i < a.data.length; i += 4) {
    if (a.data[i] !== b.data[i] || a.data[i + 1] !== b.data[i + 1]
      || a.data[i + 2] !== b.data[i + 2] || a.data[i + 3] !== b.data[i + 3]) n++;
  }
  return n;
};
const coverOf = (cv) => {
  const s = new Set();
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++)
    if (cv.data[(y * cv.width + x) * 4 + 3]) s.add(y * 64 + x);
  return s;
};
const coverDiff = (a, b) =>
  [...a].filter(c => !b.has(c)).length + [...b].filter(c => !a.has(c)).length;

/* ---------------- 2 + 3. the per-step table, and the last frame ----------- */
for (const [label, spec] of [['standaloneTable', {}],
                             ['gauntletUnmakingPy', null]]) {
  let use = spec;
  if (use === null) {
    // gauntlet/unmaking.py's own order and timings, through beatsFromCinematic.
    try {
      const { execSync } = await import('child_process');
      const json = execSync(
        'python3 -c "import json,sys;sys.path.insert(0,\'.\');'
        + 'from gauntlet import unmaking as U;print(json.dumps(U.cinematic(),default=str))"',
        { cwd: new URL('../../', import.meta.url).pathname, encoding: 'utf8' });
      use = { cinematic: JSON.parse(json) };
    } catch (e) { out[label] = { skipped: 'gauntlet/unmaking.py did not answer' }; continue; }
  }
  const ow = build(null);
  const fx = ow.castUnmaking(use);
  if (!fx) { note(`${label}: castUnmaking built nothing`); continue; }

  const rows = [];
  let prev = null, prevCover = null, guard = 0;
  while (!fx.done && guard++ < 4000) {
    ow.update(STEP); ow.draw();
    const u = ow.unmaking;
    if (!u) break;
    // sampled at the end of each beat, after the taking has landed
    if (u.k > 0.93 && (!rows.length || rows[rows.length - 1].beat !== u.beat)) {
      const cv = heroSprite(ow, false);
      const cover = coverOf(cv);
      const takes = u.beats[u.beat].takes;
      rows.push({
        beat: u.beat, id: u.beatId,
        takes: (typeof takes === 'string' ? [takes] : (takes || [])).slice(),
        pixelsChangedOnHero: prev ? pixelDiff(prev, cv) : 0,
        silhouetteCellsChanged: prevCover ? coverDiff(prevCover, cover) : 0,
        coloursOnHero: colourCount(cv),
        screenAlpha: +ow._unmakingScreenPeak.toFixed(4),
        arcPixels: ow._unmakingArcPx,
        // 1 throughout: these two passes run with no pet in the field, so the
        // companion's departure is measured in the allocation block instead,
        // which is the only one that actually has an animal to take.
        companionAlpha: +ow._unmakingCompanionAlpha.toFixed(3),
      });
      prev = cv; prevCover = cover;
    }
  }
  ow.update(STEP); ow.draw();     // the frame after the last beat

  const ref = build(null);
  ref.update(STEP); ref.draw();
  const dressed = heroSprite(ref);
  const plain = heroSprite(ow);
  const F = {
    spellFinished: !!(ow.unmaking && ow.unmaking.done),
    heroStaysPlainAfterwards: !!ow.unmaking,
    screenAlpha: +ow._unmakingScreenPeak.toFixed(4),
    arcPixelsOnSprite: ow._unmakingArcPx,
    coloursOnPlainHero: colourCount(plain),
    coloursOnDressedHero: colourCount(dressed),
    pixelsDifferentFromDressed: pixelDiff(dressed, plain),
    silhouetteIdentical: (() => {
      const a = coverOf(dressed), b = coverOf(plain);
      return a.size === b.size && [...a].every(c => b.has(c));
    })(),
  };
  out[label] = { beats: rows.length, table: rows, finalFrame: F };

  if (!F.spellFinished) note(`${label}: the spell never ended`);
  if (!F.heroStaysPlainAfterwards) note(`${label}: the hero got his gear back the frame it ended`);
  if (F.screenAlpha !== 0) note(`${label}: the last frame still washes the screen (${F.screenAlpha})`);
  if (F.arcPixelsOnSprite !== 0) note(`${label}: the last frame still has ${F.arcPixelsOnSprite} arc pixels on him`);
  if (!F.silhouetteIdentical) note(`${label}: the hero's silhouette moved — the one thing the King does not get`);
  if (F.pixelsDifferentFromDressed <= 0) note(`${label}: the plain hero is the dressed hero`);
  if (F.coloursOnPlainHero >= F.coloursOnDressedHero) note(`${label}: the plain hero did not collapse colours`);
}

/* ---------------- 4. fifteen colours, off the rendered plate -------------- */
{
  const ow = build(null);
  ow.castUnmaking({});
  let worstPlate = { colours: 0 }, worstLit = { colours: 0 };
  let guard = 0;
  // No ow.draw() in this loop: the colour budget is a property of the sprite,
  // and painting the whole field several hundred times to read it is a minute
  // of wall clock for a number that does not depend on the field.
  while (ow.unmaking && !ow.unmaking.done && guard++ < 4000) {
    ow.update(STEP);
    const u = ow.unmaking;
    if (!u) break;
    const where = `${u.beatId} k=${u.k.toFixed(2)}`;
    const p = colourCount(heroSprite(ow, false));
    if (p > worstPlate.colours) worstPlate = { colours: p, frame: where };
    const l = colourCount(heroSprite(ow, true));
    if (l > worstLit.colours) worstLit = { colours: l, frame: where };
  }
  out.fifteenColours = {
    rule: 'fifteen per SPRITE plus transparent, counted from rendered output',
    worstPlate, budget: 15,
    worstWithArcsComposited: worstLit,
    note: 'the arcs are a translucent light pass, not a palette: compositing one '
        + 'colour over a fourteen-colour sprite produces a blend per base pixel, '
        + 'the same way the night tint and the vignette do. The budget is the plate.',
  };
  if (worstPlate.colours > 15) note(`fifteen colours: the plate reaches ${worstPlate.colours} at ${worstPlate.frame}`);
}

/* ---------------- 1. it never blocks ------------------------------------- */
{
  const ow = build(null);
  ow.castUnmaking({});
  const x0 = ow.player.px;
  for (let i = 0; i < 90; i++) {
    ow.keys.clear(); ow.keys.add('arrowright'); ow.update(DT); ow.draw();
  }
  const walked = Math.abs(ow.player.px - x0);
  let interacted = true;
  try { ow.interact(); } catch (e) { interacted = false; }
  const d = ow.unmakingDebug();
  let left = true;
  try { ow.load(V.regions[1], 2); } catch (e) { left = false; }
  const src = fs.readFileSync(new URL('../../web/js/unmakingfx.js', import.meta.url), 'utf8');
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  out.neverBlocks = {
    walkedWhileBeingUnmade: walked,
    interactStillWorks: interacted,
    leftTheRegionMidSpell: left,
    spellClearedByTheDoor: ow.unmaking === null,
    debugRowSaysBlocking: d ? d.blocking : null,
    moduleTouchesInput: /addEventListener|preventDefault|prompt\(|confirm\(|alert\(/.test(code),
    moduleUsesTimersOrPromises: /\bawait\b|setTimeout|setInterval|new Promise/.test(code),
    mathRandomInCode: (code.match(/Math\.random/g) || []).length,
    dateNowInCode: (code.match(/Date\.now|new Date\(/g) || []).length,
  };
  if (walked < 8) note('1: the player could not walk while being unmade');
  if (!interacted) note('1: interact() stopped working mid-spell');
  if (ow.unmaking !== null) note('1: the spell survived a region change');
  if (d && d.blocking !== false) note('1: the debug row does not say blocking:false');
  if (out.neverBlocks.moduleTouchesInput) note('1: unmakingfx touches input');
  if (out.neverBlocks.moduleUsesTimersOrPromises) note('1: unmakingfx uses a timer or a promise');
  if (out.neverBlocks.mathRandomInCode) note('1: Math.random in unmakingfx');
  if (out.neverBlocks.dateNowInCode) note('1: a clock read in unmakingfx');
}

/* ---------------- 5. nothing allocates, companion included --------------- */
{
  const ow = build({ pets: PETS });
  // the companion's art is loaded lazily; walk until it is actually there
  for (let i = 0; i < 200; i++) {
    ow.keys.clear(); ow.keys.add(i % 2 ? 'arrowright' : 'arrowleft');
    ow.update(DT); ow.draw();
  }
  await new Promise(r => setTimeout(r, 50));
  for (let i = 0; i < 120; i++) { ow.update(DT); ow.draw(); }
  const hadCompanion = !!(ow.companion && ow.companion.art);

  ow.castUnmaking({});
  const prewarmed = ow._unmakingPrewarmed;
  for (let i = 0; i < 60; i++) { ow.update(STEP); ow.draw(); }
  RASTER.canvases = 0; RASTER.counting = true;
  let guard = 0, sawZero = false;
  while (ow.unmaking && !ow.unmaking.done && guard++ < 4000) {
    ow.update(STEP); ow.draw();
    if (ow._unmakingCompanionAlpha === 0) sawZero = true;
  }
  const alloc = RASTER.canvases;
  RASTER.counting = false;
  out.steadyState = {
    companionInTheField: hadCompanion,
    // 0 here means the cache was ALREADY warm from an earlier block in this
    // same process, not that nothing was warmed: unmakingfx.prewarm counts
    // cache growth. A cold process reports 96. What matters is the line below.
    platesBuiltAtCast: prewarmed,
    canvasesAllocatedInsideTheDrawLoop: alloc,
    companionReachedZeroAlpha: sawZero,
    companionAlphaAtTheEnd: ow._unmakingCompanionAlpha,
  };
  if (!hadCompanion) note('5: no companion was in the field — the allocation test proved less than it says');
  if (alloc !== 0) note(`5: ${alloc} canvases allocated inside the draw loop`);
  if (hadCompanion && !sawZero) note('5: the companion never left');
}

/* ---------------- 6. no spell, no cost ----------------------------------- */
{
  const a = build(null), b = build(null);
  const ha = [], hb = [];
  for (let i = 0; i < 12; i++) { a.update(DT); a.draw(); ha.push(frameHash(a.ctx.canvas)); }
  b.setUnmaking(null);
  for (let i = 0; i < 12; i++) { b.update(DT); b.draw(); hb.push(frameHash(b.ctx.canvas)); }
  const c = build(null);
  c.stateSource = () => { throw new Error('mid-rewrite'); };
  let threw = false;
  try { for (let i = 0; i < 12; i++) { c.update(DT); c.draw(); } } catch (e) { threw = true; }
  out.noSpellNoCost = {
    identicalFrames: ha.join() === hb.join(),
    aThrowingStateSourceIsSilent: !threw && c.unmaking === null,
  };
  if (ha.join() !== hb.join()) note('6: an explicit null row changed the frame');
  if (threw) note('6: a stateSource that throws took the overworld with it');
}

/* ---------------- 7. reduced motion -------------------------------------- */
{
  const ow = build(null);
  ow.reducedMotion = true;
  ow.castUnmaking({});
  const stills = new Set();
  const perBeat = {};
  let guard = 0;
  while (ow.unmaking && !ow.unmaking.done && guard++ < 4000) {
    ow.update(STEP);
    if (!ow.unmaking) break;
    const h = frameHash(heroSprite(ow));
    stills.add(h);
    (perBeat[ow.unmaking.beatId] ||= new Set()).add(h);
  }
  ow.update(STEP); ow.draw();
  out.reducedMotion = {
    distinctStills: stills.size,
    stillsWithinEachBeat: Object.fromEntries(
      Object.entries(perBeat).map(([k, v]) => [k, v.size])),
    finalScreenAlpha: +ow._unmakingScreenPeak.toFixed(4),
    finalArcPixels: ow._unmakingArcPx,
    rule: 'one still per beat, the stills must differ, and the last one is a plain man',
  };
  for (const [k, v] of Object.entries(out.reducedMotion.stillsWithinEachBeat))
    if (v !== 1) note(`7: beat ${k} produced ${v} distinct stills under reduced motion`);
  if (stills.size < 4) note('7: too few distinct stills to communicate the event');
  if (ow._unmakingScreenPeak !== 0 || ow._unmakingArcPx !== 0)
    note('7: the reduced-motion final still still has green on it');
}

/* ---------------- determinism -------------------------------------------- */
{
  const run = () => {
    U.clearUnmakingCache();
    const ow = build(null);
    ow.castUnmaking({});
    const hs = [];
    for (let i = 0; i < 90; i++) { ow.update(STEP); ow.draw(); hs.push(frameHash(ow.ctx.canvas)); }
    return hs.join();
  };
  out.deterministic = run() === run();
  if (!out.deterministic) note('two identical runs drew different frames');
}

out.FAILURES = fail;
out.VERDICT = fail.length ? 'FAIL' : 'PASS';
console.log(JSON.stringify(out, null, 1));
if (fail.length) process.exitCode = 1;
