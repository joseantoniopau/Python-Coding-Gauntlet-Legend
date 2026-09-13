/* §E, proved: a player must tell a Berserker from a Seer WITH THE COLOUR OFF.
 *
 * MEASURED ON THE SPRITE THE GAME DRAWS, which is the whole point of this
 * rewrite. The first version of this harness built its rigs as
 * `{ class_id: c, body: b }` with no gear and pushed them through
 * heroSilhouette() — a second code path with its own layer offsets (shield oy
 * 11 rather than armY + 1, over oy 9 rather than armY - 1, no face, no pose
 * adjustments) and a figure the game never draws, because engine.py starts
 * every armour piece at integrity 100 and the player is in a full kit from the
 * first frame of a new save. It reported a healthy cross-class minimum of 56
 * while the frames the player was actually looking at had the Warden at ZERO
 * cells from the classless hero: its tower slab sat exactly on the box the
 * aegis already filled.
 *
 * So the PASS hangs on heroFrame() driven from the default kit. The bare column
 * is kept beside it, because a class that only reads when dressed is a class
 * that vanishes the moment a piece breaks.
 *
 * Three laws, and every one of them is a number:
 *   1. every class pair differs by >= CROSS_MIN alpha cells of 384 in its WORST
 *      view, dressed — 28 views: four facings x (four walk frames, two idle,
 *      one cast)
 *   2. no rig may break into more than one 8-connected island in any view; a
 *      tell that floats off the body is a rendering bug, not a silhouette
 *   3. the classless hero is untouched by a null class
 */
import { installRaster } from './raster.mjs';
installRaster();
const S = await import('../../web/js/sprites.js');

const CLASSES = S.HERO_CLASSES, BODIES = S.HERO_BODY_TYPES;

/* THE KIT THE GAME STARTS IN. gauntlet/engine.py's new-game block writes every
 * world.ARMOR piece at integrity 100 except `legendary`, which is 0 because it
 * is unbuilt rather than broken; items.hero_look() turns that into this. It is
 * restated here rather than imported because this harness has no Python, and it
 * is restated in FULL — the tier a piece renders at is what decides whether a
 * class tell is covered by it. */
const DRESSED = {
  boot: '#8c7050', metal: '#7a6f5a', trim: '#e8c37d', tunic: '#9a7fd0',
  weapon: 'sword',
  _pieces: [
    { piece: 'boots', at: 100 }, { piece: 'gauntlets', at: 100 },
    { piece: 'shield', at: 100 }, { piece: 'helmet', at: 100 },
    { piece: 'chestplate', at: 100 }, { piece: 'legendary', at: 0 },
  ],
};
const BARE = { weapon: null };
const CROSS_MIN = 8;

const VIEWS = [];
for (const facing of ['down', 'up', 'left', 'right']) {
  for (let i = 0; i < 4; i++) VIEWS.push([facing, i, 'walk']);
  VIEWS.push([facing, 0, 'idle']); VIEWS.push([facing, 1, 'idle']); VIEWS.push([facing, 0, 'cast']);
}

const look = (base, c, b) => ({ ...base, sprite: c || undefined, body: b });
const mask = (cv) => { const m = new Uint8Array(cv.width * cv.height);
  for (let i = 0; i < m.length; i++) m[i] = cv.data[i * 4 + 3] ? 1 : 0; return m; };
const dist = (a, b) => { let n = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) n++; return n; };

/** 8-connected components on the alpha mask. Two islands means a piece of the
 *  rig is drawn in mid-air. */
function islands(cv) {
  const w = cv.width, h = cv.height, m = mask(cv), seen = new Uint8Array(w * h);
  let n = 0; const parts = [];
  for (let i = 0; i < m.length; i++) {
    if (!m[i] || seen[i]) continue;
    n++; const st = [i]; seen[i] = 1; let size = 0, lo = 99, hi = -1;
    while (st.length) {
      const p = st.pop(); size++;
      const x = p % w, y = (p - x) / w; if (y < lo) lo = y; if (y > hi) hi = y;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const nx = x + dx, ny = y + dy; if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        const q = ny * w + nx; if (m[q] && !seen[q]) { seen[q] = 1; st.push(q); }
      }
    }
    parts.push({ size, rows: `${lo}..${hi}` });
  }
  return { n, parts };
}

const fail = [];
const ROSTER = ['', ...CLASSES];

function matrix(base, label) {
  const masks = {};
  for (const c of ROSTER) masks[c] = VIEWS.map(v => mask(S.heroFrame(v[0], v[1], look(base, c, 'a'), v[2])));
  console.log(`\n${label} — WORST VIEW of 28, alpha cells differing of 384`);
  console.log('              ' + ROSTER.map(c => (c || 'classless').slice(0, 9).padStart(10)).join(''));
  let worst = Infinity, worstPair = '';
  for (const a of ROSTER) {
    const row = ROSTER.map(b => {
      if (a === b) return '-'.padStart(10);
      let w = Infinity, wv = '';
      for (let i = 0; i < VIEWS.length; i++) {
        const d = dist(masks[a][i], masks[b][i]);
        if (d < w) { w = d; wv = VIEWS[i].join('/'); }
      }
      if (w < worst) { worst = w; worstPair = `${a || 'classless'} vs ${b || 'classless'} at ${wv}`; }
      return String(w).padStart(10);
    }).join('');
    console.log('  ' + (a || 'classless').padEnd(12) + row);
  }
  return { worst, worstPair };
}

const dressed = matrix(DRESSED, 'DRESSED — the kit every save starts in');
console.log(`  worst pair anywhere: ${dressed.worstPair} = ${dressed.worst} cells  (law: >= ${CROSS_MIN})`);
if (dressed.worst < CROSS_MIN)
  fail.push(`dressed: ${dressed.worstPair} differ by ${dressed.worst} cells (< ${CROSS_MIN})`);

const bare = matrix(BARE, 'BARE — every piece broken, for reference only');
console.log(`  worst pair anywhere: ${bare.worstPair} = ${bare.worst} cells  (not a law)`);

/* ---- law 2: nothing floats ---- */
console.log('\nISLANDS — every rig must be one 8-connected piece in all 28 views');
let broken = 0;
for (const base of [['dressed', DRESSED], ['bare', BARE]]) {
  for (const c of ROSTER) for (const b of BODIES) {
    const bad = [];
    for (const v of VIEWS) {
      const r = islands(S.heroFrame(v[0], v[1], look(base[1], c, b), v[2]));
      if (r.n > 1) bad.push(`${v[0]}/${v[2]}${v[1]} (${r.n}: ${r.parts.slice(1).map(p => p.size + 'px rows ' + p.rows).join(', ')})`);
    }
    if (bad.length) {
      broken += bad.length;
      console.log(`  ${base[0]} ${(c || 'classless').padEnd(11)} body ${b}: ${bad.length}/28 BROKEN`);
      for (const s of bad.slice(0, 4)) console.log(`      ${s}`);
      fail.push(`${base[0]} ${c || 'classless'}/${b} breaks into islands on ${bad.length} of 28 views`);
    }
  }
}
if (!broken) console.log('  all 28 views of all 14 rigs, dressed and bare: one piece each');

/* ---- law 3: the generic hero is the generic hero ---- */
let moved = 0;
for (const v of VIEWS) {
  moved += dist(mask(S.heroFrame(v[0], v[1], { ...DRESSED }, v[2])),
                mask(S.heroFrame(v[0], v[1], { ...DRESSED, class_id: null, body: 'a' }, v[2])));
}
console.log(`\nTHE CLASSLESS HERO under a null class: ${moved} cells moved (law: 0)`);
if (moved !== 0) fail.push(`the classless hero changed shape (${moved} cells)`);

/* ---- body a vs body b still differ ---- */
console.log('\nBODY a vs b, dressed, worst view of 28');
for (const c of ROSTER) {
  let w = Infinity;
  for (const v of VIEWS) {
    w = Math.min(w, dist(mask(S.heroFrame(v[0], v[1], look(DRESSED, c, 'a'), v[2])),
                         mask(S.heroFrame(v[0], v[1], look(DRESSED, c, 'b'), v[2]))));
  }
  console.log(`  ${(c || 'classless').padEnd(12)} ${w}`);
  if (w === 0) fail.push(`body a and body b are identical for ${c || 'classless'} in at least one view`);
}

if (fail.length) { console.log('\nFAIL'); for (const f of fail) console.log('  ' + f); process.exit(1); }
console.log('\nPASS — twelve silhouettes told apart with the colour off, on the kit the');
console.log('       game actually draws; nothing floats; the classless hero is untouched.');
