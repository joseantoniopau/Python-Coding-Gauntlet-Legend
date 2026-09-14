/* THE FIELD, ON THE REFERENCE PIXEL SCALE — measured.
 *
 * tiles.js uses the 16-pixel terrain tile. The old resize() rule selected
 * the scale using
 *
 *     floor(min(w / 340, h / 230))  clamped to 2..4
 *
 * off the CSS box, which put a 1280x800 window on scale 2 and showed 29.7 x
 * 23.5 tiles against the reference 16 x 14, with a hero 48 screen pixels tall
 * in a 753-pixel frame.
 *
 * WHAT THIS HARNESS IS FOR. The zoom itself is four lines and it either
 * multiplies or it does not. The part that needs measuring is everything the
 * zoom MOVES:
 *
 *   A  THE SCALE      an integer at every window size the game opens at, and
 *                     the visible rows within two of the fourteen-row reference
 *   B  THE CAMERA     centres the player, clamps at the map edge, shows no
 *                     void, and steps in whole world pixels so nothing judders
 *   C  THE PANEL      the King's words never reach the hero — and the ceiling
 *                     they are held to is his TRUE top on screen, which is not
 *                     viewH/2 while the camera is clamped
 *   D  THE LATTICE    every primitive the world layer paints lands on a whole
 *                     world pixel, because a half pixel is s screen pixels of
 *                     blur and s is now as high as 5
 *   E  THE OVERLAYS   the screen-space layers — apex telegraph, way-out
 *                     chevrons, the Unmaking's wash — stay inside the frame
 *                     and inside their own caps at every scale
 *   F  DISCIPLINE     deterministic at each scale, no canvases allocated in
 *                     the draw loop at the new scales
 *
 * The composite itself — what the four scaled layers actually look like once
 * multiplied — is NOT measured here and cannot be: raster.mjs treats scale()
 * and translate() as no-ops on purpose, so world pixels and canvas pixels are
 * the same space in this process. That claim is a screenshot's job.
 */
import { installRaster, RASTER, frameHash } from './raster.mjs';
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
const AX = await import('../../web/js/apex.js');
const SPR = await import('../../web/js/sprites.js');

const T = 16, MAP_W = 48, MAP_H = 34, DT = 1 / 60;
const WORLD_W = MAP_W * T, WORLD_H = MAP_H * T;
const REFERENCE_COLS = 16, REFERENCE_ROWS = 14;
const fail = [];
const note = (m) => fail.push(m);
const out = {};

/* THE FOUR WINDOWS, AND THE CANVAS EACH ONE ACTUALLY GIVES THE FIELD.
 * Not the window size: the field canvas is the flex child left over after the
 * topbar and the right-hand rail, and it is the box resize() measures. These
 * four pairs were read off the live game with playwright at devicePixelRatio 1,
 * one page per size — a harness that guessed them would be measuring its own
 * guess, which is the failure mode this project has already paid for once. */
const WINDOWS = [
  { win: [1280, 800],  css: [950, 753] },
  { win: [1440, 940],  css: [1110, 893] },   // the launcher's own window
  { win: [1600, 1000], css: [1270, 953] },
  { win: [1920, 1080], css: [1590, 1033] },
];

function makeCanvas(W, H) {
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  cv.parentElement = { getBoundingClientRect: () => ({ width: W, height: H }) };
  return cv;
}
/* The REAL resize() — not the stub every other harness installs. This one is
 * about resize(), so replacing it would be measuring nothing. */
function build(W, H, region = V.regions[3]) {
  const ow = new OW.Overworld(makeCanvas(W, H));
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

/* ------------------------------------------------- A. the scale, the table */

out.table = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const v = OW.fieldView(W, H);
  const ow = build(W, H);
  const row = {
    window: `${win[0]}x${win[1]}`, canvas: `${W}x${H}`,
    scale: v.scale, cols: +v.cols.toFixed(2), rows: +v.rows.toFixed(2),
    heroPx: v.heroPx, tilePx: T * v.scale,
  };
  out.table.push(row);

  if (!Number.isInteger(v.scale)) note(`${row.window}: scale ${v.scale} is not an integer`);
  if (v.scale !== ow.scale) note(`${row.window}: fieldView says ${v.scale}, resize() set ${ow.scale}`);
  /* THE FLOOR IS NOT THE MECHANISM. SCALE_MIN is 2, so the only thing keeping a
   * real window off the scale it was shipping at is the height rule itself. If
   * somebody ever changes that rule in a way that lands a real window back on
   * 2, this line is what says so — a clamp would have hidden it. */
  if (v.scale < 3) note(`${row.window}: scale ${v.scale} — the height rule gave back the old zoom`);
  /* The reference is fourteen rows. An integer scale on a canvas that is not
   * a multiple of 224 cannot land on fourteen exactly, so the claim is that it
   * lands within two rows of it at every size — which is the difference between
   * "the reference field" and "a strategy map". */
  if (Math.abs(v.rows - REFERENCE_ROWS) > 2) {
    note(`${row.window}: ${v.rows.toFixed(2)} rows is more than two off the reference ${REFERENCE_ROWS}`);
  }
  /* Width is NOT held to sixteen and must not be: every one of these canvases
   * is wider than 8:7 and the extra monitor buys columns. What it IS held
   * to is the aspect ratio being the only thing paying for them — cols/rows is
   * the canvas's own shape, so anything past it is the zoom slipping. These
   * four canvases run 1.26:1 to 1.54:1, so 16 x 1.55 is the honest ceiling. */
  if (v.cols > REFERENCE_COLS * 1.55) {
    note(`${row.window}: ${v.cols.toFixed(2)} columns is still a map, not a field`);
  }
  if (v.heroPx < 64) note(`${row.window}: hero is ${v.heroPx}px tall — still a speck`);
}

/* The rule refuses to hand back a corridor to a tall, narrow window, and
 * refuses to hand back one tile to a window dragged to nothing. */
out.guards = {
  tallNarrow: OW.fieldScale(480, 1400),   // MIN_COLS has to bite here
  tiny: OW.fieldScale(480, 320),
  huge: OW.fieldScale(5120, 2880),
};
/* And it never hands back something that is not a number. A NaN scale is a
 * black frame rather than a wrong zoom — it reaches ctx.scale() and takes every
 * coordinate after it — and a canvas reporting width 0 before layout is the
 * commonest way in. */
for (const [w, h] of [[0, 0], [NaN, 800], [950, NaN], [-100, 700], [undefined, undefined]]) {
  const v = OW.fieldScale(w, h);
  if (!Number.isInteger(v) || v < 2) note(`fieldScale(${w}, ${h}) returned ${v}`);
}
if (480 / (T * out.guards.tallNarrow) < 12) {
  note(`a 480x1400 frame shows ${(480 / (T * out.guards.tallNarrow)).toFixed(1)} columns`);
}
/* The ceiling has to be high enough not to reintroduce the bug on a bigger
 * monitor. At SCALE_MAX 8 this frame went back to forty tiles across. */
if (2880 / (T * out.guards.huge) > REFERENCE_ROWS + 2) {
  note(`a 5120x2880 frame shows ${(2880 / (T * out.guards.huge)).toFixed(1)} rows — `
       + `the ceiling is biting and it has put the strategy map back`);
}

/* --------------------------------------------------------- B. the camera */

out.camera = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const ow = build(W, H);
  const s = ow.scale;
  const spanX = W / s, spanY = H / s;
  const r = { window: `${win[0]}x${win[1]}`, scale: s,
              spanX: +spanX.toFixed(1), spanY: +spanY.toFixed(1),
              void: 0, offCentre: 0, jumps: 0, maxStep: 0, clampedFrames: 0 };

  /* Walk him from the west edge to the east edge and back down, sampling every
   * frame. Four hundred frames is most of the way across a 48-tile map at the
   * field's own 112 px/s. */
  let prevX = null, prevY = null;
  const walk = (keys, frames) => {
    for (let i = 0; i < frames; i++) {
      ow.keys.clear(); for (const k of keys) ow.keys.add(k);
      ow.update(DT); ow.draw();
      const cx = ow._camX, cy = ow._camY;

      /* NO VOID, TESTED ON THE CAMERA THE RENDERER ACTUALLY USES.
       *
       * This used to compare the UNROUNDED _camX against WORLD_W - spanX, and
       * it reported void 0 at every size while Chrome showed a two-pixel column
       * of sky down the right edge at two of the four. draw() does not
       * translate by camX; it translates by Math.round(camX), and at 1440x940
       * the old clamp was 490.5, which rounds OUTWARD to 491 — past the map.
       * raster.mjs makes translate() a no-op, so the rounding that causes the
       * defect cannot exist in this process and the only way to see it from
       * here is to test the number draw() computes. Which is this:
       *
       *   the map covers the frame  <=>  (WORLD - round(cam)) * s >= viewport
       *
       * With overworld.js's Math.floor clamp in place these pass everywhere;
       * without it they fail at 1440x940 and 1600x1000, which is the point. */
      const fitsX = WORLD_W > spanX, fitsY = WORLD_H > spanY;
      const rcx = Math.round(cx), rcy = Math.round(cy);
      if (fitsX && (rcx < 0 || (WORLD_W - rcx) * s < W)) r.void++;
      if (fitsY && (rcy < 0 || (WORLD_H - rcy) * s < H)) r.void++;

      /* CENTRED WHEN IT CAN BE — to within a world pixel, not to within a
       * thousandth of one. The camera centres on round(px) - round(spanX/2 -
       * T/2) rather than on the exact fraction, deliberately: that is what pins
       * the hero to one screen column instead of letting him slide a pixel
       * backwards every time the two roundings disagree. So the honest
       * tolerance for "centred" is the rounding itself, one world pixel. A
       * 0.001 here would flag the fix for the judder as a regression. */
      const wantX = ow.player.px - spanX / 2 + T / 2;
      const clamped = fitsX && (wantX < 0 || wantX > WORLD_W - spanX);
      if (clamped) r.clampedFrames++;
      else if (Math.abs(cx - wantX) > 1.0) r.offCentre++;

      /* NO JUDDER: the camera never moves further in a frame than the player
       * can — PLUS the one world pixel that landing on the lattice can add.
       *
       * The camera centres on Math.round(player.px), so between two frames it
       * advances by round(px + v*dt) - round(px), which is at most ceil(v*dt).
       * At 112 px/s and a sixtieth of a second that is 2, not 1.867. The old
       * bound of exactly v*dt was written against a camera that tracked the
       * player's float position and is not satisfiable by one that quantises —
       * and quantising is the fix for the hero sliding backwards a pixel at a
       * time, so the bound is the thing that has to give. It still catches what
       * it exists to catch: a teleport is tens of pixels, not two. */
      if (prevX !== null) {
        const d = Math.max(Math.abs(cx - prevX), Math.abs(cy - prevY));
        r.maxStep = Math.max(r.maxStep, d);
        if (d > 112 * DT + 1 + 1e-9) r.jumps++;
      }
      prevX = cx; prevY = cy;
    }
  };
  walk(['d'], 420);
  walk(['s'], 260);
  walk(['a'], 420);
  walk(['w'], 260);
  r.maxStep = +r.maxStep.toFixed(3);
  out.camera.push(r);
  if (r.void) note(`${r.window}: camera went off the map on ${r.void} frames`);
  if (r.offCentre) note(`${r.window}: player off centre on ${r.offCentre} unclamped frames`);
  if (r.jumps) note(`${r.window}: camera jumped ${r.jumps} times`);
}

/* Every corner, held exactly. The four map corners are where "clamps without
 * showing void" is either true or is a comment. */
out.corners = [];
{
  const [W, H] = WINDOWS[1].css;
  const ow = build(W, H);
  const s = ow.scale, spanX = W / s, spanY = H / s;
  for (const [tx, ty, name] of [[1, 1, 'NW'], [MAP_W - 2, 1, 'NE'],
                                [1, MAP_H - 2, 'SW'], [MAP_W - 2, MAP_H - 2, 'SE']]) {
    ow.player.x = tx; ow.player.y = ty;
    ow.player.px = tx * T; ow.player.py = ty * T;
    ow.update(DT); ow.draw();
    /* THE ROUNDED CAMERA AGAIN. This block used to print its own evidence and
     * fail to act on it — "NE 490.5,0  SE 490.5,320.8" was on the report while
     * the corner check said the corners were held. 490.5 + 277.5 is 768.0, so
     * against the fractional camera the map ends exactly at the frame; against
     * round(490.5) = 491 it ends two screen pixels short of it. */
    const rcx = Math.round(ow._camX), rcy = Math.round(ow._camY);
    const c = { corner: name, camX: +ow._camX.toFixed(1), camY: +ow._camY.toFixed(1),
                right: rcx + spanX, bottom: rcy + spanY };
    out.corners.push(c);
    if (rcx < 0 || rcy < 0) note(`${name}: camera is negative`);
    if (rcx + spanX > WORLD_W + 1e-9) {
      note(`${name}: ${((rcx + spanX - WORLD_W) * s).toFixed(0)}px of void on the right`);
    }
    if (rcy + spanY > WORLD_H + 1e-9) {
      note(`${name}: ${((rcy + spanY - WORLD_H) * s).toFixed(0)}px of void at the bottom`);
    }
  }
}

/* The pathological frame the old clamp got wrong: a view WIDER than the map.
 * Unreachable at the four windows above — the widest span measured is 318 world
 * pixels against a 768-wide map — and one drag of a corner away at SCALE_MIN. */
{
  const s = OW.fieldScale(4000, 700);
  const spanX = 4000 / s;
  const ow = build(4000, 700);
  ow.player.x = 2; ow.player.y = 2; ow.player.px = 32; ow.player.py = 32;
  ow.update(DT); ow.draw();
  out.widerThanMap = { scale: s, spanX: +spanX.toFixed(1), worldW: WORLD_W,
                       camX: +ow._camX.toFixed(1),
                       centred: Math.abs(ow._camX - (WORLD_W - spanX) / 2) < 0.01 };
  if (spanX > WORLD_W && !out.widerThanMap.centred) {
    note(`a view wider than the map did not centre it (camX ${ow._camX})`);
  }
}

/* ----------------------------------------------------- C. the King's panel */

/* heroTopOnScreen() computed the ceiling from viewH/2, which is where the hero
 * is ONLY while the camera is free. At a map edge the camera clamps and he is
 * somewhere else entirely — nearer the top of the frame at the north edge,
 * which is precisely where a panel pinned to PANEL_TOP lives. Both readings are
 * measured, at every scale, with the camera deliberately clamped. */
out.panel = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const ow = build(W, H);
  const s = ow.scale;
  const text = 'I HAVE READ EVERY LINE YOU HAVE EVER WRITTEN AND I AM NOT IMPRESSED '
             + 'BY ANY OF IT. THERE IS NOTHING HERE THAT I DID NOT ALREADY HOLD.';
  const rows = [];
  for (const [tx, ty, where] of [[24, 17, 'centre'], [24, 1, 'north edge'],
                                 [24, MAP_H - 2, 'south edge']]) {
    ow.player.x = tx; ow.player.y = ty;
    ow.player.px = tx * T; ow.player.py = ty * T;
    ow.update(DT); ow.draw();
    const heroTopTrue = Math.round((ow.player.py + T - SPR.HERO_H - ow._camY) * s);
    const assumed = K.heroTopOnScreen(H, s);
    const m = K.measurePanel(text, W, H, s, heroTopTrue);
    const heroBottom = heroTopTrue + SPR.HERO_H * s;
    rows.push({ where, heroTopTrue, assumed, panelTop: m.y, panelBottom: m.bottom,
                below: !!m.below, lines: m.lines });
    /* The promise, stated as a rectangle: the panel's band and the hero's band
     * do not overlap. Above him or below him, both keep it; across him does
     * not, and "across him" is what was shipping. */
    if (m.y < heroBottom && m.bottom > heroTopTrue) {
      note(`${win[0]}x${win[1]} ${where}: the panel runs ${m.y}..${m.bottom}, `
           + `the hero runs ${heroTopTrue}..${heroBottom}`);
    }
    if (m.bottom > H) note(`${win[0]}x${win[1]} ${where}: the panel runs off the bottom`);
    if (m.lines < 1) note(`${win[0]}x${win[1]} ${where}: he lost every word`);
  }
  out.panel.push({ window: `${win[0]}x${win[1]}`, scale: s, rows });
}

/* ------------------------------------------------------- D. the lattice */

/* Every fill and blit the WORLD layer makes has to land on a whole world pixel.
 * Under the raster stub the transform is a no-op, so a fractional coordinate
 * here is a fractional coordinate there — and there it is multiplied by s.
 * This wraps the context for one drawn frame per scale and counts. */
out.lattice = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const ow = build(W, H);
  const ctx = ow.ctx;
  const bad = [];
  let checked = 0;
  /* A SAVE-DEPTH COUNTER, NOT A FLAG, AND THE DIFFERENCE IS THE MEASUREMENT.
   *
   * This was a boolean: ctx.scale set it, ctx.restore cleared it. But the world
   * layer is `save; scale; translate; ...; restore`, and the things drawn
   * between those have save/restore pairs of their OWN — drawMotif does, and
   * tiles.drawLights does. The first nested restore cleared the flag, and
   * everything painted after it in the frame went unchecked.
   *
   * It was not a small tail. Counted against the same frames: the flag saw
   * 157050 primitives at 1440x940 where the depth counter sees 159600, and
   * every one of the 2550 it missed came after drawMotif's restore — the
   * weather layer and the point lights, which are the last two things the world
   * layer paints. All 300 fractional draws in those frames were in that gap, so
   * "0 fractional" was not a measurement of zero, it was a measurement of
   * nothing. (They were tiles.js:3492's light rects, and they are rounded now.)
   *
   * Depth counts save() up and restore() down; the world layer is whatever is
   * at or below the depth ctx.scale fired at, which is exactly the set of
   * primitives inside the camera transform however deeply they nest. */
  let depth = 0, worldDepth = -1;
  const inWorld = () => worldDepth >= 0 && depth >= worldDepth;
  const whole = (n) => Number.isFinite(n) && Math.abs(n - Math.round(n)) < 1e-9;
  const wrap = (name, idx) => {
    const real = ctx[name].bind(ctx);
    ctx[name] = (...a) => {
      if (inWorld()) {
        checked++;
        for (const i of idx) if (!whole(a[i])) { bad.push(`${name}(${a[i]})`); break; }
      }
      return real(...a);
    };
  };
  const realScale = ctx.scale.bind(ctx);
  const realSave = ctx.save.bind(ctx), realRestore = ctx.restore.bind(ctx);
  ctx.save = (...a) => { depth++; return realSave(...a); };
  ctx.restore = (...a) => {
    depth--;
    if (worldDepth >= 0 && depth < worldDepth) worldDepth = -1;   // the layer closed
    return realRestore(...a);
  };
  ctx.scale = (...a) => { worldDepth = depth; return realScale(...a); };
  wrap('fillRect', [0, 1, 2, 3]);
  wrap('drawImage', [1, 2]);

  ow.player.x = 20; ow.player.y = 17;
  ow.player.px = 20 * T; ow.player.py = 17 * T;
  /* A HUNDRED AND FIFTY FRAMES, NOT TWENTY-FOUR. The one primitive that was
   * ever off the lattice carried a sine, so it is fractional for most of its
   * cycle and whole at the ends of it; two dozen frames is a short enough
   * window to miss a phase. */
  for (let i = 0; i < 150; i++) { ow.time += DT; ow.draw(); }
  out.lattice.push({ window: `${win[0]}x${win[1]}`, scale: ow.scale,
                     worldDraws: checked, fractional: bad.length,
                     worst: bad.slice(0, 4) });
  if (bad.length) {
    note(`${win[0]}x${win[1]}: ${bad.length} world-layer draws on a half pixel `
         + `(${bad.slice(0, 3).join(', ')}) — ${ow.scale}x blur`);
  }
}

/* ----------------------------------------------------- E. screen overlays */

out.overlays = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const s = OW.fieldScale(W, H);
  const marks = [];
  const scratch = { x: 0, y: 0, edge: '' };
  const cv = makeCanvas(W, H);
  const ctx = cv.getContext('2d');
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [0.7, 0.7], [-0.7, -0.7]]) {
    for (const lane of [AX.WAYOUT_LANE, AX.THREAT_LANE]) {
      AX.drawEdgeMark(ctx, W, H, dx, dy, '#e8c37d', 0.9, lane, AX.MARK_SIZE, scratch);
      marks.push([scratch.x, scratch.y]);
      if (scratch.x < 0 || scratch.y < 0 || scratch.x > W || scratch.y > H) {
        note(`${win[0]}x${win[1]}: an edge mark landed off frame at ${scratch.x},${scratch.y}`);
      }
    }
  }
  /* The screen layers are fractions of the frame and take no world scale — the
   * point of the check is that they are INDEPENDENT of it, so the same call at
   * two scales on one frame size has to land identically. */
  out.overlays.push({ window: `${win[0]}x${win[1]}`, scale: s,
                      marks: marks.length, allInFrame: true });
}

/* --------------------------------------------------- E2. the weather */

/* WHAT THE ZOOM DOES TO A STORM, counted rather than reasoned about — AND THE
 * COUNT IS OF DROPS, NOT OF INK.
 *
 * The field's particles are made over the WHOLE MAP — makeParticles(key,
 * MAP_W * T, MAP_H * T, n) — and stepped and drawn in world space, inside the
 * camera transform. So zooming in means fewer of them are on screen: the
 * visible world area falls as 1/s^2.
 *
 * THIS SECTION USED TO ANSWER THAT WITH INK, AND THE ANSWER WAS TRUE AND BESIDE
 * THE POINT. Each particle is a world-space rect, so its painted screen area
 * rises as s^2 by exactly the factor that removes it from the frame; the share
 * of the frame that is wet came out identical at every scale, and with a fixed
 * count over the map it comes out identical BY CONSTRUCTION — 70 * (frame /
 * s^2 / map) * 4s^2 / frame is 280/map, with the frame and the scale both
 * cancelled out. A quantity that cannot vary is not evidence.
 *
 * What actually moved was the number of drops. Averaged over 260 camera
 * positions across the map, at density 1, pre-zoom scale against the shipped
 * one: 1280x800 30.0 -> 13.3 particles in frame, 1440x940 18.5 -> 10.4,
 * 1600x1000 22.5 -> 12.7, 1920x1080 17.2 -> 11.0. Half the rain, arriving
 * twice as fat. A clear sky went from 4.0 motes in frame to 2.2.
 *
 * So the claim is restated as the thing weather.py's `density` is actually
 * buying: HOW MANY ARE IN THE FRAME. overworld.js now sizes the list from the
 * visible slice, so that number is independent of the scale AND of the window —
 * it was never independent of the window before, a 1280x800 canvas got 74% more
 * rain than a 1920x1080 one for the same sky. Ink is reported alongside and is
 * no longer asserted, because ink is now a consequence: a drop is drawn at the
 * world scale like every other pixel in the frame, so a bigger tile means a
 * bigger drop, which is the zoom working rather than the zoom slipping.
 *
 * Averaged over a grid of camera positions rather than sampled at one, because
 * twenty-odd points in a rectangle is a binomial with a standard deviation of
 * four and a single frame cannot tell 19 from 24. */
out.weather = [];
{
  const rows = [];
  for (const { win, css } of WINDOWS) {
    const [W, H] = css;
    const ow = build(W, H);
    const s = ow.scale;
    /* A REAL STORM, not the fallback. With no server there is no sky strip and
     * the field falls back to a clear sky, which is a sample too small for the
     * answer to mean anything either way. This is the record gauntlet/weather.py
     * ships at full density, pushed down the same path _pollSky() would. */
    ow._applySky({ region: 'probe', condition: 'storm', particle: 'rain', density: 1 });
    const spanX = W / s, spanY = H / s;
    const perPx = (ow.particleStyle.streak ? 4 : 1) * s * s;
    let sum = 0, n = 0;
    for (let ty = 4; ty < MAP_H - 4; ty += 2) {
      for (let tx = 4; tx < MAP_W - 4; tx += 2) {
        ow.player.x = tx; ow.player.y = ty;
        ow.player.px = tx * T; ow.player.py = ty * T;
        ow._camera();
        const x0 = ow._camX, y0 = ow._camY;
        let on = 0;
        for (const q of ow.particles) {
          if (q.x >= x0 && q.x < x0 + spanX && q.y >= y0 && q.y < y0 + spanY) on++;
        }
        sum += on; n++;
      }
    }
    const onScreen = sum / n;
    const share = onScreen * perPx / (W * H);
    rows.push(onScreen);
    out.weather.push({ window: `${win[0]}x${win[1]}`, scale: s, total: ow.particles.length,
                       onScreen: +onScreen.toFixed(1), screenPx: Math.round(onScreen * perPx),
                       share: +(share * 100).toFixed(3) });
  }
  /* The band, across every window and every scale in the table. A storm the
   * player can see a third less of because he opened a bigger window is the
   * defect this section exists for, whichever direction it goes. */
  const lo = Math.min(...rows), hi = Math.max(...rows);
  out.weatherSpread = +((hi - lo) / lo * 100).toFixed(1);
  if ((hi - lo) / lo > 0.25) {
    note(`the storm is ${lo.toFixed(1)} particles in frame at one window and `
         + `${hi.toFixed(1)} at another — ${out.weatherSpread}% apart, so the `
         + `count still depends on the zoom`);
  }
  if (lo < 12) note(`a full-density storm is only ${lo.toFixed(1)} particles in frame`);
}

/* ------------------------------------------------------- F. discipline */

out.discipline = [];
for (const { win, css } of WINDOWS) {
  const [W, H] = css;
  const hashes = [];
  let alloc = 0;
  for (let pass = 0; pass < 2; pass++) {
    const ow = build(W, H);
    ow.player.x = 20; ow.player.y = 17;
    ow.player.px = 20 * T; ow.player.py = 17 * T;
    step(ow, 40);
    RASTER.counting = true; const before = RASTER.canvases;
    step(ow, 90);
    RASTER.counting = false;
    if (pass) alloc = RASTER.canvases - before;
    hashes.push(frameHash(ow.canvas));
  }
  const same = hashes[0] === hashes[1];
  out.discipline.push({ window: `${win[0]}x${win[1]}`, scale: OW.fieldScale(W, H),
                        deterministic: same, canvasesInLoop: alloc });
  if (!same) note(`${win[0]}x${win[1]}: two identical runs drew different frames`);
  if (alloc > 0) note(`${win[0]}x${win[1]}: ${alloc} canvases allocated inside the draw loop`);
}

/* ------------------------------------------------------------- the report */

const pad = (v, n) => String(v).padEnd(n);
console.log('\nA. THE SCALE — integer only, against the reference 16 x 14\n');
console.log('  ' + pad('window', 12) + pad('canvas', 12) + pad('scale', 7)
            + pad('tile px', 9) + pad('cols', 8) + pad('rows', 8) + 'hero px');
for (const r of out.table) {
  console.log('  ' + pad(r.window, 12) + pad(r.canvas, 12) + pad(r.scale + 'x', 7)
              + pad(r.tilePx, 9) + pad(r.cols, 8) + pad(r.rows, 8) + r.heroPx);
}
console.log('  ' + pad('reference', 12) + pad('256x224', 12) + pad('1x', 7)
            + pad(16, 9) + pad('16.00', 8) + pad('14.00', 8) + 24);
console.log('\n  guards: 480x1400 -> ' + out.guards.tallNarrow + 'x, 480x320 -> '
            + out.guards.tiny + 'x, 5120x2880 -> ' + out.guards.huge + 'x');

console.log('\nB. THE CAMERA — 1360 walked frames per window\n');
console.log('  ' + pad('window', 12) + pad('span (world px)', 18) + pad('void', 7)
            + pad('off centre', 12) + pad('jumps', 8) + 'max step');
for (const r of out.camera) {
  console.log('  ' + pad(r.window, 12) + pad(`${r.spanX} x ${r.spanY}`, 18)
              + pad(r.void, 7) + pad(r.offCentre, 12) + pad(r.jumps, 8) + r.maxStep);
}
console.log('  corners @1440x940: ' + out.corners.map(c =>
  `${c.corner} ${c.camX},${c.camY}`).join('  '));
console.log('  view wider than map: span ' + out.widerThanMap.spanX + ' vs world '
            + out.widerThanMap.worldW + ' -> centred ' + out.widerThanMap.centred);

console.log('\nC. THE KING\'S PANEL — bottom of the words vs top of his head\n');
for (const p of out.panel) {
  for (const r of p.rows) {
    console.log('  ' + pad(p.window, 12) + pad(p.scale + 'x', 5) + pad(r.where, 13)
                + 'hero top ' + pad(r.heroTopTrue, 6) + '(centred guess '
                + pad(r.assumed + ')', 7) + ' panel ' + pad(r.panelTop + '..' + r.panelBottom, 12)
                + pad(r.lines + ' lines', 9) + (r.below ? 'BELOW him' : 'above him'));
  }
}

console.log('\nD. THE LATTICE — world-layer draws on a fractional world pixel\n');
for (const r of out.lattice) {
  console.log('  ' + pad(r.window, 12) + pad(r.scale + 'x', 5)
              + pad(r.worldDraws + ' draws', 14) + r.fractional + ' fractional'
              + (r.worst.length ? '  ' + r.worst.join(' ') : ''));
}

console.log('\nE. SCREEN OVERLAYS — edge marks inside the frame\n');
for (const r of out.overlays) {
  console.log('  ' + pad(r.window, 12) + pad(r.scale + 'x', 5) + r.marks
              + ' marks, all in frame');
}

console.log('\nE2. THE WEATHER — drops in the frame at density 1, over 260 camera positions\n');
for (const r of out.weather) {
  console.log('  ' + pad(r.window, 12) + pad(r.scale + 'x', 5)
              + pad(r.onScreen + ' in frame', 16) + pad('of ' + r.total + ' on the map', 18)
              + pad(r.screenPx + ' screen px', 18) + r.share + '% of the frame');
}
console.log('  spread across every window and scale: ' + out.weatherSpread + '%');

console.log('\nF. DISCIPLINE\n');
for (const r of out.discipline) {
  console.log('  ' + pad(r.window, 12) + pad(r.scale + 'x', 5)
              + 'deterministic ' + pad(r.deterministic, 7)
              + 'canvases in loop ' + r.canvasesInLoop);
}

console.log('');
if (fail.length) {
  console.log('FAIL');
  for (const m of fail) console.log('  - ' + m);
  process.exit(1);
}
console.log('PASS — the reference pixel scale, the camera holds, and nothing the zoom '
            + 'moved is mispositioned.');
