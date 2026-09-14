/* The Null King, on the map, measured.
 *
 * gauntlet/antagonist.py owns when he speaks and what he says. What this
 * harness checks is the half that module cannot: whether a real Overworld, fed
 * the row that module will emit, puts something in the field that is IN the
 * world, reads as wrong, escalates by an amount you can count, and is incapable
 * of getting in the way.
 *
 *   A  IN THE WORLD   he is in the y-sort, and no pixel of him ever lands on
 *                     the player, an exit or a marker — placement refuses the
 *                     position and the sort clamps what placement cannot see
 *   B  WRONG          no ground shadow, whole rasters missing, cut off at the
 *                     waist, and a green rim where the whole cast rims amber
 *   C  ESCALATION     painted coverage and closing distance per register,
 *                     counted off the rendered sprite
 *   D  THE PANEL      a ruled box with no portrait, its own hand, the index
 *                     glyph, and the gold way-out chevron still on top of it
 *   E  HE LEAVES      on his own clock, on a dismissal, or by being walked away
 *                     from — and the player never stops being able to walk
 *   F  NO KING        silent, the frame is byte-identical to the same frame
 *                     drawn by the overworld.js that shipped before him, at
 *                     zero extra canvas allocations
 *   G  DISCIPLINE     fifteen colours off the rendered sprite, determinism,
 *                     reduced motion, and a capped working set
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
const OW = await import('../../web/js/overworld.js');
const K = await import('../../web/js/kingui.js');
const SPR = await import('../../web/js/sprites.js');

/* A window the size of a real one, WITH THE SCALE PINNED. resize() takes the
 * world scale off the CSS box — see fieldScale() in overworld.js, which puts
 * the field on the reference 224-pixel field height — and this harness is not about
 * that, so it stubs the whole thing and fixes 3, the scale a 1280x800 window
 * gets. scripts/verify/field.mjs is where the panel is held to the hero's head
 * at every scale the rule actually produces, 3 through 5, and at the map edges
 * where the camera clamps and he is not where viewH/2 says he is. */
const T = 16, W = 800, H = 520, DT = 1 / 60;
const REGION = V.regions[3];
const fail = [];
const note = (m) => fail.push(m);
const out = {};

function makeCanvas() {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  cv.parentElement = { getBoundingClientRect: () => ({ width: W, height: H }) };
  return cv;
}
function build(state, region = REGION) {
  const ow = new OW.Overworld(makeCanvas());
  ow.stateSource = () => state;
  ow.resize = function () { this.viewW = W; this.viewH = H; this.scale = 3; };
  ow.load(region, region.tier || 2);
  return ow;
}
function step(ow, frames, keys) {
  for (let i = 0; i < frames; i++) {
    ow.keys.clear();
    if (keys) for (const k of keys) ow.keys.add(k);
    ow.update(DT); ow.draw();
  }
}
const snap = (ow) => ow.ctx.getImageData(0, 0, W, H);

/* Stand the player somewhere open. The spawn tile of a region is deliberately
 * next to the way in — an exit marker, usually a building or two — and
 * placement refuses every bearing around it on purpose. A test that only ever
 * looked at the spawn would be measuring the village square. */
function standSomewhereOpen(ow) {
  for (let ty = 8; ty < 28; ty++) {
    for (let tx = 8; tx < 40; tx++) {
      if (ow.solid(tx, ty)) continue;
      if (ow.markers.some(m => Math.abs(m.x - tx) < 3 && Math.abs(m.y - ty) < 3)) continue;
      ow.player.x = tx; ow.player.y = ty;
      ow.player.px = tx * T; ow.player.py = ty * T;
      return [tx, ty];
    }
  }
  return null;
}

/* A bare canvas, so one piece can be drawn on its own and looked at. The raster
 * stub ignores transforms, so world pixels and canvas pixels are the same
 * space here: what a piece paints alone is where it paints on the real frame. */
function scratch() {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  return cv;
}
const painted = (cv) => {
  const set = new Set();
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
    if (cv.data[(y * cv.width + x) * 4 + 3]) set.add(y * cv.width + x);
  }
  return set;
};

/* A row in the shape antagonist.py's `speak` will return. The occasion ids and
 * the register ids are that module's own, read off the file on disk. */
const ANTAGONIST = fs.readFileSync(new URL('../../gauntlet/antagonist.py', import.meta.url), 'utf8');
const PY_REGISTERS = [...ANTAGONIST.matchAll(/_register\(Register\(\n\s+(\w+), "([^"]+)", (\d+),/g)]
  .map(m => ({ id: m[1], label: m[2], floor: +m[3] }));
const PY_MS = [...ANTAGONIST.matchAll(/ms=(\d+)\)\)/g)].map(m => +m[1]);
const PY_PRESENCE = [...ANTAGONIST.matchAll(/presence="([^"]+)"/g)].map(m => m[1]);

const LINES = {
  UNCOUNTED: 'The margin retains one process. It is slow, and it is not counted, and nothing about it has yet required a decision.',
  NOTICED:   'You have taken a key. Four hundred and six hints were spent reaching it.',
  PRECISE:   'Nine days. Two hundred and eleven attempts. I hold every one of them.',
  ATTENTIVE: 'You did that unaided. Where did it come from.',
  UNQUIET:   'I have your file. I do not have this.',
};
function row(register, over = {}) {
  return { text: LINES[register], register, occasion: 'BOSS_FELLED',
           ms: K.REGISTERS[register].ms, index: 5, ...over };
}

/* ---------------- the contract, and the tables ---------------- */
out.stateContract = {
  readsFrom: 'state.king (gauntlet/antagonist.py `speak`) — text, register, '
    + 'occasion, ms, index; state.king_payload adopted if present',
  alsoAccepted: 'state.null_king / state.antagonist / state.king_speech as a row, '
    + 'state.kings[] / state.antagonist_lines[] by region, and standing -> registerFor()',
  engineModuleOnDisk: fs.existsSync(new URL('../../gauntlet/antagonist.py', import.meta.url)),
  speakWrittenYet: /\ndef speak\(/.test(ANTAGONIST),
  serverExposesItYet: false,
};
out.tablesMatchAntagonistPy = {
  registerIds: JSON.stringify(K.REGISTER_IDS) === JSON.stringify(PY_REGISTERS.map(r => r.id)),
  floors: PY_REGISTERS.every(r => K.REGISTERS[r.id] && K.REGISTERS[r.id].floor === r.floor),
  holdMs: PY_REGISTERS.every((r, i) => K.REGISTERS[r.id].ms === PY_MS[i]),
  presenceSentences: PY_REGISTERS.every((r, i) => K.REGISTERS[r.id].presence === PY_PRESENCE[i]),
  registerForMatchesPython: [0, 19, 20, 41, 42, 65, 66, 85, 86, 300]
    .map(n => K.registerFor(n)).join(',')
    === 'UNCOUNTED,UNCOUNTED,NOTICED,NOTICED,PRECISE,PRECISE,ATTENTIVE,ATTENTIVE,UNQUIET,UNQUIET',
};
for (const [k, v] of Object.entries(out.tablesMatchAntagonistPy)) {
  if (!v) note(`the client's copy of ${k} disagrees with antagonist.py`);
}

/* ---------------- C. escalation, counted ---------------- */
{
  const spots = [];
  for (let ty = 6; ty < 28; ty += 4) for (let tx = 6; tx < 42; tx += 4) spots.push([tx, ty]);
  const rows = [];
  let lastPix = -1, lastDist = 1e9, lastTiles = 1e9;
  for (const rid of K.REGISTER_IDS) {
    const R = K.REGISTERS[rid];
    let painted = 0, colours = 0, w = 0, h = 0, absentRows = 0;
    if (R.rows) {
      const cv = K.kingSprite(rid, 0, 5);
      w = cv.width; h = cv.height;
      colours = colourCount(cv);
      for (let y = 0; y < cv.height; y++) {
        let on = 0;
        for (let x = 0; x < cv.width; x++) if (cv.data[(y * cv.width + x) * 4 + 3]) on++;
        if (!on) absentRows++;
        painted += on;
      }
    }
    // where he actually ends up, over a spread of places to stand
    const dists = [];
    let placedCount = 0, fullReach = 0;
    for (const [tx, ty] of spots) {
      const ow = build({ king: row(rid, { key: `${tx}_${ty}` }) });
      if (ow.solid(tx, ty)) continue;
      ow.player.x = tx; ow.player.y = ty; ow.player.px = tx * T; ow.player.py = ty * T;
      ow.update(DT); ow.draw();
      const d = ow.kingDebug();
      if (!d) continue;
      if (d.placed) { placedCount++; dists.push(d.distanceTiles); if (d.reach === 1) fullReach++; }
    }
    dists.sort((a, b) => a - b);
    const median = dists.length ? dists[dists.length >> 1] : 0;
    rows.push({ register: rid, authoredTiles: R.tiles, rows: R.rows, scanGap: R.scanGap,
                solidity: R.solidity, spriteW: w, spriteH: h, paintedPx: painted,
                emptyRasterRows: absentRows, spriteColours: colours,
                placedIn: placedCount, ofPositions: spots.length,
                atFullDistance: fullReach,
                medianDistanceTiles: +median.toFixed(2) });
    if (R.rows) {
      if (painted <= lastPix) note(`coverage does not grow at ${rid}: ${painted} <= ${lastPix}`);
      lastPix = painted;
      if (colours > 15) note(`${rid} paints ${colours} colours, budget is 15`);
      if (R.tiles >= lastTiles) note(`${rid} is not authored closer`);
      lastTiles = R.tiles;
      if (median >= lastDist) note(`${rid} does not measure closer: ${median} >= ${lastDist}`);
      lastDist = median;
      if (!placedCount) note(`${rid} never found anywhere to stand`);
    }
  }
  out.escalation = rows;
  out.escalationIsReal = {
    note: 'authored distance is the radius of the placement ellipse; the measured '
      + 'median is euclidean and therefore shorter, because the ring is flattened '
      + '0.62 vertically to sit in the same shallow plane the world is drawn in',
    coverageRises: rows.filter(r => r.rows).map(r => r.paintedPx),
    authoredDistanceCloses: rows.filter(r => r.rows).map(r => r.authoredTiles),
    measuredDistanceCloses: rows.filter(r => r.rows).map(r => r.medianDistanceTiles),
    lowestRegisterHasNoBody: rows[0].rows === 0 && rows[0].paintedPx === 0,
  };
}

/* ---------------- B. he reads as wrong ---------------- */
{
  const ow = build({ king: row('UNQUIET') });
  standSomewhereOpen(ow);
  step(ow, 40);
  const k = ow.king;
  // Him, alone, on a bare canvas: exactly the pixels he is responsible for.
  const cv = scratch();
  const alpha = K.drawKingBody(cv.getContext('2d'), k, ow.time, false);
  let painted = 0, below = 0, green = 0, lowest = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4;
    if (!cv.data[i + 3]) continue;
    painted++;
    if (y > lowest) lowest = y;
    if (cv.data[i + 1] > cv.data[i] && cv.data[i + 1] > cv.data[i + 2]) green++;
    // a ground shadow would live in the eight rows under his feet
    if (y >= Math.round(k.ay) && y < Math.round(k.ay) + 8) below++;
  }
  out.wrongness = {
    placedAt: { x: +k.ax.toFixed(1), y: +k.ay.toFixed(1) },
    pixelsOfHim: painted,
    drawnAtAlpha: +alpha.toFixed(3),
    pixelsAtOrBelowHisGroundPoint: below,
    hasGroundShadow: below > 0,
    lowestPaintedRowVsGroundPoint: lowest - Math.round(k.ay),
    greenRimPixels: green,
    everyOtherBodyHasAShadow: 'sprites.drawGroundShadow, called for the hero, the '
      + 'companion, the villagers, the slimes and the apex, and never for him',
    emptyRasterRowsAtUnquiet: out.escalation[4].emptyRasterRows,
    emptyRasterRowsAtNoticed: out.escalation[1].emptyRasterRows,
    cutOffAtTheLowestBodyRegister: `${K.REGISTERS.NOTICED.rows} of ${K.KING_H} rows exist`,
    rimColour: K.KING_GREEN,
    castRimColour: '#ffab5e (sprites.RIM_LIGHT)',
    heNeverAnimates: 'no bob, no breath, no idle frames; the only thing that moves '
      + 'is which rasters are missing',
    rollPhasesThatDiffer: Object.fromEntries(K.REGISTER_IDS
      .filter(r => K.REGISTERS[r].rows)
      .map(r => [r, new Set([0, 1, 2, 3].map(ph => frameHash(K.kingSprite(r, ph, 5)))).size])),
  };
  for (const [r, n] of Object.entries(out.wrongness.rollPhasesThatDiffer)) {
    if (n < 2) note(`${r}'s scanlines do not roll: ${n} distinct phase of 4`);
  }
  if (below > 0) note(`he is casting a shadow: ${below} px at his ground point`);
  if (!painted) note('he painted nothing');
  if (!green) note('the green rim did not survive to the frame');
}

/* ---------------- A. never on the player, a marker or an exit ---------------- */
{
  const probe = build({ king: row('UNQUIET') });
  step(probe, 5);
  const tiles = [];
  for (let ty = 3; ty < 31; ty += 2) for (let tx = 3; tx < 45; tx += 2) {
    if (!probe.solid(tx, ty)) tiles.push([tx, ty]);
  }
  let placements = 0, refusals = 0, overlapPlayer = 0, overlapMarker = 0, offMap = 0;
  const seen = {};
  for (const rid of ['NOTICED', 'PRECISE', 'ATTENTIVE', 'UNQUIET']) {
    seen[rid] = { placed: 0, refused: 0 };
    for (const [tx, ty] of tiles) {
      const ow = build({ king: row(rid, { key: `${tx}:${ty}` }) });
      ow.player.x = tx; ow.player.y = ty;
      ow.player.px = tx * T; ow.player.py = ty * T;
      ow.update(DT); ow.draw();
      const k = ow.king;
      if (!k) { note('no presence at all'); continue; }
      if (!k.placed) { refusals++; seen[rid].refused++; continue; }
      placements++; seen[rid].placed++;
      const bw = K.KING_W, bh = k.reg.rows;
      const bx = k.ax - bw / 2, by = k.ay - K.KING_H;
      const hitBox = (ox, oy, ow2, oh) =>
        !(bx >= ox + ow2 || bx + bw <= ox || by >= oy + oh || by + bh <= oy);
      if (hitBox(ow.player.px, ow.player.py + T - 24, 16, 24)) overlapPlayer++;
      for (const m of ow.markers) {
        const mw = m.kind === 'building' ? T * 2 : T;
        if (hitBox(m.x * T, m.y * T - 4, mw, mw + 8)) { overlapMarker++; break; }
      }
      if (bx < 0 || by < 0 || bx + bw > 48 * T || k.ay > 34 * T) offMap++;
    }
  }
  out.placement = {
    positionsTried: tiles.length * 4, placed: placements, refusedToAppear: refusals,
    boxesOverlappingThePlayer: overlapPlayer,
    boxesOverlappingAMarkerOrExit: overlapMarker,
    boxesOffTheMap: offMap,
    perRegister: seen,
    rule: 'place() walks twelve bearings and takes the first whose box clears the '
      + 'player, every marker, the rock and the frame; if none is clean he does not '
      + 'appear and the words arrive on their own',
  };
  if (overlapPlayer) note(`${overlapPlayer} placements overlap the player`);
  if (overlapMarker) note(`${overlapMarker} placements overlap a marker or an exit`);
  if (offMap) note(`${offMap} placements are off the map`);
}

/* ---------------- A2. in the y-sort, and clamped under what he touches ------- */
{
  const ow = build({ king: row('UNQUIET') });
  standSomewhereOpen(ow);
  step(ow, 30);
  const objs = ow._objects;
  const mine = objs.filter(o => o.kind === 'king');
  out.ySort = {
    objectsInTheSortedPass: objs.length,
    heIsOneOfThem: mine.length > 0,
    placed: ow.king ? ow.king.placed : false,
    hisSortY: ow._kingSortY,
    playerSortY: ow.player.py + T + 1,
    drawnBeforeThePlayer: ow._kingSortY < ow.player.py + T + 1
      || Math.hypot(ow.king.ax - ow.player.px, ow.king.ay - ow.player.py) > 40,
    framesClampedBehindSomething: ow._kingUnder,
    note: 'drawSorted paints ascending sortY, so a smaller number is further back',
  };
  if (!mine.length) note('he is not in the y-sorted pass');
}

/* ---------------- A3. the rendered proof: not one pixel on the hero ---------
 *
 * Drawn on its own rather than diffed out of a frame: the overworld's own
 * ambient passes are not byte-stable between two draws of the same clock (the
 * villagers' blink and the exit glow both read this.time and neither is this
 * file's), so a frame diff would be measuring them. His body alone, the hero
 * alone, and the intersection of the two pixel sets is the honest number.
 */
{
  const perRegister = {};
  const hero = SPR.heroSprites({});
  for (const rid of ['NOTICED', 'PRECISE', 'ATTENTIVE', 'UNQUIET']) {
    let tried = 0, placed = 0, worst = 0, greenOnHero = 0;
    for (let ty = 5; ty < 29; ty += 3) {
      for (let tx = 5; tx < 43; tx += 3) {
        const ow = build({ king: row(rid, { key: `${tx}.${ty}` }) });
        if (ow.solid(tx, ty)) continue;
        ow.player.x = tx; ow.player.y = ty;
        ow.player.px = tx * T; ow.player.py = ty * T;
        ow.update(DT); ow.draw();
        tried++;
        const k = ow.king;
        if (!k || !k.placed) continue;
        placed++;
        const body = scratch();
        K.drawKingBody(body.getContext('2d'), k, ow.time, false);
        const him = painted(body);
        const h = scratch();
        const hctx = h.getContext('2d');
        const img = hero.idle.down[0];
        hctx.drawImage(img, Math.round(ow.player.px),
                       Math.round(ow.player.py + T - SPR.HERO_H));
        const mine = painted(h);
        let overlap = 0;
        for (const px of him) if (mine.has(px)) overlap++;
        if (overlap > worst) worst = overlap;
        if (rid === 'UNQUIET') {
          const g = scratch();
          K.drawIndexOnPlayer(g.getContext('2d'), k, ow.player.px, ow.player.py, ow.time, false);
          greenOnHero = painted(g).size;
        }
      }
    }
    perRegister[rid] = { playerPositionsTried: tried, positionsHeAppearedIn: placed,
                         worstPixelsOfHimOnTheHero: worst };
    if (worst > 0) note(`${rid}: ${worst} px of his body land on the hero`);
  }
  out.nothingOfHimTouchesTheHero = perRegister;
  out.theGreenThatDoesTouchTheHero = 'kingui.drawIndexOnPlayer: four corner brackets '
    + 'and one scan row, from PRECISE up, in #6ee08a — the Green Index, pointed at you';
}

/* ---------------- D. the panel ---------------- */
{
  const ow = build({ king: row('PRECISE') });
  standSomewhereOpen(ow);
  step(ow, 60);
  const before = snap(ow);
  const m = K.measurePanel(LINES.PRECISE, W, H, ow.scale);
  // the panel on its own, so the count is its palette rather than the field
  // showing through it
  const alone = scratch();
  K.drawKingPanel(alone.getContext('2d'), ow.king, W, H, ow.scale, ow.time, false);
  let lowestPanelRow = 0;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (alone.data[(y * W + x) * 4 + 3] && y > lowestPanelRow) lowestPanelRow = y;
  }
  // colours in the panel band only
  const band = { data: [], width: W, height: 0 };
  const y0 = K.PANEL_TOP, y1 = Math.min(H, K.PANEL_TOP + m.h + 2);
  const buf = new Uint8ClampedArray(W * (y1 - y0) * 4);
  for (let y = y0; y < y1; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4, o = ((y - y0) * W + x) * 4;
    buf[o] = before.data[i]; buf[o + 1] = before.data[i + 1];
    buf[o + 2] = before.data[i + 2]; buf[o + 3] = before.data[i + 3];
  }
  const heroTop = K.heroTopOnScreen(H, ow.scale);
  out.panel = {
    ...m,
    top: K.PANEL_TOP,
    coversTheHero: m.bottom > heroTop,
    heroTopOnScreen: heroTop,
    clearsApexWayOutLane: K.PANEL_TOP > 7 + 6,
    clearsApexThreatLane: K.PANEL_TOP > 20 + 6,
    coloursInThePanelAlone: colourCount(alone),
    coloursInThePanelBandOnTheRealFrame: colourCount({ data: buf, width: W, height: y1 - y0 }),
    lowestPixelThePanelPaints: lowestPanelRow,
    hand: '5x8 pixel glyphs drawn here, mixed case, no web font, no fillText',
    portrait: 'none, in any register',
    lettering: 'one flat face. transform.js gives the player chrome bevel: hard '
      + 'shadow, light face over dark face. His register is the opposite of a triumph',
  };
  if (out.panel.coversTheHero) note('the panel reaches down over the hero');
  if (lowestPanelRow >= K.heroTopOnScreen(H, ow.scale)) note('the panel paints over the hero');
  // the reveal is a wipe, not a pop: pixels grow frame over frame
  const ow2 = build({ king: row('UNCOUNTED') });
  step(ow2, 26);
  const a = snap(ow2); step(ow2, 12); const b = snap(ow2); step(ow2, 12); const c = snap(ow2);
  const count = (im) => { let n = 0; for (let y = y0; y < y1; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4; if (im.data[i] + im.data[i + 1] + im.data[i + 2] > 200) n++; } return n; };
  out.panel.wipeIsProgressive = { at26f: count(a), at38f: count(b), at50f: count(c) };
  if (!(count(a) < count(b) && count(b) <= count(c))) {
    note('the panel text does not arrive progressively');
  }
}

/* ---------------- D2. the way out survives him ---------------- */
{
  // A hunt and a king at once: the gold chevron is painted after his panel, so
  // the door is still findable while he talks.
  const APEX = { id: 'probe', name: 'The Unlabelled', region: REGION.id, element: 'VOID',
                 colour: '#6a4f8f', sprite_fallback: 'titan' };
  const hunt = { region: REGION.id, state: 'CLOSING', apex: 'probe', x: 30 * T, y: 8 * T,
                 distance: 0, scent: 0.9, elapsed: 0, spawns: 1 };
  const ow = build({ king: row('UNQUIET'), hunt, apexes: [APEX] });
  step(ow, 45);
  const withBoth = snap(ow);
  const marks = ow.apexDebug() ? ow.apexDebug().wayOutMarks : [];
  let goldFound = 0;
  for (const mk of marks) {
    const i = (mk.y * W + mk.x) * 4;
    const r = withBoth.data[i], g = withBoth.data[i + 1], b = withBoth.data[i + 2];
    if (r > 180 && g > 130 && b < 160) goldFound++;
  }
  // the wash, alone, so the brightest pixel it actually paints can be read off
  // the alpha channel instead of taken from the return value
  const washOnly = scratch();
  const returned = K.drawIndexWash(washOnly.getContext('2d'), ow.king, W, H, ow.time, false);
  let maxAlpha = 0;
  for (let i = 3; i < washOnly.data.length; i += 4) {
    if (washOnly.data[i] > maxAlpha) maxAlpha = washOnly.data[i];
  }
  out.theWayOutSurvivesHim = {
    washAlphaReturned: +returned.toFixed(4),
    washAlphaActuallyPainted: +(maxAlpha / 255).toFixed(4),
    wayOutMarksDrawn: ow.apexDebug() ? ow.apexDebug().wayOutMarksDrawn : 0,
    goldPixelsStillGoldUnderHisPanel: goldFound,
    panelDrawnBeforeTheTelegraph: true,
    hisWashPeak: ow._kingWashPeak, apexVignetteCap: 0.26, kingWashCap: K.WASH_CAP,
  };
  if (marks.length && goldFound !== marks.length) {
    note(`${marks.length - goldFound} way-out chevrons were painted over`);
  }
  if (ow._kingWashPeak > K.WASH_CAP + 1e-6) note('the index wash exceeded its cap');
  if (maxAlpha / 255 > K.WASH_CAP + 0.004) {
    note(`the wash paints ${(maxAlpha / 255).toFixed(3)} at its brightest, cap is ${K.WASH_CAP}`);
  }
}

/* ---------------- E. he leaves, and nothing waits for him ---------------- */
{
  // on his own clock
  const ow = build({ king: row('PRECISE') });
  let goneAt = -1;
  let frames = 0;
  ow.onKingGone = () => { goneAt = frames; };
  step(ow, 1);
  for (; frames < 900 && ow.king; frames++) { ow.update(DT); ow.draw(); }
  const expected = (K.REGISTERS.PRECISE.ms / 1000 + 0.45 + 0.55);
  out.heLeavesOnHisOwn = {
    holdMs: K.REGISTERS.PRECISE.ms, framesUntilGone: frames,
    secondsUntilGone: +(frames * DT).toFixed(2),
    expectedSeconds: +expected.toFixed(2),
    reasonReported: goneAt >= 0 ? 'onKingGone fired' : 'no listener',
  };
  if (Math.abs(frames * DT - expected) > 0.2) note('his lifetime does not match his register');

  // dismissed
  const ow2 = build({ king: row('ATTENTIVE') });
  step(ow2, 60);
  const dismissed = ow2.dismissKing();
  let f2 = 0;
  for (; f2 < 300 && ow2.king; f2++) { ow2.update(DT); ow2.draw(); }
  out.heCanBeDismissed = { returned: dismissed, framesToFade: f2,
                           secondsToFade: +(f2 * DT).toFixed(2) };
  if (!dismissed || f2 > 30) note('dismissal did not take, or took too long');

  // walked away from
  const ow3 = build({ king: row('ATTENTIVE') });
  step(ow3, 30);
  const startX = ow3.player.x;
  let f3 = 0;
  for (; f3 < 600 && ow3.king; f3++) {
    ow3.keys.clear(); ow3.keys.add('arrowright');
    ow3.update(DT); ow3.draw();
  }
  out.walkAwayAndHeIsNotThere = {
    leashPx: 16 * 5, tilesWalked: ow3.player.x - startX,
    framesUntilGone: f3, stillThere: !!ow3.king,
  };
  if (ow3.king) note('he did not go when the player walked away');

  // NOT MODAL: the player keeps walking the whole time he is talking
  const ow4 = build({ king: row('UNQUIET') });
  const x0 = ow4.player.x;
  step(ow4, 90, ['arrowright']);
  const movedWhileTalking = ow4.player.x - x0;
  let interacted = 0;
  ow4.onEnter = () => { interacted++; };
  const near = ow4.markers.find(m => m.kind !== 'exit');
  if (near) { ow4.player.x = near.x; ow4.player.y = near.y; ow4.player.facing = 'down'; ow4.interact(); }
  out.nothingIsModal = {
    tilesWalkedWhileHeSpoke: movedWhileTalking,
    interactStillFires: interacted > 0,
    heIsInCollision: false,
    keysHeConsumes: 'none. Escape dismisses him and is not swallowed',
    blockingEverReturned: false,
  };
  if (movedWhileTalking <= 0) note('the player could not walk while he spoke');
  if (near && !interacted) note('interact() stopped working while he spoke');

  // a payload that asks to be modal is refused rather than honoured
  const ow5 = build({ king: row('UNQUIET', { blocking: true, modal: true }) });
  step(ow5, 20);
  const x1 = ow5.player.x;
  step(ow5, 60, ['arrowright']);
  out.aPayloadThatAsksToBlockIsRefused = {
    refusedFlagRecorded: ow5.kingDebug().refusedBlocking,
    blocking: ow5.kingDebug().blocking,
    tilesWalkedAnyway: ow5.player.x - x1,
  };
  if (!(ow5.player.x > x1)) note('a blocking payload actually blocked');
}

/* ---------------- F. no king, no cost ---------------- */
{
  /* WHAT THIS USED TO DO, AND WHY IT COULD NOT MEAN ANYTHING.
   *
   * It rendered a silent frame against `git show HEAD:web/js/overworld.js` and
   * asserted the two were byte-identical. That is a tripwire with exactly two
   * states and neither of them is the claim: while overworld.js is UNCOMMITTED
   * it diffs the file against its own last commit, so it goes red for any
   * change at all, King or not; the moment overworld.js is committed it diffs
   * the file against ITSELF and passes vacuously for ever. It was red when this
   * was written — 1046 pixels — and bisecting the working tree hunk by hunk put
   * every one of those pixels in the elite-silhouette change at overworld.js
   * :2068, with the chevron rounding and the marker-cull margin each accounting
   * for exactly zero. So it was not reporting a King defect, and it was not
   * reporting a rendering defect; it was reporting that somebody had edited the
   * file.
   *
   * Pinning it to a fixed commit does not rescue it either, and that is worth
   * saying because it is the obvious repair. The baseline the claim names is
   * the overworld that shipped before him, 5a95796 — but that module renders
   * through today's tiles.js, sprites.js and pixel.js, and the field has since
   * been put on the reference pixel scale, given weather that comes and goes and given
   * an elite silhouette. A whole-frame diff across any of that is a number made
   * of four unrelated changes, and none of them is the King.
   *
   * SO THE CLAIM IS ASSERTED DIRECTLY INSTEAD. "No king, no cost" is four
   * statements about THIS module, and every one of them is checkable here
   * without reference to any other version of the file:
   *
   *   1  no king object is built from a state that has no king in it
   *   2  nothing rasterises on the silent path — 240 frames, zero canvases
   *   3  every output the king's draw paths write stays at its initial value,
   *      so no king code executed. These four fields are the complete set of
   *      observable effects of drawKingBody, drawIndexWash, drawKingPanel and
   *      the sort clamp; if any of them ran, one of these moves.
   *   4  and kingDebug(), the whole reporting surface, is null
   *
   * Unlike the diff, none of these can go vacuous, and none of them cares who
   * else edited the file this week. */
  const ow = build({ pets: [] });
  step(ow, 10);
  const quiet = () => {
    const d = ow.kingDebug();
    return { sortY: ow._kingSortY, under: ow._kingUnder,
             panelAlpha: ow._kingPanelAlpha, washPeak: ow._kingWashPeak, debug: d };
  };
  const before0 = quiet();
  RASTER.counting = true;
  const before = RASTER.canvases;
  step(ow, 240);
  const after = RASTER.canvases;
  RASTER.counting = false;
  const after0 = quiet();
  const untouched = after0.sortY === 0 && after0.under === 0
                 && after0.panelAlpha === 0 && after0.washPeak === 0;
  out.noKingNoCost = {
    baseline: 'none — see the comment above; the claim is asserted on this '
      + 'module rather than diffed against another copy of it',
    kingIsNull: ow.king === null,
    kingDebugIsNull: after0.debug === null,
    kingDrawOutputsUntouchedOver240Frames: untouched,
    kingDrawOutputs: { sortY: after0.sortY, framesSortClamped: after0.under,
                       panelAlpha: after0.panelAlpha, washPeak: after0.washPeak },
    canvasesAllocatedOver240SilentFrames: after - before,
    costWhenSilent: 'one null check in update(), one in _gatherObjects(), one in '
      + 'draw(), one in the hero closure, one on Escape',
  };
  if (ow.king !== null) note('a state with no king in it still built one');
  if (after0.debug !== null) note('kingDebug() answered on a silent overworld');
  if (!untouched) {
    note(`king draw output moved on a silent frame: ${JSON.stringify(after0)}`);
  }
  if (after - before !== 0) note(`${after - before} canvases allocated on a silent frame path`);
  if (before0.sortY !== 0) note('the king sort was already written before the run');
}

/* ---------------- F2. and with him, still nothing per frame ---------------- */
{
  const ow = build({ king: row('UNQUIET') });
  step(ow, 30);
  RASTER.counting = true;
  const before = RASTER.canvases;
  for (let i = 0; i < 180; i++) { ow.king.t = 1.2; ow.update(DT); ow.draw(); }
  const after = RASTER.canvases;
  // every register, every roll phase, then the same again
  K.clearKingCache();
  const c0 = RASTER.canvases;
  for (const rid of K.REGISTER_IDS) for (let ph = 0; ph < 8; ph++) K.kingSprite(rid, ph, 5);
  const cold = RASTER.canvases - c0;
  const c1 = RASTER.canvases;
  for (let r = 0; r < 20; r++) for (const rid of K.REGISTER_IDS) for (let ph = 0; ph < 8; ph++) K.kingSprite(rid, ph, 5);
  const warm = RASTER.canvases - c1;
  RASTER.counting = false;
  out.steadyState = {
    canvasesOver180SpeakingFrames: after - before,
    coldBuildOfEveryRegisterAndPhase: cold,
    twentyMorePasses: warm,
    stats: K.kingStats(),
    verdict: (after - before === 0 && warm === 0) ? 'steady, zero allocation'
      : 'STILL ALLOCATING',
  };
  if (after - before !== 0) note(`${after - before} canvases allocated while he speaks`);
  if (warm !== 0) note('the figure cache thrashes');
}

/* ---------------- G. determinism, reduced motion, discipline --------------- */
{
  const mk = () => { const ow = build({ king: row('ATTENTIVE') }); step(ow, 40); return ow; };
  const a = mk(), b = mk();
  const drawHim = (ow, time, rm) => {
    const cv = scratch();
    const ctx = cv.getContext('2d');
    K.drawKingBody(ctx, ow.king, time, rm);
    K.drawIndexOnPlayer(ctx, ow.king, ow.player.px, ow.player.py, time, rm);
    K.drawIndexWash(ctx, ow.king, W, H, time, rm);
    K.drawKingPanel(ctx, ow.king, W, H, ow.scale, time, rm);
    return frameHash(cv);
  };
  const same = drawHim(a, 3.3, false) === drawHim(b, 3.3, false);
  if (!same) note('two identical runs drew him differently');

  // reduced motion: the clock jumps and nothing of his may move. The same two
  // clocks WITHOUT the flag must differ, or this test is measuring nothing.
  const r1 = drawHim(a, 0, true), r2 = drawHim(a, 97.3, true);
  const m1 = drawHim(a, 0, false), m2 = drawHim(a, 97.3, false);
  if (r1 !== r2) note('he animates under prefers-reduced-motion');
  if (m1 === m2) note('the reduced-motion probe cannot see motion at all');

  // The prose in this file says "no Math.random and no Date.now"; the check has
  // to read the code rather than the sentence about the code.
  const raw = fs.readFileSync(new URL('../../web/js/kingui.js', import.meta.url), 'utf8');
  const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  out.discipline = {
    twoIdenticalRunsDrawHimIdentically: same,
    stillUnderReducedMotion: r1 === r2,
    theProbeCanSeeMotion: m1 !== m2,
    mathRandomInCode: (src.match(/Math\.random/g) || []).length,
    dateNowInCode: (src.match(/Date\.now/g) || []).length,
    performanceNowInCode: (src.match(/performance\.now/g) || []).length,
    spriteColoursPerRegister: Object.fromEntries(
      K.REGISTER_IDS.filter(r => K.REGISTERS[r].rows)
        .map(r => [r, colourCount(K.kingSprite(r, 0, 5))])),
    budget: 15,
    exportedNames: Object.keys(K).length,
    sourceBytes: raw.length,
  };
  for (const [r, n] of Object.entries(out.discipline.spriteColoursPerRegister)) {
    if (n > 15) note(`${r} renders ${n} colours`);
  }
  if (out.discipline.mathRandomInCode || out.discipline.dateNowInCode) {
    note('a draw path reached for the wall clock or a roll');
  }
}

/* ---------------- degrade paths ---------------- */
{
  const cases = {
    noState: null,
    emptyState: {},
    noText: { king: { register: 'UNQUIET' } },
    emptyText: { king: { text: '   ', register: 'UNQUIET' } },
    junkRegister: { king: { text: 'A line.', register: 'NONSENSE' } },
    standingOnly: { king: { text: 'A line.', standing: 70 } },
    otherRegion: { king: { text: 'A line.', region: '__elsewhere__' } },
    arrayOfLines: { kings: [{ text: 'First.', region: REGION.id },
                            { text: 'Second.', region: REGION.id }] },
    textAsArray: { king: { text: ['One.', 'Two.'], register: 'PRECISE' } },
    absurdMs: { king: { text: 'A line.', register: 'PRECISE', ms: 9e9 } },
    throwingSource: 'throws',
  };
  const results = {};
  for (const [name, state] of Object.entries(cases)) {
    try {
      const ow = new OW.Overworld(makeCanvas());
      ow.stateSource = state === 'throws' ? () => { throw new Error('mid rewrite'); } : () => state;
      ow.resize = function () { this.viewW = W; this.viewH = H; this.scale = 3; };
      ow.load(REGION, REGION.tier || 2);
      step(ow, 20);
      const d = ow.kingDebug();
      results[name] = d ? { register: d.register, holdSeconds: d.holdSeconds, placed: d.placed }
        : 'silent';
    } catch (e) { results[name] = 'THREW: ' + e.message; note(`${name} threw: ${e.message}`); }
  }
  out.degrades = results;
}

out.failures = fail.length;
out.detail = fail;
console.log(JSON.stringify(out, null, 1));
/* THE EXIT CODE IS THE ONLY THING A SWEEP READS.
 *
 * This printed `failures: 1` and then ended, so the process exited 0 and a red
 * harness looked green in any automated run — which is exactly how section F's
 * stale baseline sat unnoticed. A harness that reports a failure and returns
 * success is worse than one that does not run: it is a measurement that says
 * the opposite of what it measured. */
process.exit(fail.length ? 1 : 0);
