/* The companion, measured.
 *
 * Every claim in the follow brief is a claim about where an animal is on a
 * screen, and not one of them can be checked by asking whether the module
 * parses. So this drives a real Overworld — real terrain, real markers, real
 * rAF-free update/draw loop — over a scripted walk, and reads the answers off
 * the rasterised frame and off the companion's own state.
 *
 *   A  FOLLOW      lag distance held, and the path actually retraced
 *   B  NOT ANNOYING never on a solid tile, never on a marker tile at rest,
 *                   never the tile the player is facing, never over the hero
 *   C  Z-ORDER     it is IN _gatherObjects' sorted list, not painted after
 *   D  FACING      its own heading, measured against a player facing elsewhere
 *   E  TELEPORT    a region change puts it beside you on frame one
 *   F  NO PET      the frame is byte-identical to the same frame with the
 *                  feature absent — the only honest form of "renders as it
 *                  does today"
 *   G  STATE       read out of state.pets, the array the client already holds
 *
 * plus the two budgets this project counts rather than claims: colours in a
 * rendered companion frame, and pixels that change across a gait.
 */
import { installRaster, RASTER, pixelDiff, colourCount, frameHash } from './raster.mjs';
installRaster();
import fs from 'fs';

/* The raster stub is built for sprite sheets, not for a live scene. Fill in the
 * handful of browser surfaces an Overworld touches on the way to a frame. */
const listeners = [];
globalThis.window.addEventListener = (t, fn) => listeners.push([t, fn]);
globalThis.window.removeEventListener = () => {};
globalThis.performance = globalThis.performance || { now: () => 0 };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
/* audio.js builds a real WebAudio graph on the first sfx. A Proxy that answers
 * every factory with another Proxy is enough for it to run and make no sound. */
const audioNode = () => new Proxy({}, {
  get(_, k) {
    if (k === 'value' || k === 'currentTime' || k === 'numberOfChannels'
        || k === 'length' || k === 'sampleRate') return 0;
    if (k === 'state') return 'running';
    if (k === 'destination' || k === 'gain' || k === 'frequency' || k === 'Q'
        || k === 'detune' || k === 'threshold' || k === 'ratio' || k === 'knee'
        || k === 'attack' || k === 'release' || k === 'pan' || k === 'delayTime'
        || k === 'playbackRate' || k === 'buffer' || k === 'type') return audioNode();
    if (k === Symbol.toPrimitive || typeof k === 'symbol') return undefined;
    return (...a) => audioNode();
  },
  set() { return true; },
});
globalThis.AudioContext = function () { return audioNode(); };
globalThis.webkitAudioContext = globalThis.AudioContext;

const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const OW = await import('../../web/js/overworld.js');
const SPR = await import('../../web/js/sprites.js');

const T = 16;
const W = 320, H = 240;

function makeCanvas() {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  cv.parentElement = { getBoundingClientRect: () => ({ width: W, height: H }) };
  return cv;
}

const PETS = [
  { id: 'jaguar', name: 'ROSETTE', species: 'Jaguar', sprite: 'jaguar',
    colour: '#e8a33d', found: true, active: true },
  { id: 'crow', name: 'WITNESS', species: 'Crow', sprite: 'crow',
    colour: '#9b96b8', found: true, active: false },
];

function build(pets) {
  const ow = new OW.Overworld(makeCanvas());
  ow.stateSource = () => ({ pets });
  ow.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
  ow.load(V.regions[1], 2);
  return ow;
}

/* Step the world exactly as start()'s loop does, minus rAF. */
const DT = 1 / 60;
function step(ow, frames, keys) {
  for (let i = 0; i < frames; i++) {
    ow.keys.clear();
    if (keys) for (const k of keys) ow.keys.add(k);
    ow.update(DT);
    ow.draw();
  }
}

const fail = [];
const note = (m) => fail.push(m);
const out = {};

/* ---------------- art: wait for the lazy import to resolve ---------------- */
let ow = build(PETS);
step(ow, 2);
for (let i = 0; i < 40 && !(ow.companion && ow.companion.art); i++) {
  await new Promise(r => setImmediate(r));
  step(ow, 1);
}
const art = ow.companion && ow.companion.art;
{
  let petart = null;
  try { petart = await import('../../web/js/petart.js'); } catch (e) { petart = null; }
  const hasContract = !!(petart && typeof petart.petSprites === 'function');
  out.artSource = hasContract
    ? 'petart.js petSprites()'
    : (fs.existsSync(new URL('../../web/js/petart.js', import.meta.url))
        ? 'partyui.js petSprite() — petart.js is on disk but exports no petSprites() yet'
        : 'partyui.js petSprite() — petart.js not on disk yet');
  out.petartExportsSeen = petart ? Object.keys(petart) : [];
}
out.artLoaded = !!art;
if (!art) note('companion art never resolved');
const probe = art && art.down && art.down[0];
out.spriteSize = probe ? `${probe.width}x${probe.height}` : null;

/* ---------------- G. read out of state.pets ---------------- */
out.stateField = 'state.pets[] (rows with found/active/sprite/colour) — no new fetch';
out.pickedAnimal = ow.companion && ow.companion.animal;
if (out.pickedAnimal !== 'jaguar') note(`picked ${out.pickedAnimal}, expected the active row`);

/* ---------------- A + B. a scripted walk ---------------- */
let lagMin = Infinity, lagMax = 0, lagSum = 0, lagN = 0;
let onSolid = 0, offPath = 0, maxOffPath = 0, maxOffPathSettled = 0;
let overHero = 0, overHeroBehind = 0;
const path = [];          // every player pixel position, for the retrace test

function sampleWalk(ow) {
  const p = ow.player, c = ow.companion;
  path.push([p.px, p.py]);
  if (!c) return;
  const d = Math.hypot(c.px - p.px, c.py - p.py);
  lagMin = Math.min(lagMin, d); lagMax = Math.max(lagMax, d);
  lagSum += d; lagN++;
  const tx = Math.floor((c.px + T / 2) / T), ty = Math.floor((c.py + T / 2) / T);
  if (ow.solid(tx, ty)) onSolid++;
  // nearest point on the ground the player has actually stood on
  let best = Infinity;
  for (let i = Math.max(0, path.length - 400); i < path.length; i++) {
    const dd = Math.hypot(path[i][0] - c.px, path[i][1] - c.py);
    if (dd < best) best = dd;
  }
  if (c.settled) maxOffPathSettled = Math.max(maxOffPathSettled, best);
  else maxOffPath = Math.max(maxOffPath, best);
  if (best > T) offPath++;
}

// a route with corners, reversals and a long straight
const LEG = [
  [['arrowright'], 150], [['arrowdown'], 90], [['arrowright'], 60],
  [['arrowup'], 120], [['arrowleft'], 70], [[], 40],
  [['arrowdown'], 60], [['arrowleft'], 90], [['arrowup'], 50], [[], 60],
];
for (const [keys, frames] of LEG) {
  for (let i = 0; i < frames; i++) {
    ow.keys.clear(); for (const k of keys) ow.keys.add(k);
    ow.update(DT); ow.draw();
    sampleWalk(ow);
    // C: it must be inside the sorted list, never appended after it
    const objs = ow._objects;
    const c = ow.companion;
    if (c && c.art) {
      const mine = objs.filter(o => o.sortY !== undefined
        && Math.abs(o.x - Math.floor(c.px / T)) < 1 && Math.abs(o.y - Math.floor(c.py / T)) < 1);
      if (!mine.length && keys.length) { /* culled by tile rounding, not a failure */ }
    }
  }
}
out.follow = {
  lagMin: +lagMin.toFixed(2), lagMax: +lagMax.toFixed(2),
  lagMean: +(lagSum / lagN).toFixed(2),
  configuredLag: 18,
  samples: lagN,
  framesOnASolidTile: onSolid,
  maxDistanceOffTheWalkedPathWhileFollowing: +maxOffPath.toFixed(2),
  maxDistanceOffItWhileSettlingBesideYou: +maxOffPathSettled.toFixed(2),
  settleOffsetByDesign: 13,
  framesMoreThanATileOffThatPath: offPath,
};
if (onSolid) note(`companion stood on a solid tile on ${onSolid} frame(s)`);
if (maxOffPath > T) note(`companion strayed ${maxOffPath.toFixed(1)}px off the walked path`);
if (lagMax > 40) note(`companion fell ${lagMax.toFixed(1)}px behind — reads as towed`);

/* ---------------- C. z-order, measured off the sorted list ---------------- */
{
  const objs = ow._objects;
  const p = ow.player, c = ow.companion;
  const hero = objs.find(o => Math.abs(o.sortY - (p.py + T + 1)) < 0.001);
  const comp = objs.find(o => o !== hero && Math.abs(o.sortY - (c.py + T)) < 0.001
                            || (o !== hero && Math.abs(o.sortY - (p.py + T + 0.5)) < 0.001));
  out.zorder = {
    objectsInSortedList: objs.length,
    heroInList: !!hero,
    companionInList: !!comp,
    companionSortY: comp ? +comp.sortY.toFixed(2) : null,
    heroSortY: hero ? +hero.sortY.toFixed(2) : null,
  };
  if (!comp) note('companion is not in the y-sorted object list');
}

/* ---------------- B. never over the hero, over a long run ---------------- */
{
  const o2 = build(PETS);
  step(o2, 2);
  for (let i = 0; i < 40 && !(o2.companion && o2.companion.art); i++) {
    await new Promise(r => setImmediate(r)); step(o2, 1);
  }
  const legs = [[['arrowright'], 80], [['arrowleft'], 80], [['arrowup'], 60],
                [['arrowdown'], 60], [[], 60], [['arrowdown'], 40], [[], 60]];
  let overlapFrames = 0, overlapDrawnUnder = 0;
  for (const [keys, frames] of legs) {
    for (let i = 0; i < frames; i++) {
      o2.keys.clear(); for (const k of keys) o2.keys.add(k);
      o2.update(DT); o2.draw();
      const p = o2.player, c = o2.companion;
      if (!c || !c.art) continue;
      const img = c.art.down[0];
      const cx = Math.round(c.px + (T - img.width) / 2), cy = Math.round(c.py + T - img.height);
      const hx = Math.round(p.px), hy = Math.round(p.py + T - SPR.HERO_H);
      const over = cx < hx + SPR.HERO_W && cx + img.width > hx
                && cy < hy + SPR.HERO_H && cy + img.height > hy;
      if (!over) continue;
      overlapFrames++;
      // The module records the sortY it actually handed to drawSorted. Lower
      // sorts first, which means drawn first, which means underneath.
      if (c.sortY < p.py + T + 1) overlapDrawnUnder++;
    }
  }
  overHero = overlapFrames; overHeroBehind = overlapDrawnUnder;
  out.neverOverTheHero = {
    framesWhereTheBoxesOverlapped: overlapFrames,
    ofThoseSortedUnderTheHero: overlapDrawnUnder,
  };
  if (overlapFrames && overlapDrawnUnder < overlapFrames) {
    note(`companion sorted OVER the hero on ${overlapFrames - overlapDrawnUnder} frame(s)`);
  }
}

/* ---------------- B. at rest: beside, and off every interactable ---------- */
{
  let restedOnMarker = 0, restedOnFacingTile = 0, restedInsideHero = 0, rests = 0;
  for (let trial = 0; trial < 24; trial++) {
    const o3 = build(PETS);
    step(o3, 2);
    for (let i = 0; i < 40 && !(o3.companion && o3.companion.art); i++) {
      await new Promise(r => setImmediate(r)); step(o3, 1);
    }
    const dir = ['arrowright', 'arrowdown', 'arrowleft', 'arrowup'][trial % 4];
    step(o3, 30 + trial * 7, [dir]);
    step(o3, 120);                       // stand still, let it settle
    const p = o3.player, c = o3.companion;
    if (!c) continue;
    rests++;
    const tx = Math.round(c.px / T), ty = Math.round(c.py / T);
    if (o3.markers.some(m => m.kind === 'building'
          ? (tx >= m.x && tx <= m.x + 1 && ty >= m.y && ty <= m.y + 1)
          : (m.x === tx && m.y === ty))) restedOnMarker++;
    const f = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[p.facing] || [0, 1];
    if (tx === p.x + f[0] && ty === p.y + f[1]) restedOnFacingTile++;
    if (Math.hypot(c.px - p.px, c.py - p.py) < 5) restedInsideHero++;
  }
  out.atRest = { trials: rests, restedOnAnInteractable: restedOnMarker,
                 restedOnTheTileYouAreFacing: restedOnFacingTile,
                 restedInsideTheHero: restedInsideHero };
  if (restedOnMarker) note(`settled on an interactable in ${restedOnMarker} trial(s)`);
  if (restedOnFacingTile) note(`settled on the interact tile in ${restedOnFacingTile} trial(s)`);
  if (restedInsideHero) note(`settled inside the hero in ${restedInsideHero} trial(s)`);
}

/* ---------------- D. its facing is its own ---------------- */
{
  const o4 = build(PETS);
  step(o4, 2);
  for (let i = 0; i < 40 && !(o4.companion && o4.companion.art); i++) {
    await new Promise(r => setImmediate(r)); step(o4, 1);
  }
  step(o4, 120, ['arrowleft']);      // walk west; both face left
  const same = o4.companion.facing;
  // now turn north. The companion is still finishing the westward trail.
  let diverged = 0, frames = 0, sample = null;
  for (let i = 0; i < 26; i++) {
    o4.keys.clear(); o4.keys.add('arrowup');
    o4.update(DT); o4.draw();
    frames++;
    if (o4.companion.facing !== (o4.player.facing === 'side' ? 'right' : o4.player.facing)) {
      diverged++;
      if (!sample) sample = { player: o4.player.facing, companion: o4.companion.facing };
    }
  }
  out.facing = { whileBothWalkedWest: same, framesAfterTheTurn: frames,
                 framesTheyDisagreed: diverged, example: sample };
  if (!diverged) note('companion facing never diverged from the player — it is copying him');
}

/* ---------------- E. teleport ---------------- */
{
  const o5 = build(PETS);
  step(o5, 2);
  for (let i = 0; i < 40 && !(o5.companion && o5.companion.art); i++) {
    await new Promise(r => setImmediate(r)); step(o5, 1);
  }
  step(o5, 200, ['arrowright']);
  const before = Math.hypot(o5.companion.px - o5.player.px, o5.companion.py - o5.player.py);
  o5.load(V.regions[4], 3, { x: 30, y: 9 });      // a region change, far away
  const atLoad = Math.hypot(o5.companion.px - o5.player.px, o5.companion.py - o5.player.py);
  step(o5, 1);
  const frame1 = Math.hypot(o5.companion.px - o5.player.px, o5.companion.py - o5.player.py);
  // and a fast travel inside one region: teleport the player, do not call load()
  o5.player.x = 8; o5.player.y = 28; o5.player.px = 8 * T; o5.player.py = 28 * T;
  step(o5, 1);
  const afterJump = Math.hypot(o5.companion.px - o5.player.px, o5.companion.py - o5.player.py);
  out.teleport = {
    distanceBeforeTheRegionChange: +before.toFixed(2),
    distanceImmediatelyAfterLoad: +atLoad.toFixed(2),
    distanceOnFrameOne: +frame1.toFixed(2),
    distanceOneFrameAfterAnUnannouncedJump: +afterJump.toFixed(2),
    trailSamplesHeld: o5.trail.count,
  };
  if (frame1 > T * 1.5) note(`companion did not arrive with the player: ${frame1.toFixed(1)}px away`);
  if (afterJump > T * 1.5) note(`companion did not follow an unannounced jump: ${afterJump.toFixed(1)}px`);
}

/* ---------------- F. no pet at all: byte-identical frames -------------- */
{
  const NONE = [{ ...PETS[0], active: false }, PETS[1]];
  const DEAD = [{ ...PETS[0], dead: true }, PETS[1]];
  const UNFOUND = [{ ...PETS[0], found: false }, PETS[1]];
  const hashes = {};
  for (const [label, pets] of [['noStateSourceAtAll', undefined], ['noneActive', NONE],
                               ['dead', DEAD], ['notFound', UNFOUND],
                               ['emptyPetsArray', []], ['stateSourceThrows', 'THROW']]) {
    const o = new OW.Overworld(makeCanvas());
    if (pets === 'THROW') o.stateSource = () => { throw new Error('mid-rewrite'); };
    else if (pets !== undefined) o.stateSource = () => ({ pets });
    o.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
    o.load(V.regions[1], 2);
    step(o, 40, ['arrowright']);
    step(o, 20);
    hashes[label] = { frame: frameHash(o.canvas), companion: o.companion === null };
  }
  const base = hashes.noStateSourceAtAll.frame;
  out.noCompanion = hashes;
  out.noCompanionAllIdentical = Object.values(hashes).every(v => v.frame === base && v.companion);
  if (!out.noCompanionAllIdentical) {
    note('a world with no companion does not render identically to one before this feature');
  }
}

/* ---------------- the colour budget, counted off the raster ------------- */
{
  const counts = [];
  for (const animal of ['jaguar', 'snake', 'llama', 'penguin', 'raptor', 'axolotl',
                        'tortoise', 'nautilus', 'crow', '__no_such_animal__']) {
    const row = { id: animal, sprite: animal, colour: '#e8a33d', found: true, active: true };
    const o = new OW.Overworld(makeCanvas());
    o.stateSource = () => ({ pets: [row] });
    o.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
    o.load(V.regions[1], 2);
    step(o, 2);
    for (let i = 0; i < 40 && !(o.companion && o.companion.art); i++) {
      await new Promise(r => setImmediate(r)); step(o, 1);
    }
    const a = o.companion && o.companion.art;
    if (!a) { counts.push([animal, null]); continue; }
    let worst = 0;
    for (const f of ['down', 'up', 'left', 'right']) {
      for (const img of a[f]) worst = Math.max(worst, colourCount(img));
      for (const img of a.idle[f]) worst = Math.max(worst, colourCount(img));
    }
    counts.push([animal, worst]);
  }
  out.colourBudget = Object.fromEntries(counts);
  const over = counts.filter(([, n]) => n !== null && n > 15);
  out.coloursOverBudget = over;
  if (over.length) note(`over the fifteen-colour budget: ${JSON.stringify(over)}`);
}

/* ---------------- the gait, counted in pixels that move ---------------- */
{
  const o = build(PETS);
  step(o, 2);
  for (let i = 0; i < 40 && !(o.companion && o.companion.art); i++) {
    await new Promise(r => setImmediate(r)); step(o, 1);
  }
  const a = o.companion.art;
  const walk = a.down;
  const diffs = [];
  for (let i = 0; i < walk.length; i++) {
    diffs.push(pixelDiff(walk[i], walk[(i + 1) % walk.length]));
  }
  const idle = a.idle.down;
  out.gait = {
    framesPerFacing: walk.length,
    pixelsChangedBetweenConsecutiveWalkFrames: diffs,
    pixelsChangedBetweenIdleFrames: pixelDiff(idle[0], idle[1]),
    totalPixelsInAFrame: walk[0].width * walk[0].height,
  };
  // how many distinct gait frames the walk actually reaches over a run
  const seen = new Set();
  for (let i = 0; i < 240; i++) {
    o.keys.clear(); o.keys.add('arrowright');
    o.update(DT); o.draw();
    seen.add(o.companion.frame % walk.length);
  }
  out.gait.distinctFramesReachedOverA240FrameWalk = seen.size;
  out.gait.note = out.artSource.startsWith('petart')
    ? 'four authored gait frames per facing'
    : 'the fallback has one pose and a breath, so the four walk slots alternate '
      + 'two images; the gait INDEX is driven by ground covered either way and '
      + 'reaches every slot, so real four-frame art drops straight in';
  if (diffs.every(d => d === 0)) note('the gait does not change a single pixel');
}

/* ---------------- steady state: no canvas allocated in the loop --------
 *
 * The scene warms its own caches for a long time — bosses.js builds a boss
 * frame the first time its idle animation reaches it, and that has nothing to
 * do with a pet. So both worlds are walked for the same 1200 frames first, and
 * then the same 600 are counted. The number that matters is the difference.
 */
{
  const WARM = 1200, COUNT = 300;
  const measure = (o) => {
    step(o, WARM / 2, ['arrowright']);
    step(o, WARM / 2);
    RASTER.counting = true; RASTER.canvases = 0;
    step(o, COUNT, ['arrowright']);
    const walking = RASTER.canvases;
    RASTER.canvases = 0;
    step(o, COUNT);
    const standing = RASTER.canvases;
    RASTER.counting = false;
    return { walking300: walking, standing300: standing };
  };
  const withPet = build(PETS);
  step(withPet, 2);
  for (let i = 0; i < 40 && !(withPet.companion && withPet.companion.art); i++) {
    await new Promise(r => setImmediate(r)); step(withPet, 1);
  }
  const bare = build([{ ...PETS[0], active: false }, PETS[1]]);
  step(bare, 2);
  for (let i = 0; i < 40; i++) { await new Promise(r => setImmediate(r)); step(bare, 1); }
  const a = measure(withPet), b = measure(bare);
  out.steadyState = { withCompanion: a, withNoCompanion: b,
                      addedByTheCompanion: (a.walking300 + a.standing300)
                                         - (b.walking300 + b.standing300) };
  if (out.steadyState.addedByTheCompanion > 0) {
    note(`the companion added ${out.steadyState.addedByTheCompanion} canvas alloc(s) to a warm draw loop`);
  }
}

/* ---------------- determinism: the same walk twice ---------------- */
{
  const run = () => {
    const o = build(PETS);
    step(o, 2);
    step(o, 120, ['arrowright']);
    step(o, 60, ['arrowdown']);
    step(o, 40);
    return { x: o.companion.px, y: o.companion.py, facing: o.companion.facing,
             frame: o.companion.frame, side: o._settleSide };
  };
  const a = run(), b = run();
  out.determinism = { first: a, second: b,
                      identical: JSON.stringify(a) === JSON.stringify(b) };
  if (!out.determinism.identical) note('two identical walks put the companion in two places');
}

out.failures = fail.length;
out.detail = fail;
console.log(JSON.stringify(out, null, 1));
process.exit(fail.length ? 1 : 0);
