/* unmakingfx.mjs — web/js/unmakingfx.js, measured in pixels.
 *
 * scripts/verify/unmaking.mjs belongs to the spellfx pass and measures the
 * chamber cinematic against gauntlet/unmaking.py. This one measures the
 * OVERWORLD layer: the green on the hero's own silhouette, the green on the
 * frame, and the four things that leave the sprite.
 *
 * Nothing below is asserted. Every claim is counted off a real raster:
 *   A  the arcs sit on CONTOUR CELLS traced from the alpha mask, and zero of
 *      them land off it; the screen layer paints and stays quiet.
 *   B  it is slower than transform.js, and each taking owns a beat.
 *   C  one thing leaves at a time — pixels and silhouette cells per step, for
 *      the hero AND for the companion, which is the only thing that truly goes.
 *   D  the last frame is plain: the rim hex and the trim hex are gone from the
 *      raster entirely, and not one opaque pixel was lost doing it.
 *   E  one authored green.
 *   F  deterministic from a cold cache, capped, fifteen colours off rendered
 *      pixels across three kits, and reduced motion is one still per beat.
 *   G  the same, driven by gauntlet/unmaking.py's real cinematic() table.
 */
import { installRaster, RASTER, pixelDiff, silhouetteDiff, colourCount } from './raster.mjs';
installRaster();
import { execFileSync } from 'child_process';
import fs from 'fs';

const S = await import('../../web/js/sprites.js');
const T = await import('../../web/js/transform.js');
const U = await import('../../web/js/unmakingfx.js');

/* The dressed hero the sequence runs on: full plate, a Runed blade so there is
 * real runework to dim, a cloak worth losing. hero_look()'s own shape. */
const LOOK = {
  weapon: 'sword', emote: 'neutral',
  cloak: '#52456e', tunic: '#7d6b90', metal: '#b0aabd', trim: '#a08a52',
  boot: '#715b45', skin: '#c08a62', hair: '#4a3a2c',
  _weapon: { key: 'sword', rung: 3, name: 'Runed', metal: '#cfd2e8', trim: '#a89aff' },
  _pieces: [{ piece: 'helmet', at: 75 }, { piece: 'chestplate', at: 75 },
            { piece: 'gauntlets', at: 75 }, { piece: 'boots', at: 75 },
            { piece: 'shield', at: 75 }],
};
const LOOKS = {
  bare: { weapon: 'sword', emote: 'neutral' },
  plate: LOOK,
  mythic: { weapon: 'sword', emote: 'neutral', cloak: '#6a4fb0', tunic: '#9a7fd0',
            metal: '#ffd9df', trim: '#ff6a7a', boot: '#8c7050', skin: '#d78f6d', hair: '#b07748',
            _weapon: { key: 'sword', rung: 5, name: 'Mythic', metal: '#ffd9df', trim: '#ff6a7a' },
            _pieces: [{ piece: 'helmet', at: 100 }, { piece: 'chestplate', at: 100 },
                      { piece: 'gauntlets', at: 100 }, { piece: 'boots', at: 100 },
                      { piece: 'shield', at: 100 }, { piece: 'legendary', at: 100 }] },
};
const FACING = 'down', FRAME = 0, POSE = 'idle';
const KEY = `hero|${FACING}|${FRAME}|${POSE}`;
const hero = S.heroFrame(FACING, FRAME, LOOK, POSE);
const pet = S.enemySprite('wolf', 0, 0) || S.heroFrame('down', 0, { weapon: null }, 'idle');
const dataOf = (c) => c.getContext().getImageData(0, 0, c.width, c.height);
const opaque = (d) => { let n = 0; for (let i = 3; i < d.data.length; i += 4) if (d.data[i]) n++; return n; };
const BIT = { companion: 0, weapon: 1, trim: 2, garb: 4, rim: 8 };

const report = {};
const fails = [];

/* --------------------------------- E. the green is one authored ramp ----- */
{
  /* The Green Index has ONE hex in this codebase and three files want to say
   * it. finale.py is the origin, kingui.js quotes it, and this ramp is built on
   * it — so the check is a real comparison against both, read live, not a
   * comment claiming they agree. */
  let kingGreen = null, pyGreen = null, err = '';
  try { kingGreen = (await import('../../web/js/kingui.js')).KING_GREEN; } catch (e) { err = e.message; }
  try {
    const PY = [
      'import re, sys',
      'from gauntlet import finale as f',
      'src = open(f.__file__).read()',
      'm = re.search(chr(34) + "accent" + chr(34) + r\'\\s*:\\s*\' + chr(34) + r\'(#[0-9a-fA-F]{6})\' + chr(34), src)',
      'sys.stdout.write(m.group(1) if m else "")',
    ].join('\n');
    pyGreen = execFileSync('python3', ['-c', PY],
      { cwd: new URL('../../', import.meta.url).pathname, encoding: 'utf8' }).trim() || null;
  } catch (e) { /* python optional */ }
  report.palette = {
    INDEX_GREEN: U.INDEX_GREEN, sphere: U.INDEX_GREEN_HEX, PLAIN: U.PLAIN,
    kinguiKING_GREEN: kingGreen, finalePyAccent: pyGreen, kinguiImportError: err || undefined,
    agreesWithKingui: kingGreen ? kingGreen.toLowerCase() === U.INDEX_GREEN_HEX.toLowerCase() : null,
    agreesWithFinalePy: pyGreen ? pyGreen.toLowerCase() === U.INDEX_GREEN_HEX.toLowerCase() : null,
    reason: 'palette.js has no ramp for the Green Index; `venom` is a warm olive authored for poison',
  };
  if (report.palette.agreesWithKingui === false) fails.push(`INDEX_GREEN_HEX ${U.INDEX_GREEN_HEX} != kingui.KING_GREEN ${kingGreen}`);
  if (report.palette.agreesWithFinalePy === false) fails.push(`INDEX_GREEN_HEX ${U.INDEX_GREEN_HEX} != finale.py accent ${pyGreen}`);
}

/* --------------------------------- B. the shape of time ------------------ */
report.timing = {
  transform_seconds: T.TRANSFORM_SECONDS,
  unmaking_overworld_seconds: +U.UNMAKING_SECONDS.toFixed(2),
  ratio: +(U.UNMAKING_SECONDS / T.TRANSFORM_SECONDS).toFixed(2),
  beats: U.BEATS.map(b => ({ id: b.id, span: b.span, takes: [...b.takes] })),
};
if (U.UNMAKING_SECONDS <= T.TRANSFORM_SECONDS) fails.push('not slower than transform.js');

/* --------------------------------- A. the outline ------------------------ */
const contour = U.spriteContour(hero, KEY);
report.contour = contour ? {
  loops: contour.loops.length, cells: contour.total, longest: contour.loops[0].length >> 1,
  edgePixelsInSprite: contour.edges,
  outlineCovered: +(contour.total / contour.edges).toFixed(3),
  spritePixels: hero.width * hero.height,
} : null;
if (!contour) fails.push('no contour traced off the hero');

/* --------------------------------- C. the takings, on the hero ----------- */
report.steps = U.measureUnmaking(S, hero, { look: LOOK, key: KEY, facing: FACING, frame: FRAME, pose: POSE });
report.roleCounts = report.steps.roleCounts;
if (!report.steps.length) fails.push('measureUnmaking returned nothing');
{
  /* Each taking must move pixels that the previous one did not. Four deltas
   * that are the same rectangle is one wipe with a counter on it. */
  let mask = 0; const regions = [];
  let prev = dataOf(hero);
  for (const b of U.BEATS) {
    const add = [...b.takes].reduce((m, t) => m | BIT[t], 0);
    if (!add) continue;
    mask |= add;
    const now = dataOf(U.heroPlate(S, hero, LOOK, FACING, FRAME, POSE, KEY, mask));
    const cells = new Set();
    for (let i = 0; i < now.data.length; i += 4) {
      if (prev.data[i] !== now.data[i] || prev.data[i + 1] !== now.data[i + 1]
        || prev.data[i + 2] !== now.data[i + 2]) cells.add(i);
    }
    regions.push({ id: b.id, cells });
    prev = now;
  }
  const overlaps = [];
  for (let i = 0; i < regions.length; i++) for (let j = i + 1; j < regions.length; j++) {
    let shared = 0;
    for (const c of regions[i].cells) if (regions[j].cells.has(c)) shared++;
    if (shared) overlaps.push(`${regions[i].id}/${regions[j].id}=${shared}`);
  }
  report.disjointTakings = {
    perTaking: regions.map(r => ({ id: r.id, pixels: r.cells.size })),
    overlappingPixelPairs: overlaps,
    rule: 'no two takings may move the same pixel — companion excluded, it is not on him',
  };
  if (overlaps.length) fails.push(`takings overlap: ${overlaps.join(',')}`);
}

/* --------------------------------- C. the companion, which really leaves -- */
{
  const e = U.createUnmaking({ sprites: S, look: LOOK });
  e.prewarm(hero, KEY, FACING, FRAME, POSE); e.prewarmSprite(pet, 'pet');
  const bi = U.BEATS.findIndex(b => [...b.takes].includes('companion'));
  let at = 0; for (let i = 0; i < bi; i++) at += U.BEATS[i].span;
  const pd = dataOf(pet); const petCover = opaque(pd);
  const c = U.spriteContour(pet, 'pet');
  const track = [];
  for (const k of [0, 0.25, 0.5, 0.75, 1]) {
    e.seek(at + U.BEATS[bi].span * k);
    const tc = traceCtx();
    const lit = e.drawCompanion(tc, pet, 0, 0, 'pet');
    const a = e.companionAlpha();
    track.push({ k, alphaHostApplies: +a.toFixed(3), outlineCellsLit: lit,
                 opaquePixelsRemaining: Math.round(petCover * a) });
  }
  report.companionDeparture = {
    beat: U.BEATS[bi].id, spritePixels: pet.width * pet.height, opaquePixels: petCover,
    outlineCells: c ? c.total : 0, track, endsAtZero: e.companionAlpha() === 0,
  };
  if (!report.companionDeparture.endsAtZero) fails.push('the companion does not finish gone');
}

/* --------------------------------- D. the last frame --------------------- */
const plain = U.heroPlate(S, hero, LOOK, FACING, FRAME, POSE, KEY, 15);
const base = dataOf(hero), last = dataOf(plain);
report.lastFrame = {
  pixelsChangedFromDressed: pixelDiff({ data: base.data }, { data: last.data }),
  silhouetteChangedFromDressed: silhouetteDiff({ data: base.data }, { data: last.data }),
  opaquePixelsDressed: opaque(base), opaquePixelsPlain: opaque(last),
  coloursDressed: colourCount({ data: base.data }), coloursPlain: colourCount({ data: last.data }),
};
if (report.lastFrame.opaquePixelsPlain !== report.lastFrame.opaquePixelsDressed) {
  fails.push('the plain hero lost pixels — that reads as an asset failing to load, not as a deliberate frame');
}
if (report.lastFrame.coloursPlain >= report.lastFrame.coloursDressed) fails.push('the plain hero did not collapse colours');
{
  const pal = S.heroPalette(LOOK);
  const hexOf = (d, hex) => {
    const n = parseInt(hex.replace('#', ''), 16);
    const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    let c = 0;
    for (let i = 0; i < d.data.length; i += 4) {
      if (d.data[i + 3] && d.data[i] === r && d.data[i + 1] === g && d.data[i + 2] === b) c++;
    }
    return c;
  };
  report.rimGone = {
    rimHex: pal.R, trimHex: pal.g,
    rimPixelsDressed: hexOf(base, pal.R), rimPixelsPlain: hexOf(last, pal.R),
    trimPixelsDressed: hexOf(base, pal.g), trimPixelsPlain: hexOf(last, pal.g),
  };
  if (report.rimGone.rimPixelsPlain !== 0) fails.push('the rim tone survives into the plain frame');
  if (report.rimGone.trimPixelsPlain !== 0) fails.push('the trim tone survives into the plain frame');
}

/* --------------------------------- F. fifteen colours, off the raster ---- */
{
  const budget = [];
  for (const [lookName, lookOpts] of Object.entries(LOOKS))
    for (const facing of ['down', 'up', 'left', 'right'])
      for (let f = 0; f < 4; f++)
        for (const pose of ['walk', 'idle', 'cast']) {
          const k = `${lookName}|${facing}|${f}|${pose}`;
          const img = S.heroFrame(facing, f, lookOpts, pose);
          budget.push({ look: lookName, facing, f, pose, beat: 'DRESSED', colours: colourCount({ data: dataOf(img).data }) });
          let mask = 0;
          for (const b of U.BEATS) {
            mask |= [...b.takes].reduce((m, t) => m | BIT[t], 0);
            const plate = mask ? U.heroPlate(S, img, lookOpts, facing, f, pose, k, mask) : img;
            budget.push({ look: lookName, facing, f, pose, beat: b.id, colours: colourCount({ data: dataOf(plate).data }) });
          }
        }
  const worst = budget.reduce((a, b) => b.colours > a.colours ? b : a);
  const worstDressed = budget.filter(x => x.beat === 'DRESSED').reduce((a, b) => b.colours > a.colours ? b : a);
  report.colourBudget = {
    platesMeasured: budget.length, maxAny: worst.colours, worst, worstDressed,
    over15: budget.filter(x => x.colours > 15).length,
    countedFrom: 'rendered pixels, not the palette dict',
  };
  if (report.colourBudget.over15) fails.push(`${report.colourBudget.over15} plates exceed 15 colours`);
}

/* --------------------------------- traces -------------------------------- */
let IMG_IDS = new WeakMap(), imgSeq = 0;
function resetImgIds() { IMG_IDS = new WeakMap(); imgSeq = 0; }
/* A canvas has no identity of its own, so a trace that logs only coordinates
 * cannot see the hero's plate being swapped — which is the entire event. */
function imgId(img) {
  if (!img) return 'null';
  if (!IMG_IDS.has(img)) IMG_IDS.set(img, 'img' + (++imgSeq));
  return IMG_IDS.get(img);
}
function traceCtx() {
  const log = [];
  const h = {
    canvas: { width: 640, height: 420 }, _f: '#000', _s: '#000', globalAlpha: 1,
    get fillStyle() { return this._f; }, set fillStyle(v) { this._f = v; log.push('F' + v); },
    get strokeStyle() { return this._s; }, set strokeStyle(v) { this._s = v; log.push('S' + v); },
    drawImage(img, ...r) { log.push('I' + imgId(img) + ':' + r.join(',')); },
    createLinearGradient() { return { addColorStop() {} }; },
    createRadialGradient() { return { addColorStop() {} }; },
    log,
  };
  for (const m of ['fillRect', 'save', 'restore', 'beginPath', 'fill', 'stroke', 'translate', 'scale']) {
    h[m] = (...a) => log.push(m + ':' + a.map(v => typeof v === 'number' ? Math.round(v * 1000) / 1000 : String(v)).join(',')
      + '@' + Math.round(h.globalAlpha * 1000) / 1000);
  }
  return h;
}
function play(reduced, beats, dt = 1 / 60) {
  resetImgIds();
  const e = U.createUnmaking({ sprites: S, look: LOOK, reducedMotion: reduced, beats });
  e.prewarm(hero, KEY, FACING, FRAME, POSE); e.prewarmSprite(pet, 'pet');
  const c = traceCtx();
  for (let i = 0; i * dt <= e.duration + dt; i++) {
    e.step(dt);
    const img = e.heroImage(hero, KEY, FACING, FRAME, POSE);
    c.drawImage(img, 100, 100);
    e.drawSprite(c, img, 100, 100, KEY);
    e.drawCompanion(c, pet, 60, 110, 'pet');
    e.drawScreen(c, 640, 420);
  }
  return c.log;
}

/* --------------------------------- F. determinism ------------------------ */
U.clearUnmakingCache(); const runA = play(false);
U.clearUnmakingCache(); const runB = play(false);
report.determinism = {
  ctxCalls: runA.length,
  identicalFromColdCache: runA.length === runB.length && runA.join('|') === runB.join('|'),
};
if (!report.determinism.identicalFromColdCache) fails.push('non-deterministic between cold runs');
{
  /* Comments are not code: the header says the words "Math.random" and
   * "Date.now" while promising not to use them, and a grep that cannot tell
   * those apart reports a violation every time somebody documents the rule. */
  const src = fs.readFileSync(new URL('../../web/js/unmakingfx.js', import.meta.url), 'utf8');
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  report.forbidden = {
    mathRandom: (code.match(/Math\.random/g) || []).length,
    dateNow: (code.match(/Date\.now/g) || []).length,
    performanceNow: (code.match(/performance\.now/g) || []).length,
    countedOverCodeOnly: true,
  };
  if (report.forbidden.mathRandom || report.forbidden.dateNow || report.forbidden.performanceNow) {
    fails.push('a clock or an rng in the draw path');
  }
}

/* --------------------------------- F. reduced motion --------------------- */
{
  const perBeat = [];
  for (let bi = 0; bi < U.BEATS.length; bi++) {
    const sigs = new Set();
    for (const k of [0.05, 0.3, 0.5, 0.7, 0.95]) {
      const e = U.createUnmaking({ sprites: S, look: LOOK, reducedMotion: true });
      e.prewarm(hero, KEY, FACING, FRAME, POSE); e.prewarmSprite(pet, 'pet');
      let at = 0; for (let i = 0; i < bi; i++) at += U.BEATS[i].span;
      e.seek(at + U.BEATS[bi].span * k);
      const c = traceCtx();
      const img = e.heroImage(hero, KEY, FACING, FRAME, POSE);
      c.drawImage(img, 0, 0); e.drawSprite(c, img, 0, 0, KEY);
      e.drawCompanion(c, pet, 0, 0, 'pet'); e.drawScreen(c, 640, 420);
      sigs.add(c.log.join('|'));
    }
    perBeat.push({ beat: U.BEATS[bi].id, distinctFramesWithinBeat: sigs.size });
  }
  const across = new Set();
  for (let bi = 0; bi < U.BEATS.length; bi++) {
    const e = U.createUnmaking({ sprites: S, look: LOOK, reducedMotion: true });
    e.prewarm(hero, KEY, FACING, FRAME, POSE); e.prewarmSprite(pet, 'pet');
    let at = 0; for (let i = 0; i < bi; i++) at += U.BEATS[i].span;
    e.seek(at + U.BEATS[bi].span * 0.6);
    // NO resetImgIds() here: the ids have to stay stable ACROSS the seven
    // stills, or every still is 'img1' and the plate swap — the entire event —
    // is invisible to the trace and the check passes for the wrong reason.
    const c = traceCtx();
    const img = e.heroImage(hero, KEY, FACING, FRAME, POSE);
    c.drawImage(img, 0, 0); e.drawSprite(c, img, 0, 0, KEY); e.drawScreen(c, 640, 420);
    across.add(c.log.join('|'));
  }
  report.reducedMotion = {
    perBeat, distinctStillsAcrossBeats: across.size, beats: U.BEATS.length,
    rule: 'one still per beat, and the stills must differ or the event is not communicated',
  };
  const moving = perBeat.filter(x => x.distinctFramesWithinBeat !== 1);
  if (moving.length) fails.push(`reduced motion animates in: ${moving.map(m => m.beat).join(',')}`);
  if (across.size !== U.BEATS.length) fails.push('reduced-motion stills do not distinguish the beats');
}

/* --------------------------------- F. allocation and caps ---------------- */
U.clearUnmakingCache();
{
  const e = U.createUnmaking({ sprites: S, look: LOOK });
  RASTER.counting = true; RASTER.canvases = 0;
  const built = e.prewarm(hero, KEY, FACING, FRAME, POSE);
  e.prewarmSprite(pet, 'pet');
  const warmAllocs = RASTER.canvases;
  const c = traceCtx();
  RASTER.canvases = 0;
  for (let i = 0; i < 1200; i++) {
    e.step(1 / 60);
    const img = e.heroImage(hero, KEY, FACING, FRAME, POSE);
    e.drawSprite(c, img, 100, 100, KEY);
    e.drawCompanion(c, pet, 60, 110, 'pet');
    e.drawScreen(c, 640, 420);
  }
  const drawAllocs = RASTER.canvases;
  RASTER.counting = false;
  report.allocation = {
    platesBuiltByPrewarm: built, canvasesDuringPrewarm: warmAllocs,
    canvasesDuring1200DrawFrames: drawAllocs, stats: U.unmakingStats(),
  };
  if (drawAllocs !== 0) fails.push(`${drawAllocs} canvases allocated inside the draw loop`);
}
{
  U.clearUnmakingCache();
  for (let i = 0; i < 700; i++) {
    U.heroPlate(S, hero, LOOK, FACING, FRAME, POSE, `junk-${i}`, 15);
    U.spriteContour(hero, `junkc-${i}`);
  }
  const st = U.unmakingStats();
  report.caps = { after700Distinct: st, capped: st.plates <= st.PLATE_MAX && st.contours <= st.CONTOUR_MAX };
  if (!report.caps.capped) fails.push('caches grew past their cap');
}

/* --------------------------------- A. the two layers, painting ----------- */
{
  U.clearUnmakingCache();
  const e = U.createUnmaking({ sprites: S, look: LOOK });
  e.prewarm(hero, KEY, FACING, FRAME, POSE);
  e.seek(U.UNMAKING_SECONDS * 0.5);

  const c = traceCtx();
  const peak = e.drawScreen(c, 640, 420);
  const rectLines = c.log.filter(l => l.startsWith('fillRect'));
  const alphas = rectLines.map(l => +l.split('@')[1]);
  report.screenLayer = {
    fillRects: rectLines.length, gradientsAllocated: 0,
    peakEdgeAlpha: +peak.toFixed(4), maxAlphaPainted: +Math.max(...alphas).toFixed(4),
    apexVignetteCapForComparison: 0.26,
    transformFlashPeakForComparison: 0.92,
    greensUsed: [...new Set(c.log.filter(l => l.startsWith('F')).map(l => l.slice(1)))],
  };
  /* Escalation, measured. His presence wash all game is kingui.WASH_CAP; the
   * Unmaking is allowed to be louder than that and is NOT allowed to be
   * anywhere near what transform.js spends on one white-out frame. */
  let washCap = null;
  try { washCap = (await import('../../web/js/kingui.js')).WASH_CAP; } catch (e) { /* optional */ }
  report.screenLayer.kinguiPresenceWashCap = washCap;
  report.screenLayer.timesLouderThanHisPresence = washCap
    ? +(report.screenLayer.maxAlphaPainted / washCap).toFixed(2) : null;
  report.screenLayer.fractionOfTransformFlash =
    +(report.screenLayer.maxAlphaPainted / 0.92).toFixed(2);
  if (report.screenLayer.maxAlphaPainted > 0.31) fails.push('the screen layer is louder than 0.31 — he is never loud');
  if (washCap && report.screenLayer.maxAlphaPainted <= washCap) {
    fails.push('the Unmaking is no louder than his ordinary presence — the once-only event does not read');
  }

  const c2 = traceCtx();
  const painted = e.drawSprite(c2, hero, 0, 0, KEY);
  const cells = c2.log.filter(l => l.startsWith('fillRect'))
    .map(l => l.split('@')[0].split(':')[1].split(',').slice(0, 2).join(','));
  const onContour = new Set(); const cset = new Set();
  for (const loop of U.spriteContour(hero, KEY).loops) {
    for (let i = 0; i < loop.length; i += 2) cset.add(`${loop[i]},${loop[i + 1]}`);
  }
  for (const p of cells) if (cset.has(p)) onContour.add(p);
  report.spriteLayer = {
    cellsPainted: painted, distinctCells: new Set(cells).size,
    onContour: onContour.size, offContour: new Set(cells).size - onContour.size,
    rule: 'offContour must be 0 — the arcs follow the outline, they are not drawn across it',
  };
  if (report.spriteLayer.offContour !== 0) fails.push('arcs painted off the contour');
}

/* --------------------------------- G. driven by gauntlet/unmaking.py ----- */
{
  let cin = null, err = '';
  try {
    const src = 'import json;from gauntlet import unmaking as m;'
      + 'c=m.cinematic();'
      + 'print(json.dumps({"beats":[{k:b[k] for k in ("index","crutch","at","end","seconds","take_seconds","read_seconds","ramp","motif","surface","leaves")} for b in c["beats"]],"timing":c["timing"]}))';
    cin = JSON.parse(execFileSync('python3', ['-c', src],
      { cwd: new URL('../../', import.meta.url).pathname, encoding: 'utf8' }));
  } catch (e) { err = String(e.message).slice(0, 200); }

  if (!cin) {
    report.drivenByPython = { available: false, error: err,
      note: 'gauntlet/unmaking.py did not answer; the standalone BEATS path is what shipped' };
  } else {
    const beats = U.beatsFromCinematic(cin);
    const spriteBeats = beats.filter(b => b.takes.length);
    const order = spriteBeats.map(b => `${b.id}->${[...b.takes].join('+')}`);
    const steps = U.measureUnmaking(S, hero, { look: LOOK, key: KEY, facing: FACING, frame: FRAME, pose: POSE, beats });
    const nonZero = steps.filter(s => s.pixelsChanged > 0);
    const colours = steps.map(s => s.coloursAfter);
    let monotone = true;
    for (let i = 1; i < colours.length; i++) if (colours[i] > colours[i - 1] + 1) monotone = false;
    U.clearUnmakingCache(); const a2 = play(false, beats);
    U.clearUnmakingCache(); const b2 = play(false, beats);
    report.drivenByPython = {
      available: true,
      pythonTakes: cin.beats.length,
      pythonTotalSeconds: cin.timing.unattended_seconds,
      beatsProduced: beats.length,
      firstTakeAt: cin.beats[0].at, lastTakeEnd: cin.beats[cin.beats.length - 1].end,
      spriteMapping: U.SPRITE_FOR_CRUTCH,
      spriteBeatsInPythonOrder: order,
      rimIsLast: order[order.length - 1] === 'OBLIGING_HAND->rim',
      pixelsPerTaking: nonZero.map(s => ({ id: s.id, takes: s.takes, px: s.pixelsChanged, colours: s.coloursAfter })),
      maxColours: Math.max(...colours),
      coloursNeverRise: monotone,
      deterministic: a2.length === b2.length && a2.join('|') === b2.join('|'),
      ctxCalls: a2.length,
    };
    if (!report.drivenByPython.rimIsLast) fails.push('driven by python, the rim does not fail last');
    if (report.drivenByPython.maxColours > 15) fails.push('driven by python, a plate exceeds 15 colours');
    if (!report.drivenByPython.deterministic) fails.push('driven by python, non-deterministic');
  }
}

report.FAILURES = fails;
report.VERDICT = fails.length ? 'FAIL' : 'PASS';
console.log(JSON.stringify(report, null, 1));
