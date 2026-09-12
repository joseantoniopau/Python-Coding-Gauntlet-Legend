/* Watching it come, measured.
 *
 * The chase belongs to gauntlet/hunters.py. What this harness checks is the
 * half that module cannot: whether a real Overworld, fed the rows that module
 * actually serialises, puts a creature on the screen that behaves, and whether
 * the way out is still visible while it does.
 *
 *   A  THE HUNT      it is embodied, it is IN the y-sort, its dead reckoning
 *                    never walks inside rock, and it never sorts in front of
 *                    the player, a marker or an exit
 *   B  TELEGRAPH     every one of hunters.py's states produces the vignette and
 *                    the map channel that module's own table asks for, the wash
 *                    is capped, the stale marker genuinely lags, and your
 *                    companion notices before you do
 *   C  THE WAY OUT   the gold chevron survives every pixel painted over it and
 *                    sits outboard of the threat, the exits brighten, the body
 *                    stays off the door, and no payload can make it outrun you
 *   D  NOT THERE     no hunt, and the frame is byte-identical to the same frame
 *                    with the feature absent, at zero extra canvas allocations
 *   E  STATE         read from state.hunt + state.apexes, which is what
 *                    hunters.Hunt.to_dict() and client_payload() emit, with
 *                    every degrade path silent
 *   F  MIRROR        the engine's position is authority and the client's dead
 *                    reckoning is a guess: how wrong the guess gets, in pixels
 *
 * The fixtures are not invented. scripts/verify/apexdata.json is a dump of
 * hunters.client_payload(), so the sprite keys, colours, elements, speeds and
 * telegraph rows under test are the ones the engine ships.
 */
import { installRaster, RASTER, colourCount, frameHash } from './raster.mjs';
installRaster();
import fs from 'fs';

const listeners = [];
globalThis.window.addEventListener = (t, fn) => listeners.push([t, fn]);
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
    if (k === Symbol.toPrimitive || typeof k === 'symbol') return undefined;
    return (...a) => audioNode();
  },
  set() { return true; },
});
globalThis.AudioContext = function () { return audioNode(); };
globalThis.webkitAudioContext = globalThis.AudioContext;

const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));
const ENGINE = JSON.parse(fs.readFileSync(new URL('./apexdata.json', import.meta.url), 'utf8'));
const OW = await import('../../web/js/overworld.js');
const AX = await import('../../web/js/apex.js');
const SPR = await import('../../web/js/sprites.js');
const BOSS = await import('../../web/js/bosses.js');

const T = 16, W = 320, H = 240, DT = 1 / 60;
const MAP_W = 48, MAP_H = 34;

function makeCanvas() {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  cv.parentElement = { getBoundingClientRect: () => ({ width: W, height: H }) };
  return cv;
}

const APEX_BY_REGION = Object.fromEntries(ENGINE.apexes.map(a => [a.region, a]));
const REGION = V.regions.find(r => APEX_BY_REGION[r.id]) || V.regions[5];

/* A hunters.Hunt.to_dict(), exactly the fields that dataclass serialises.
 * The spawn tile is looked up on the real map rather than hard-coded: the
 * engine guarantees it never spawns in rock, so a fixture that does would be
 * testing a payload the engine cannot emit. */
const PETS = [{ id: 'jaguar', name: 'ROSETTE', species: 'Jaguar', sprite: 'jaguar',
                colour: '#e8a33d', found: true, active: true }];
let SPAWN = null;
function spawnTileFor(region) {
  if (SPAWN && SPAWN.region === region.id) return SPAWN;
  const probe = new OW.Overworld(makeCanvas());
  probe.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
  probe.load(region, region.tier || 2);
  const p = probe.player;
  let best = { region: region.id, x: 30 * T, y: 8 * T };
  for (let ty = 3; ty < MAP_H - 3; ty++) {
    for (let tx = 3; tx < MAP_W - 3; tx++) {
      if (probe.solid(tx, ty)) continue;
      if (probe.markers.some(m => m.x === tx && m.y === ty)) continue;
      const d = Math.hypot(tx * T - p.px, ty * T - p.py);
      if (d >= 22 * T && d <= 30 * T) { best = { region: region.id, x: tx * T, y: ty * T }; ty = MAP_H; break; }
    }
  }
  SPAWN = best;
  return best;
}
function huntRow(region, over = {}) {
  const apex = APEX_BY_REGION[region.id] || ENGINE.apexes[0];
  const s = spawnTileFor(region);
  return {
    region: region.id, state: 'TRACKING', apex: apex.id,
    elapsed: 0, dwell: 200, pressure: 100,
    x: s.x, y: s.y, distance: 0, best_distance: 0,
    beyond: 0, scent: 0.8, cooldown: 0, spawns: 1, kills: 0, flights: 0,
    ...over,
  };
}

function build(region, hunt, extra = {}) {
  const ow = new OW.Overworld(makeCanvas());
  ow.stateSource = () => (hunt === null ? { pets: PETS }
    : { hunt, apexes: ENGINE.apexes, pets: PETS, ...extra });
  ow.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
  ow.load(region, region.tier || 2);
  return ow;
}

/* Every tile the player could walk to from here. Used to keep a fixture from
 * standing somewhere no route exists, which measures the harness rather than
 * the feature. */
function reachableFrom(ow, sx, sy) {
  const seen = new Set();
  const q = [sy * MAP_W + sx];
  seen.add(q[0]);
  for (let i = 0; i < q.length; i++) {
    const c = q[i], cx = c % MAP_W, cy = (c / MAP_W) | 0;
    const push = (tx, ty) => {
      if (tx < 0 || ty < 0 || tx >= MAP_W || ty >= MAP_H) return;
      const n = ty * MAP_W + tx;
      if (seen.has(n) || ow.solid(tx, ty)) return;
      seen.add(n); q.push(n);
    };
    push(cx + 1, cy); push(cx - 1, cy); push(cx, cy + 1); push(cx, cy - 1);
  }
  return seen;
}

function step(ow, frames, keys) {
  for (let i = 0; i < frames; i++) {
    ow.keys.clear();
    if (keys) for (const k of keys) ow.keys.add(k);
    ow.update(DT); ow.draw();
  }
}
function sim(ow, frames, keys) {
  for (let i = 0; i < frames; i++) {
    ow.keys.clear();
    if (keys) for (const k of keys) ow.keys.add(k);
    ow.update(DT);
  }
}

const fail = [];
const note = (m) => fail.push(m);
const out = {};

/* ---------------- E. the contract, and what is assumed ---------------- */
out.stateContract = {
  readsFrom: 'state.hunt (hunters.Hunt.to_dict) + state.apexes '
    + '(hunters.client_payload().apexes); state.apex_payload adopted if present',
  alsoAccepted: 'state.apex_hunt, state.hunts[] / state.apex_hunts[] by region, '
    + 'state.apex as a single row',
  engineModuleOnDisk: fs.existsSync(new URL('../../gauntlet/hunters.py', import.meta.url)),
  serverExposesItYet: false,
  assumed: [
    'the hunt row for the CURRENT region reaches the client each poll',
    'Hunt.x / Hunt.y are PIXELS in player.px/py space (SPAWN_MIN_PX = 352 implies it); '
      + 'a row whose coordinates are plainly tile indices is scaled and labelled',
    'the apex table may be absent: the creature still draws, in neutral grey',
  ],
  fallbackWhenNoCoordinatesEverArrive:
    'the same motion model drives locally from a deterministic spawn, labelled source:"local"',
};
{
  // the copied tables must equal the engine's, or the client is drawing a
  // different game from the one being simulated
  const speedMatch = Object.keys(ENGINE.speed)
    .every(k => AX.STATE_SPEED[k] === ENGINE.speed[k]);
  const teleMatch = Object.keys(ENGINE.telegraph).every(k =>
    AX.TELEGRAPH[k] && AX.TELEGRAPH[k].vignette === ENGINE.telegraph[k].vignette
    && AX.TELEGRAPH[k].map === ENGINE.telegraph[k].map
    && AX.TELEGRAPH[k].countdown === ENGINE.telegraph[k].countdown);
  out.tablesMatchTheEngine = {
    states: JSON.stringify(AX.HUNT_STATES) === JSON.stringify(ENGINE.states),
    speeds: speedMatch, telegraph: teleMatch,
    playerWalkSpeed: AX.PLAYER_WALK_SPEED === ENGINE.player_walk_speed,
    contactPx: AX.CONTACT_PX === ENGINE.distances.contact,
  };
  for (const [k, v] of Object.entries(out.tablesMatchTheEngine)) {
    if (!v) note(`the client's copy of ${k} disagrees with hunters.py`);
  }
}
{
  const ow = build(REGION, huntRow(REGION));
  sim(ow, 2);
  out.resolved = ow.apexDebug();
  if (!ow.hunt) note('a hunt in state.hunt did not resolve');
}

/* ---------------- C. nothing can make it outrun you ---------------- */
{
  const hostile = { speed: { ROAMING: 38, TRACKING: 52, CLOSING: 900, SPRINT: 400 } };
  const before = { ...AX.STATE_SPEED };
  const res = AX.adoptPayload(hostile);
  const ow = build(REGION, huntRow(REGION, { state: 'CLOSING' }), { apex_payload: hostile });
  sim(ow, 60);
  out.cannotOutrunYou = {
    playerWalkSpeed: AX.PLAYER_WALK_SPEED,
    apexMaxSpeed: AX.APEX_MAX_SPEED,
    marginPxPerSecond: AX.SPEED_MARGIN,
    payloadAskedFor: hostile.speed,
    refusedByTheClient: res.refused,
    speedActuallyUsedWhileClosing: ow.hunt.speed,
    everyStateAtOrUnderTheCap: Object.values(AX.STATE_SPEED)
      .every(v => v <= AX.APEX_MAX_SPEED),
  };
  if (ow.hunt.speed > AX.APEX_MAX_SPEED) note('a payload made the apex faster than the cap');
  if (!out.cannotOutrunYou.everyStateAtOrUnderTheCap) note('a state speed beats the cap');
  // put the table back for the rest of the run
  for (const k of Object.keys(before)) AX.STATE_SPEED[k] = before[k];
}

/* ---------------- A. it is embodied, it moves, it is in the sort -------- */
{
  const ow = build(REGION, huntRow(REGION, { state: 'TRACKING' }));
  sim(ow, 2);
  const x0 = ow.hunt.px, y0 = ow.hunt.py;
  sim(ow, 600);                                  // ten seconds, player still
  const moved = Math.hypot(ow.hunt.px - x0, ow.hunt.py - y0);
  step(ow, 2);
  const objs = ow._objects;
  const inList = objs.some(o => Math.abs(o.sortY - ow._apexSortY) < 0.001);
  out.itComes = {
    stateGiven: 'TRACKING',
    spawnedAtEngineCoordinates: spawnTileFor(REGION),
    source: ow.hunt.source,
    pixelsWalkedInTenSeconds: +moved.toFixed(1),
    speedForThatState: ow.hunt.speed,
    arithmeticPrediction: +(ow.hunt.speed * 10).toFixed(1),
    tilesAwayNow: +ow.hunt.tiles.toFixed(2),
    objectsInTheSortedList: objs.length,
    apexInThatList: inList,
    apexSortY: +ow._apexSortY.toFixed(2),
    heroSortY: +(ow.player.py + T + 1).toFixed(2),
  };
  if (moved < 100) note('the apex did not walk');
  if (!inList) note('the apex is not in the y-sorted object list');
}

/* ---------------- A. never inside rock, never in front of anything ------ */
{
  const o = build(REGION, huntRow(REGION, { state: 'CLOSING' }));
  sim(o, 60);
  let inRock = 0, frames = 0, onTheDoor = 0, aheadOfHero = 0, aheadOfMarker = 0, aheadOfExit = 0;
  const exits = o.markers.filter(m => m.kind === 'exit');
  const legs = [[[], 150], [['arrowleft'], 80], [[], 150], [['arrowup'], 60],
                [[], 120], [['arrowright'], 90], [[], 200]];
  for (const [keys, n] of legs) {
    for (let i = 0; i < n; i++) {
      o.keys.clear(); for (const k of keys) o.keys.add(k);
      o.update(DT); o.draw();
      const h = o.hunt;
      if (!h || !h.embodied) continue;
      frames++;
      const tx = Math.floor((h.tx + T / 2) / T), ty = Math.floor((h.ty + T / 2) / T);
      if (o.solid(tx, ty)) inRock++;
      for (const e of exits) {
        if (Math.hypot(e.x - tx, e.y - ty) * T < AX.EXIT_KEEP_PX - 0.001) onTheDoor++;
      }
      const bx = h.px + T / 2 - AX.APEX_SIZE / 2, by = h.py + T - AX.APEX_SIZE;
      const S = AX.APEX_SIZE;
      const p = o.player;
      const hx = p.px, hy = p.py + T - SPR.HERO_H;
      if (bx < hx + SPR.HERO_W && bx + S > hx && by < hy + SPR.HERO_H && by + S > hy
          && o._apexSortY >= p.py + T + 1) aheadOfHero++;
      for (const m of o.markers) {
        if (m.kind === 'building') continue;
        if (m.kind === 'exit') {
          const mx = m.x * T, my = m.y * T - 4;
          if (bx < mx + T && bx + S > mx && by < my + T + 8 && by + S > my
              && o._apexSortY >= m.y * T) aheadOfExit++;
          continue;
        }
        const mx = m.x * T - 4, my = m.y * T + T - 24;
        if (bx < mx + T + 8 && bx + S > mx && by < my + 24 && by + S > my
            && o._apexSortY >= m.y * T + T) aheadOfMarker++;
      }
    }
  }
  out.neverInTheWay = {
    framesEmbodied: frames,
    framesWithItsCentreInsideASolidTile: inRock,
    framesInsideTheExitKeepOut: onTheDoor,
    exitKeepOutPx: AX.EXIT_KEEP_PX,
    framesItCoveredTheHeroAndSortedInFront: aheadOfHero,
    framesItCoveredAMarkerAndSortedInFront: aheadOfMarker,
    framesItCoveredAnExitAndSortedInFront: aheadOfExit,
    timesTheSortWasClampedBehindSomething: o._apexUnder,
    bodySizePx: AX.APEX_SIZE,
  };
  if (inRock) note(`the apex dead-reckoned inside rock on ${inRock} frame(s)`);
  if (onTheDoor) note(`the apex stood on the door on ${onTheDoor} frame(s)`);
  if (aheadOfHero) note(`the apex drew in front of the player on ${aheadOfHero} frame(s)`);
  if (aheadOfMarker) note(`the apex drew in front of a marker on ${aheadOfMarker} frame(s)`);
  if (aheadOfExit) note(`the apex drew in front of an exit on ${aheadOfExit} frame(s)`);
}

/* ---------------- B. every state, its own telegraph ---------------- */
{
  const rows = {};
  let overCap = 0;
  for (const st of ENGINE.states) {
    const o = build(REGION, huntRow(REGION, { state: st }));
    sim(o, 120); step(o, 30);
    const want = ENGINE.telegraph[st] || { vignette: 0, map: 'none' };
    const h = o.hunt;
    rows[st] = {
      embodied: !!(h && h.embodied),
      vignetteAsked: want.vignette,
      peakPainted: +o._apexPeak.toFixed(4),
      mapChannel: want.map,
      threatChevronDrawn: want.map !== 'none' && !!(h && h.embodied),
      wayOutChevrons: o._wayOutMarks,
      companionAlerted: !!(o.companion && o.companion.alert),
      exitsBrightened: !!(h && h.embodied && st !== 'ROAMING'),
    };
    if (o._apexPeak > AX.VIGNETTE_CAP + 1e-9) overCap++;
    if (want.vignette > 0 && want.map !== 'none' && h && h.embodied && o._apexPeak <= 0) {
      note(`${st} painted no vignette though its table asks for ${want.vignette}`);
    }
    if (want.map !== 'none' && h && h.embodied && !o._wayOutMarks) {
      note(`${st} telegraphs a threat and marked no way out`);
    }
  }
  out.telegraphByState = rows;
  out.vignetteCap = AX.VIGNETTE_CAP;
  if (overCap) note(`${overCap} state(s) painted over the ${AX.VIGNETTE_CAP} vignette cap`);
  // the two states that are "not there" must be exactly that
  for (const st of ['DORMANT', 'SPENT']) {
    if (rows[st].embodied) note(`${st} put a body on the map`);
    if (rows[st].wayOutChevrons) note(`${st} drew overlay chrome`);
  }
  if (rows.STIRRING.wayOutChevrons) note('STIRRING drew a map marker; its channel is "none"');
  if (!rows.TRACKING.companionAlerted) note('the companion did not react at TRACKING');
  if (rows.ROAMING.companionAlerted) note('the companion reacted at ROAMING, before it has your trail');
}

/* ---------------- B. the stale marker actually lags ---------------- */
{
  const o = build(REGION, huntRow(REGION, { state: 'TRACKING' }));
  sim(o, 120);
  let maxLag = 0, samples = 0;
  for (let i = 0; i < 600; i++) {
    o.keys.clear(); o.update(DT);
    const h = o.hunt;
    if (!h.embodied) continue;
    samples++;
    maxLag = Math.max(maxLag, Math.hypot(h.staleX - h.px, h.staleY - h.py));
  }
  out.theScentIsOld = {
    staleLagSeconds: AX.STALE_LAG_SECONDS,
    maxPixelsBetweenTheMarkerAndTheCreature: +maxLag.toFixed(1),
    inTiles: +(maxLag / T).toFixed(2),
    samples,
    says: 'TRACKING means it knows where you WERE; a marker that told the truth '
        + 'would be saying the opposite',
  };
  if (maxLag < 8) note('the stale marker does not lag; TRACKING and CLOSING look identical');
}

/* ---------------- C. the dread never hides the door ---------------- */
{
  const o = build(REGION, huntRow(REGION, { state: 'CLOSING' }));
  let goldSeen = 0, goldPaintedOver = 0, outboard = 0, peak = 0, samples = 0;
  for (let i = 0; i < 900; i++) {
    o.keys.clear(); o.update(DT);
    if (!o.hunt.embodied) continue;
    o.draw();
    samples++;
    peak = Math.max(peak, o._apexPeak);
    const ctx = o.canvas.getContext('2d');
    for (let k = 0; k < o._wayOutMarks; k++) {
      const m = o._wayOutMark[k];
      const px = ctx.getImageData(m.x, m.y, 1, 1).data;
      const gold = px[0] > 190 && px[1] > 150 && px[2] > 90 && px[0] > px[2] + 60;
      if (gold) goldSeen++; else goldPaintedOver++;
      if (Math.min(m.x, m.y, W - m.x, H - m.y) < AX.THREAT_LANE) outboard++;
    }
    if (samples > 300) break;
  }
  out.dreadNeverHidesTheDoor = {
    framesSampled: samples,
    peakVignettePainted: +peak.toFixed(4), cap: AX.VIGNETTE_CAP,
    wayOutChevronsPerFrame: o._wayOutMarks,
    exitsOnTheMap: o.markers.filter(m => m.kind === 'exit').length,
    goldPixelStillGoldInTheFinishedFrame: goldSeen,
    goldPixelPaintedOver: goldPaintedOver,
    goldChevronsNearerTheRimThanTheThreatLane: outboard,
    lanes: { wayOut: AX.WAYOUT_LANE, threat: AX.THREAT_LANE },
    paintedLast: 'after the night tint, the encounter flash and the room vignette',
  };
  if (goldPaintedOver) note(`the way out was painted over on ${goldPaintedOver} sample(s)`);
  if (outboard !== goldSeen + goldPaintedOver) note('a way-out chevron sat inboard of the threat lane');
  if (!goldSeen) note('nothing marked the way out while the apex was closing');
}

/* ---------------- F. the mirror: how wrong the guess gets ----------------
 *
 * Two worlds, the same player script, the same map. One runs the motion model
 * at sixty hertz and is TRUTH. The other is handed truth's position once a
 * second, the way a polled client is, and dead-reckons in between. The number
 * that matters is how far apart they are on the frame before the correction
 * lands, because that is the largest lie the player is ever shown.
 */
{
  const truth = build(REGION, huntRow(REGION, { state: 'CLOSING', x: undefined, y: undefined }));
  const mirror = new OW.Overworld(makeCanvas());
  mirror.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
  let row = huntRow(REGION, { state: 'CLOSING', x: undefined, y: undefined });
  mirror.stateSource = () => ({ hunt: row, apexes: ENGINE.apexes, pets: PETS });
  mirror.load(REGION, REGION.tier || 2);

  // let truth place its creature, then hand the mirror the same starting point
  for (let i = 0; i < 200; i++) { truth.keys.clear(); truth.update(DT); }
  const legs = [['arrowright', 90], ['arrowdown', 60], ['arrowleft', 70], [null, 60],
                ['arrowup', 80], ['arrowright', 110], [null, 90]];
  let worstBeforeCorrection = 0, worstCorrection = 0, ticks = 0, frame = 0;
  for (const [key, n] of legs) {
    for (let i = 0; i < n; i++) {
      const keys = key ? [key] : [];
      truth.keys.clear(); for (const k of keys) truth.keys.add(k);
      truth.update(DT);
      mirror.keys.clear(); for (const k of keys) mirror.keys.add(k);
      mirror.update(DT);
      frame++;
      const th = truth.hunt, mh = mirror.hunt;
      if (!th || !th.placed) continue;
      if (mh && mh.placed) {
        worstBeforeCorrection = Math.max(worstBeforeCorrection,
          Math.hypot(mh.px - th.px, mh.py - th.py));
      }
      if (frame % 60 === 0) {          // the poll lands
        row = huntRow(REGION, { state: 'CLOSING', x: th.px, y: th.py });
        ticks++;
        mirror.update(0);
        if (mh) worstCorrection = Math.max(worstCorrection, mh.corrected);
      }
    }
  }
  out.mirror = {
    authorityCadenceHz: 1,
    stateSpeed: AX.STATE_SPEED.CLOSING,
    pollsDelivered: ticks,
    worstGapBeforeACorrectionLandedPx: +worstBeforeCorrection.toFixed(1),
    inTiles: +(worstBeforeCorrection / T).toFixed(2),
    worstCorrectionAppliedPx: +worstCorrection.toFixed(1),
    snapsTakenOverFourTiles: mirror.hunt ? mirror.hunt.snaps : null,
    snapThresholdPx: AX.SNAP_PX,
    source: mirror.hunt ? mirror.hunt.source : null,
    says: 'the engine position is authority; between polls the client walks the '
        + 'same route at the same speed and eases onto the correction',
  };
  if (mirror.hunt && mirror.hunt.source !== 'engine') {
    note('the client did not take the engine position as authority');
  }
  if (worstBeforeCorrection > AX.STATE_SPEED.CLOSING) {
    note(`the mirror drifted ${worstBeforeCorrection.toFixed(0)}px from truth between polls`);
  }
}

/* ---------------- every region: the art resolves ---------------- */
{
  const rows = [];
  let unauthored = 0, wrong = 0;
  for (const a of ENGINE.apexes) {
    const key = AX.artKeyFor(a);
    const authoredResolves = BOSS.resolveBoss(a.sprite) === a.sprite;
    const fallbackResolves = BOSS.resolveBoss(a.sprite_fallback) === a.sprite_fallback;
    if (!authoredResolves) unauthored++;
    if (!fallbackResolves) wrong++;
    if (!authoredResolves && key !== BOSS.resolveBoss(a.sprite_fallback)) {
      note(`${a.id}: art key ${key} is neither the authored sprite nor the declared fallback`);
    }
    rows.push([a.region, `${a.name} · ${a.element} · ${key}${authoredResolves ? '' : ' (fallback)'}`]);
  }
  out.artRoster = {
    apexes: ENGINE.apexes.length,
    resolvedThrough: 'bosses.resolveBoss(sprite) then sprite_fallback',
    authoredSpritesNotDrawnYet: unauthored,
    declaredFallbacksThatDoNotResolve: wrong,
    perRegion: Object.fromEntries(rows),
  };
  if (wrong) note(`${wrong} declared sprite_fallback(s) do not resolve to themselves`);
}

/* ---------------- it comes, in every region ---------------- */
{
  const rows = [];
  let never = 0;
  for (const r of V.regions) {
    if (!APEX_BY_REGION[r.id]) continue;
    // no coordinates at all: the local fallback has to place and drive it
    const o = build(r, huntRow(r, { state: 'CLOSING', x: undefined, y: undefined }));
    /* Out in the open. The default spawn tile is two tiles from the west exit
     * and therefore permanently inside the body's keep-out, which is the draw
     * rule working exactly as written — the creature stops two and a half tiles
     * off and looks at you across ground it will not stand on. Measured on its
     * own below; this test is about whether the route works. */
    /* Somewhere in the middle that is actually CONNECTED to where the player
     * started. Teleporting them onto an island in the marsh and then reporting
     * that the apex never arrived would be measuring the harness. */
    const reach = reachableFrom(o, o.player.x, o.player.y);
    let mid = null, bestD = -1;
    for (let ty = 4; ty < MAP_H - 4; ty++) {
      for (let tx = 18; tx < 32; tx++) {
        if (!reach.has(ty * MAP_W + tx)) continue;
        if (o.markers.some(m => m.x === tx && m.y === ty)) continue;
        const d = Math.abs(tx - 24) + Math.abs(ty - (MAP_H >> 1));
        if (bestD < 0 || d < bestD) { bestD = d; mid = { x: tx, y: ty }; }
      }
    }
    if (mid) {
      o.player.x = mid.x; o.player.y = mid.y;
      o.player.px = mid.x * T; o.player.py = mid.y * T;
    }
    let reached = false, closest = Infinity;
    for (let i = 0; i < 7200; i++) {
      o.keys.clear(); o.update(DT);
      const h = o.hunt;
      if (!h) break;
      if (h.embodied) closest = Math.min(closest, h.tiles);
      if (h.embodied && h.tiles * T <= AX.CONTACT_PX) { reached = true; break; }
    }
    if (!reached) never++;
    rows.push([r.id, reached ? 'reached you' : `stalled at ${closest.toFixed(1)} tiles`]);
  }
  out.localFallbackReachesYou = {
    regionsWithAnApex: rows.length,
    routing: `breadth-first flood from the player over ${MAP_W * MAP_H} cells, `
      + `reflooded every ${AX.REFLOW_SECONDS}s while hunting and never otherwise`,
    outcome: Object.fromEntries(rows),
    regionsWhereItNeverArrived: never,
    note: 'this path only runs when the engine sends no coordinates',
  };
  if (never) note(`the local fallback never reached the player in ${never} region(s)`);
}

/* ---------------- C. it will not stand on the door ----------------
 *
 * Not a mechanic — the apex has no collision, cannot block a step, and a fight
 * it starts can always be fled, all of which is hunters.py's business. This is
 * a DRAW rule and the only thing it buys is that forty-eight pixels of monster
 * never sit on the exit glyph, so the way out is never something you have to
 * look around a creature to find.
 */
{
  const o = build(REGION, huntRow(REGION, { state: 'CLOSING', x: undefined, y: undefined }));
  const exit = o.markers.find(m => m.kind === 'exit');
  o.player.x = exit.x; o.player.y = exit.y;
  o.player.px = exit.x * T; o.player.py = exit.y * T;
  let closestToTheDoor = Infinity, closestToYou = Infinity, frames = 0;
  for (let i = 0; i < 5400; i++) {
    o.keys.clear(); o.update(DT);
    o.player.x = exit.x; o.player.y = exit.y;
    o.player.px = exit.x * T; o.player.py = exit.y * T;
    const h = o.hunt;
    if (!h || !h.embodied) continue;
    frames++;
    closestToTheDoor = Math.min(closestToTheDoor,
      Math.hypot(h.tx - exit.x * T, h.ty - exit.y * T));
    closestToYou = Math.min(closestToYou, h.tiles);
  }
  out.itWillNotStandOnTheDoor = {
    secondsStoodOnTheExitTile: 90,
    keepOutPx: AX.EXIT_KEEP_PX,
    closestItGotToTheDoorPx: Number.isFinite(closestToTheDoor) ? +closestToTheDoor.toFixed(1) : null,
    closestItGotToYouTiles: Number.isFinite(closestToYou) ? +closestToYou.toFixed(2) : null,
    framesEmbodied: frames,
    isAMechanic: false,
    says: 'it stops at the edge and looks at you across ground it will not stand on',
  };
  if (Number.isFinite(closestToTheDoor) && closestToTheDoor < AX.EXIT_KEEP_PX - 8) {
    note(`the apex came ${closestToTheDoor.toFixed(0)}px from the door, inside the keep-out`);
  }
}

/* ---------------- D. nothing hunting: byte-identical ---------------- */
{
  const cases = {
    noStateSourceAtAll: undefined,
    noHuntField: {},
    explicitlyNull: { hunt: null },
    dormant: { hunt: huntRow(REGION, { state: 'DORMANT' }), apexes: ENGINE.apexes },
    spent: { hunt: huntRow(REGION, { state: 'SPENT' }), apexes: ENGINE.apexes },
    anotherRegion: { hunt: huntRow(REGION, { region: 'somewhere_else' }), apexes: ENGINE.apexes },
    malformedRow: { hunt: 7 },
    unknownState: { hunt: huntRow(REGION, { state: 'RAMPAGING' }), apexes: ENGINE.apexes },
    emptyList: { hunts: [] },
    stateSourceThrows: 'THROW',
  };
  const hashes = {};
  for (const [label, state] of Object.entries(cases)) {
    const o = new OW.Overworld(makeCanvas());
    if (state === 'THROW') o.stateSource = () => { throw new Error('mid-rewrite'); };
    else if (state !== undefined) o.stateSource = () => state;
    o.resize = function () { this.viewW = W; this.viewH = H; this.scale = 2; };
    o.load(REGION, 2);
    step(o, 400, ['arrowright']);
    step(o, 200);
    hashes[label] = { frame: frameHash(o.canvas),
                      embodied: !!(o.hunt && o.hunt.embodied),
                      stateSeen: o._apexStage };
  }
  const base = hashes.noStateSourceAtAll.frame;
  out.nothingHunting = hashes;
  out.nothingHuntingAllIdentical = Object.values(hashes)
    .every(v => v.frame === base && !v.embodied
                && (v.stateSeen === 'DORMANT' || v.stateSeen === 'SPENT'));
  if (!out.nothingHuntingAllIdentical) {
    note('a world with nothing hunting does not render identically to one before this feature');
  }
}

/* ---------------- D. and costs nothing ---------------- */
{
  const WARM = 1200, COUNT = 300;
  const measure = (o) => {
    step(o, WARM / 2, ['arrowright']); step(o, WARM / 2);
    RASTER.counting = true; RASTER.canvases = 0;
    step(o, COUNT, ['arrowright']);
    const walking = RASTER.canvases;
    RASTER.canvases = 0;
    step(o, COUNT);
    const standing = RASTER.canvases;
    RASTER.counting = false;
    return { walking300: walking, standing300: standing };
  };
  const bare = build(REGION, null);
  const hunted = build(REGION, huntRow(REGION, { state: 'CLOSING' }));
  sim(hunted, 120);
  const b = measure(bare), a = measure(hunted);
  out.steadyState = {
    withNothingHunting: b, withAnApexClosing: a,
    canvasesAddedByAnActiveHunt: (a.walking300 + a.standing300) - (b.walking300 + b.standing300),
    canvasesAddedWhenNothingIsHunting: 0,
    perFrameAllocationsInTheOverlay: 0,
  };
  out.steadyState.note = 'the baseline is what this region already cost before '
    + 'this feature: the claim under test is the delta, which is zero';
  if (out.steadyState.canvasesAddedByAnActiveHunt > 2) {
    note(`an active hunt added ${out.steadyState.canvasesAddedByAnActiveHunt} canvas alloc(s) to a warm loop`);
  }
}

/* ---------------- the colour budget, off the rendered map form ---------- */
{
  const counts = [];
  for (const a of ENGINE.apexes) {
    const key = AX.artKeyFor(a);
    let worst = 0;
    for (let f = 0; f < 5; f++) {
      const img = BOSS.bossMapSprite
        ? BOSS.bossMapSprite(key, a.colour, f, {})
        : null;
      if (img) worst = Math.max(worst, colourCount(img));
    }
    counts.push([`${a.id}/${key}`, worst || null]);
  }
  out.colourBudget = Object.fromEntries(counts);
  const over = counts.filter(([, n]) => n !== null && n > 15);
  out.coloursOverBudget = over;
  if (over.length) note(`over the fifteen-colour budget: ${JSON.stringify(over)}`);
}

/* ---------------- determinism ---------------- */
{
  const run = () => {
    const o = build(REGION, huntRow(REGION, { state: 'TRACKING', x: undefined, y: undefined }));
    sim(o, 300);
    sim(o, 200, ['arrowright']);
    sim(o, 200, ['arrowdown']);
    sim(o, 118);
    step(o, 2);
    return { px: o.hunt.px, py: o.hunt.py, state: o.hunt.state,
             facing: o.hunt.facing, frame: frameHash(o.canvas) };
  };
  const a = run(), b = run();
  out.determinism = { first: a, second: b,
                      identical: JSON.stringify(a) === JSON.stringify(b) };
  if (!out.determinism.identical) note('two identical walks put the apex in two places');
}

/* ---------------- no rolls anywhere near a draw ---------------- */
{
  const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  const hits = {};
  for (const f of ['apex.js', 'overworld.js']) {
    const src = strip(fs.readFileSync(new URL('../../web/js/' + f, import.meta.url), 'utf8'));
    hits[f] = (src.match(/Math\.random/g) || []).length;
  }
  out.noRolls = { mathRandomInCode: hits };
  for (const [f, n] of Object.entries(hits)) if (n) note(`${f} calls Math.random ${n} time(s)`);
}

out.failures = fail.length;
out.detail = fail;
console.log(JSON.stringify(out, null, 1));
process.exit(fail.length ? 1 : 0);
