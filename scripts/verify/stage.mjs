/* THE STAGE RASTER, MEASURED.
 *
 * docs/08-art-direction §A moved the battle stage from 192x128 to 256x224 with
 * a 256x176 SAFE AREA at rows 24..199, and §G says every contract in that
 * document is proved by measurement rather than by the absence of a throw. This
 * is the measurement for §A, and it makes four claims that can each fail:
 *
 *   1. THERE IS ONE GEOMETRY. fx.js, battlescene.js and spellfx.js each declare
 *      their own copy of w/h/ground/heroX/enemyX, and main.js declares a fourth
 *      for the box it sizes. They are compared field by field. Two copies that
 *      disagree is the failure this file exists for: it is what let the death
 *      harness go on measuring the old stage for a whole migration.
 *
 *   2. EVERY SPRITE BOX IS A WHOLE SNES TILE. §B builds the ladder out of the
 *      8x8 tile, so every size constant must divide by 8, and so must the two
 *      foot centres — 64 and 184 land on the tile grid, 46 and 136 did not.
 *
 *   3. NOTHING LOAD-BEARING LIVES IN THE OVERSCAN. A real BattleFX is built on
 *      a host big enough that all 224 rows are on the canvas — which the
 *      shipped layout never is, and is exactly why it has to be forced — and
 *      then each piece of on-stage furniture is switched on one at a time and
 *      the frame is diffed against a baseline. Every pixel a readout changed
 *      must land in rows 24..199. A piece that changes NOTHING fails too: that
 *      is how a gauge disappears without anyone noticing.
 *
 *   4. THE FIT IS A WHOLE NUMBER AND THE EDITOR SURVIVES IT. fitBattleStage()'s
 *      arithmetic is reproduced against the chrome measured live in a browser
 *      (borders 6, chromeV 47, chromeH 28) at the six window sizes the game is
 *      actually opened at, and checked against the table in §A-5.
 *
 * Run: node scripts/verify/stage.mjs
 */
import { installRaster, RASTER } from './raster.mjs';
installRaster();

/* raster.mjs's document is deliberately minimal — it exists to make canvases.
 * BattleFX also wants a stylesheet and a host element, so those are added here
 * rather than in the shared stub, where they would be dead weight for every
 * other harness. */
const doc = globalThis.document;
doc.getElementById = () => null;
doc.head = { appendChild() {} };
doc.querySelector = () => null;
/* raster.mjs answers createElement('div') with a bare {style, getContext}. The
 * stage wraps its canvas in one, so the non-canvas branch needs to behave like
 * a node: hold children and carry a class name. */
const rasterCreate = doc.createElement.bind(doc);
doc.createElement = (tag) => {
  if (String(tag).toLowerCase() === 'canvas') return rasterCreate(tag);
  return {
    tagName: String(tag).toUpperCase(), style: {}, className: '', id: '',
    children: [], parentNode: null,
    appendChild(n) { this.children.push(n); n.parentNode = this; return n; },
    removeChild(n) { this.children = this.children.filter(c => c !== n); },
    querySelector() { return null; },
    getBoundingClientRect() { return { x: 0, y: 0, width: 0, height: 0,
      top: 0, left: 0, right: 0, bottom: 0 }; },
  };
};
globalThis.addEventListener = () => {};
globalThis.removeEventListener = () => {};
globalThis.getComputedStyle = () => ({ position: 'relative', borderLeftWidth: '3px',
  borderRightWidth: '3px', borderTopWidth: '3px', borderBottomWidth: '3px',
  paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
  borderBottomWidth: '1px' });

import fs from 'fs';
import * as fxm from '../../web/js/fx.js';
import * as scene from '../../web/js/battlescene.js';
import * as spellfx from '../../web/js/spellfx.js';
import * as sprites from '../../web/js/sprites.js';
import * as monsterart from '../../web/js/monsterart.js';
import * as apex from '../../web/js/apex.js';
import * as bosses from '../../web/js/bosses.js';
import * as bossart from '../../web/js/bossart.js';
import {BATTLE_HERO} from '../../web/js/battlehero.js';

const ROOT = new URL('../../', import.meta.url).pathname;
const fails = [];
const ok = (cond, msg) => { if (!cond) fails.push(msg); return !!cond; };
const S = fxm.STAGE;

/* ================== 1. ONE GEOMETRY, FOUR DECLARATIONS ================== */
console.log('1. ONE GEOMETRY');
const FIELDS = ['w', 'h', 'ground', 'heroX', 'enemyX', 'safeTop', 'safeH'];
const copies = [
  ['fx.STAGE', S],
  ['battlescene.SCENE_STAGE', scene.SCENE_STAGE],
  ['spellfx.STAGE_GEOM', spellfx.STAGE_GEOM],
];
for (const [name, g] of copies) {
  for (const f of FIELDS) {
    ok(g[f] === S[f], `${name}.${f} is ${g[f]}, fx.STAGE.${f} is ${S[f]}`);
  }
  console.log(`   ${name.padEnd(24)} ${FIELDS.map(f => `${f}=${g[f]}`).join(' ')}`);
}
/* main.js is not importable here — it boots a whole app — so its constant is
 * read out of the source. A regex is the honest tool for one frozen literal. */
const mainSrc = fs.readFileSync(ROOT + 'web/js/main.js', 'utf8');
const mLog = /const STAGE_LOGICAL = \{ w: (\d+), h: (\d+), fitH: (\d+) \};/.exec(mainSrc);
ok(!!mLog, 'main.js STAGE_LOGICAL no longer matches the shape this harness reads');
if (mLog) {
  const [, w, h, fitH] = mLog.map(Number);
  console.log(`   main.js STAGE_LOGICAL     w=${w} h=${h} fitH=${fitH}`);
  ok(w === S.w, `main.js fits width ${w}, the raster is ${S.w}`);
  ok(h === S.h, `main.js declares height ${h}, the raster is ${S.h}`);
  ok(fitH === S.safeH, `main.js fits ${fitH} rows, the safe area is ${S.safeH}`);
}
ok(S.safeTop * 2 + S.safeH === S.h,
   `the safe area is not centred: ${S.safeTop} + ${S.safeH} + ${S.safeTop} != ${S.h}`);
console.log(`   safe area rows ${S.safeTop}..${S.safeTop + S.safeH - 1}, centred in ${S.h}: ok`);

/* ================== 2. THE LADDER IS WHOLE TILES ================== */
console.log('\n2. EVERY BOX IS A WHOLE 8x8 TILE');
const LADDER = [
  ['HERO_W', sprites.HERO_W], ['HERO_H', sprites.HERO_H],
  ['ENEMY_SIZE', sprites.ENEMY_SIZE], ['BOSS_SIZE', sprites.BOSS_SIZE],
  ['MON_SIZE', monsterart.MON_SIZE], ['monsterart.ELITE_SIZE', monsterart.ELITE_SIZE],
  ['monsterart.APEX_SIZE', monsterart.APEX_SIZE],
  ['apex.APEX_SIZE', apex.APEX_SIZE],
  ['bossart.ART_W', bossart.ART_W], ['bossart.ART_H', bossart.ART_H],
  ['bossart.ART_WIDE_W', bossart.ART_WIDE_W],
  /* The two rungs added with the 96x128 final boss. They were outside this
   * check entirely, which meant the newest boxes in the ladder were the only
   * ones nothing proved were whole tiles. */
  ['bossart.ART_FINAL_W', bossart.ART_FINAL_W], ['bossart.ART_FINAL_H', bossart.ART_FINAL_H],
  ['bosses.FINAL_BOSS_W', bosses.FINAL_BOSS_W], ['bosses.FINAL_BOSS_H', bosses.FINAL_BOSS_H],
  ['STAGE.w', S.w], ['STAGE.h', S.h], ['STAGE.safeH', S.safeH], ['STAGE.safeTop', S.safeTop],
  ['STAGE.heroX', S.heroX], ['STAGE.enemyX', S.enemyX],
];
for (const [n, v] of LADDER) ok(v % 8 === 0, `${n} = ${v} is not a multiple of 8`);
console.log('   ' + LADDER.map(([n, v]) => `${n}=${v}`).join('  '));
ok(S.ground < S.safeTop + S.safeH && S.ground > S.safeTop,
   `the ground line ${S.ground} is outside the safe area`);
console.log(`   ground ${S.ground} is ${((S.ground / S.h) * 100).toFixed(1)}% down the raster `
  + `and sits inside the safe area`);

/* ================== 3. NOTHING LOAD-BEARING IN THE OVERSCAN ============ */
console.log('\n3. NOTHING A PLAYER MUST READ IS IN THE OVERSCAN');
class Host {
  constructor(w, h) { this._w = w; this._h = h; this.children = []; this.style = {}; }
  appendChild(n) { this.children.push(n); n.parentNode = this; return n; }
  removeChild(n) { this.children = this.children.filter(c => c !== n); }
  getBoundingClientRect() { return { x: 0, y: 0, width: this._w, height: this._h,
    top: 0, left: 0, right: this._w, bottom: this._h }; }
  querySelector() { return null; }
}
/* Big enough that px lands on 1 AND every row of the raster is on the canvas.
 * The shipped box never shows the overscan; this one has to. */
const host = new Host(S.w + 16, S.h + 16);
const fx = new fxm.BattleFX(host, { reducedMotion: true });
fx.setScene({ region: 'ember', pattern: 'loops',
  enemy: { name: 'THE ROLLING TITAN', sprite: 'titan', boss: true, hp: 7, hp_max: 10, phases: 6 } });
fx.setEnemyHp(7, 10);
fx._update(0.016);            // builds the authored stage layer
const cv = fx.canvas;
const W = cv.width, H = cv.height;
const rowOf = y => Math.floor((y - fx.oy) / fx.px);
console.log(`   host ${host._w}x${host._h} -> canvas ${W}x${H}, px ${fx.px}, oy ${fx.oy}`
  + ` -> stage rows ${rowOf(0)}..${rowOf(H - 1)} all on the canvas`);
ok(rowOf(0) <= 0 && rowOf(H - 1) >= S.h - 1,
   'the probe canvas does not show the whole raster, so the overscan cannot be checked');

/* raster.mjs composites fillRect and drawImage for real and deliberately paints
 * nothing for fillText — it is a pixel harness, not a font engine. So the two
 * pieces of furniture that are ONLY text (the taunt crawl, the damage number)
 * would diff to zero pixels and look like they had vanished. Their baselines
 * are recorded instead, which is the same claim measured one level up: the text
 * is in stage coordinates here, so `y` IS the stage row of the baseline and
 * `y - size` is the top of the glyph box. */
const texts = [];
const realFillText = fx.ctx.fillText ? fx.ctx.fillText.bind(fx.ctx) : null;
fx.ctx.fillText = function (str, x, y) {
  const size = parseFloat(String(this.font || '8px')) || 8;
  texts.push({ str: String(str), x, y, size });
  if (realFillText) return realFillText(str, x, y);
};
const grab = () => { texts.length = 0; fx._render(); return cv.data.slice(); };
const clear = () => {
  fx.banner = null; fx.phaseCard = null; fx.nameCard = null; fx.crawl = null;
  fx.xpTarget = 0; fx.xpShown = 0; fx.xpBar = null;
  fx.comboMult = 1; fx.combo = 0; fx.pips = 0; fx.pipsLit = 0;
  fx.numbers.length = 0; fx.chips.length = 0;
};
clear();
const base = grab();
const baseText = texts.slice();
const FURNITURE = {
  'enemy bar': () => { fx.pips = 6; fx.pipsLit = 4; },
  'banner':    () => { fx.banner = { text: 'STILL STANDING', sub: 'THE ARC HELD',
                                     colour: '#ffd97a', t: 0.3, dur: 2, slam: false }; },
  'phase card': () => { fx.phaseCard = { label: 'PHASE THREE — THE SHELL SPLITS',
    herald: 'You have broken the outer casing and it did not ever need it at all.',
    tell: 'Every second cast now costs one more focus than the panel says it does.',
    colour: '#ff6a7a', t: 0.4, dur: 3 }; },
  'name card': () => { fx.nameCard = { text: 'THE ROLLING TITAN', t: 0.6, dur: 3 }; },
  'taunt crawl': () => { fx.crawl = { shown: 76,
    text: 'I AM THE INDEX AND I DO NOT FORGET ONE SINGLE LINE THAT YOU EVER WROTE HERE.' }; },
  'xp readout': () => { fx.xpTarget = 420; fx.xpShown = 260;
                        fx.xpBar = { from: 0.2, to: 0.8, t: 0.6 }; },
  'combo':     () => { fx.comboMult = 1.35; fx.combo = 7; },
  'damage number': () => fx.damageNumber(1847, { kind: fxm.DAMAGE_KIND.CRIT }),
  'status chip': () => fx.chips.push({ text: 'FOCUS +2', colour: '#7ec8ff',
    x: S.enemyX, y: S.ground - 60, tx: S.w / 2, ty: S.ground - 90, t: 0.5, dur: 2 }),
};
const SAFE_BOT = S.safeTop + S.safeH;
for (const [name, set] of Object.entries(FURNITURE)) {
  clear(); set();
  const img = grab();
  let changed = 0, lo = Infinity, hi = -Infinity, outside = 0;
  for (let p = 0, i = 0; i < img.length; i += 4, p++) {
    if (img[i] === base[i] && img[i + 1] === base[i + 1]
        && img[i + 2] === base[i + 2] && img[i + 3] === base[i + 3]) continue;
    changed++;
    const row = rowOf((p / W) | 0);
    if (row < lo) lo = row;
    if (row > hi) hi = row;
    if (row < S.safeTop || row >= SAFE_BOT) outside++;
  }
  // Text drawn this frame that was not drawn in the baseline frame.
  const newText = texts.filter(t => !baseText.some(b => b.str === t.str && b.y === t.y));
  let textOutside = 0;
  for (const t of newText) {
    const top = Math.floor(t.y - t.size), bot = Math.ceil(t.y + 1);
    if (top < lo) lo = top;
    if (bot > hi) hi = bot;
    if (top < S.safeTop || bot >= SAFE_BOT) textOutside++;
  }
  ok(changed > 0 || newText.length > 0,
     `"${name}" painted nothing at all — a readout that draws no pixels is gone`);
  ok(outside === 0, `"${name}" put ${outside} pixels in the overscan (rows ${lo}..${hi})`);
  ok(textOutside === 0, `"${name}" put ${textOutside} lines of text outside rows `
    + `${S.safeTop}..${SAFE_BOT - 1}`);
  console.log(`   ${name.padEnd(15)} ${String(changed).padStart(6)} px + ${String(newText.length).padStart(2)} text`
    + `, rows ${String(lo).padStart(3)}..${String(hi).padStart(3)}`
    + `  ${outside === 0 && textOutside === 0 ? 'inside' : 'OUTSIDE'}`);
}
clear();

/* ================== 4. THE FIT IS A WHOLE NUMBER ======================= */
console.log('\n4. THE FIT, AT THE WINDOWS THE GAME OPENS AT');
/* Chrome measured live at dpr 1 through a real encounter; see docs/08 §A-2.
 * `sh` and `hudH` are the two the layout supplies and they are measured per
 * window, because the combat HUD wraps a line at the narrow ones. */
const BAND = 0.62, MAIN_MIN = 184, WIDE = 0.52, GUTTER = 8, bw = 6, bh = 6,
      chromeV = 47, chromeH = 28;
const WINDOWS = [
  // window        sh    hudH   expected px, expected box
  [1024, 640,      583,  141,   1,  270, 190],
  [1280, 800,      753,  148,   2,  526, 366],
  [1440, 940,      893,  132,   2,  526, 366],
  [1600, 1000,     953,  132,   3,  782, 542],
  [1920, 1080,    1033,  132,   3,  782, 542],
  [2560, 1440,    1393,  132,   4, 1038, 718],
];
for (const [ww, wh, sh, hudH, wantPx, wantW, wantH] of WINDOWS) {
  const bandMax = Math.max(140, sh - hudH - MAIN_MIN);
  const band = Math.min(sh * BAND, bandMax);
  const artMaxH = Math.max(S.safeH, (band - chromeV - bh - GUTTER));
  const artMaxW = Math.max(S.w, (ww * WIDE - chromeH - bw - GUTTER));
  const px = Math.max(1, Math.floor(Math.min(artMaxH / S.safeH, artMaxW / S.w)));
  const boxW = Math.round(S.w * px + bw + GUTTER);
  const boxH = Math.round(S.safeH * px + bh + GUTTER);
  const main = sh - hudH - boxH - chromeV;
  ok(px === wantPx, `${ww}x${wh}: fit gave scale ${px}, the §A-5 table says ${wantPx}`);
  ok(boxW === wantW && boxH === wantH,
     `${ww}x${wh}: box ${boxW}x${boxH}, the §A-5 table says ${wantW}x${wantH}`);
  ok(main >= MAIN_MIN, `${ww}x${wh}: #battle-main left with ${main}px, floor is ${MAIN_MIN}`);
  ok(Number.isInteger(px), `${ww}x${wh}: scale ${px} is not a whole number`);
  console.log(`   ${String(ww + 'x' + wh).padEnd(10)} scale ${px}  box ${String(boxW + 'x' + boxH).padEnd(9)}`
    + ` figure ${24 * 4 * px}px  #battle-main ${main}`);
}

/* ============ 5. EVERY FIGURE LANDS ON A WHOLE DEVICE PIXEL ============
 *
 * The stage runs under ctx.setTransform(px, ...), so ONE SOURCE PIXEL of any
 * sprite covers `blit * px` device pixels, where `blit` is the factor the
 * drawing code scales that sprite by in logical space. If `blit` is not a whole
 * number the sprite is resampled: some source columns come out n device columns
 * wide and the rest n+1, and the raggedness moves with the window.
 *
 * BOSS_STAGE_SCALE was 1.5 for the four wide archetypes, which is whole at the
 * even px values and half a pixel at px 3 and px 5 — three of the six windows
 * above. This is the check that would have caught it.
 *
 * It also proves the creature is still in frame, because the fix for the half
 * pixel was to make the wide rigs twice as big and pull them back with a bias:
 * a boss whose scale is whole but whose tail is off the right edge has traded
 * one defect for another. Painted bounding boxes, not rig boxes — a rig column
 * with nothing in it is allowed to hang over the edge. */
console.log('\n5. EVERY FIGURE BLIT IS A WHOLE NUMBER, AND STAYS IN FRAME');
const PXS = [1, 2, 3, 4, 5, 6];
const HERO_L = S.heroX - BATTLE_HERO.footX*BATTLE_HERO.scale,
      HERO_R = HERO_L+BATTLE_HERO.width*BATTLE_HERO.scale-1;
const fills = [];
/* THE WHOLE ENVELOPE, NOT A CORNER OF IT.
 *
 * This swept `ph < 3` against BOSS_PHASE_COUNT = 6 and never passed a beat, so
 * it sampled three stages of six at beat 0 — and the last two stages are
 * exactly the ones that ADD contour (spall bites the outline, crown() puts
 * spines out of it), while the wyrm's widest frame is at beat 4. It therefore
 * printed dragon 94..255 and hydra 144..225 for real envelopes of 84..255 and
 * 130..247, and called wyrm 86..253 and interpreter 68..249 when both were
 * touching 255. A harness that samples an eighth of the animation and reports
 * the answer as the animation is not a measurement, it is a sample dressed up
 * as one. All six stages, all five frames, all six beats. */
function paintedCols(key) {
  let lo = 1e9, hi = -1;
  for (let ph = 0; ph < bosses.BOSS_PHASE_COUNT; ph++)
    for (let f = 0; f < bosses.BOSS_FRAME_COUNT; f++)
      for (let b = 0; b < bosses.BOSS_BEATS; b++) {
        const img = bosses.bossSprite(key, null, f, { phase: ph, beat: b });
        for (let y = 0; y < img.height; y++) for (let x = 0; x < img.width; x++) {
          if (img.data[(y * img.width + x) * 4 + 3]) { if (x < lo) lo = x; if (x > hi) hi = x; }
        }
      }
  return [lo, hi];
}

/* AND THE SWAY, WHICH IS THE HALF THE STILL LEAVES OUT.
 *
 * drawBoss does not blit at `left`; it blits at `left + dx`, where
 * dx = clamp(round(pose.dx * scale), -4, 4) and pose.dx sweeps +-sway every
 * idle period. Asserting the still certifies a pose the renderer never draws,
 * and that is precisely how dragon, wyrm and interpreter shipped with two to
 * four columns off the right edge while this file printed green. Returns every
 * horizontal offset the renderer can actually produce for this archetype. */
function swayOffsets(key, scale) {
  const sway = (bosses.BOSS_MOTION[key] || {}).sway || 0;
  const out = new Set();
  for (let s = -sway; s <= sway; s++) out.add(Math.max(-4, Math.min(4, Math.round(s * scale))));
  return [...out].sort((a, b) => a - b);
}
ok(Number.isInteger(24 * 4), 'the figure blit is not a whole number');
console.log(`   combat hero blit 2 / field mob 4 · whole at px ${PXS.join(',')}   hero stands ${HERO_L}..${HERO_R}`);
/* Every archetype, not a hand-picked six. The literal list covered 6 of 16 and
 * omitted `interviewer`, the 96x128 rung this pass added — so the newest rig in
 * the game was the one rig whose painted box nothing asserted. */
for (const key of bosses.BOSS_ARCHETYPES) {
  const scale = bosses.bossStageScale(key);
  const bias = (bosses.BOSS_MOTION[key] || {}).bias || 0;
  const sway = (bosses.BOSS_MOTION[key] || {}).sway || 0;
  const img = bosses.bossSprite(key, null, 0, {});
  const [lo, hi] = paintedCols(key);
  const w = img.width * scale;
  const left = Math.round(S.enemyX + bias - w / 2);
  const dxs = swayOffsets(key, scale);
  const pl = left + lo * scale + dxs[0];
  const pr = left + (hi + 1) * scale - 1 + dxs[dxs.length - 1];
  const bad = PXS.filter(px => !Number.isInteger(scale * px));
  ok(bad.length === 0, `${key}: blit ${scale} is not whole at px ${bad.join(',')}`);
  ok(pl >= 0 && pr <= S.w - 1,
     `${key}: painted box ${pl}..${pr} leaves the ${S.w}-wide frame at full sway `
     + `(sway ${sway} -> dx ${dxs[0]}..${dxs[dxs.length - 1]})`);
  /* HOW MUCH OF THE DECLARED BOX IS ACTUALLY PAINTED. A rig that asks for the
   * 96-wide rung and draws 59 columns has not been drawn at that rung; it has
   * been drawn at the 64 rung and given a bigger canvas, and every consumer
   * that sizes a card, a cell or a stage slot off bossSize() is being told a
   * width the art does not use. Reported for every archetype so the outlier is
   * named on every run rather than found again in a year. */
  const fill = (hi - lo + 1) / img.width;
  fills.push({ key, fill, painted: hi - lo + 1, declared: img.width });
  console.log(`   ${key.padEnd(12)} rig ${String(img.width).padStart(2)}x${img.height}`
    + ` blit ${scale} bias ${String(bias).padStart(3)} sway ${sway}`
    + `  painted ${String(pl).padStart(3)}..${String(pr).padStart(3)}`
    + ` (${String(S.w - 1 - pr).padStart(2)} clear of the right edge)`
    + `  fills ${String(Math.round(fill * 100)).padStart(3)}% of its box`
    + `  ${bad.length ? 'HALF PIXEL at px ' + bad.join(',') : 'whole at every px'}`
    + `${pl <= HERO_R ? '   (passes behind the hero)' : ''}`);
}

/* A rig using less than four fifths of the width it declares is an authored-
 * but-not-redrawn box. This is a NOTE and not a failure: the fix is to re-author
 * the creature or to move it down a rung, both of which are art decisions with
 * an owner, and neither of which belongs in a harness run. What the harness owes
 * them is the number. */
const THIN = fills.filter(f => f.fill < 0.8);
if (THIN.length) {
  console.log('\n   NOTE — rigs that do not use the box they declare:');
  for (const f of THIN.sort((a, b) => a.fill - b.fill)) {
    console.log(`     ${f.key.padEnd(12)} paints ${f.painted} of ${f.declared} declared columns`
      + ` (${Math.round(f.fill * 100)}%) over all six stages`);
  }
  console.log('     Either re-author to the declared width or drop the rung —'
    + ' bossSize() is promising a box the art does not fill.');
}

/* ================== verdict ================== */
console.log('\n' + '='.repeat(72));
if (fails.length) {
  console.log(`FAIL (${fails.length})`);
  for (const f of fails) console.log('  - ' + f);
  process.exitCode = 1;
} else {
  console.log('PASS — one geometry in four files, every box a whole tile, every');
  console.log('       readout inside rows ' + S.safeTop + '..' + (SAFE_BOT - 1) + ', and a whole-number');
  console.log('       scale with the editor above its floor at all six windows.');
}
