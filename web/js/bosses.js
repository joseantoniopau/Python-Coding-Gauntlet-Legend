/* Boss art: fourteen authored creatures, generated at runtime.
 *
 * Nothing here is traced, sampled or derived from any existing game, film or
 * franchise. "Lich, dragon, knight" are archetypes as old as the woodcut; these
 * are drawn fresh as pixel grids and rasterised at load, the same way sprites.js
 * and tiles.js do everything else. There are no image assets and there must not
 * be any.
 *
 * Why this module exists at all: sprites.bossSprite draws a 48x48 mirrored half
 * and gets its animation from one generic deformation. That is fine for a trash
 * mob promoted to a miniboss. It is not fine for the thing the player has spent
 * twenty minutes earning, which is on screen for six phases and is the only
 * moment the game has that the player will describe to someone else afterwards.
 * So the bosses move out of the mob pipeline and get their own:
 *
 *   64x64, or 96x64 for the winged and serpentine ones, DRAWN AT 1.75 with its
 *     feet under the floor — 112 pixels against the hero's 72, reaching from
 *     just under the ceiling of the stage down through the ground line. A boss
 *     the same height as the thing fighting it is a mob with more health.
 *   Five frames — idle, the exhale, a wind-up, the attack, and a hurt pose —
 *     and six BEATS inside the idle loop, which each moving part reads at its
 *     own rate. Uniform motion is the tell of cheap animation, and the fix is
 *     not more frames, it is parts that disagree about where they are.
 *   Three PHASES. The fight already had six (world.BOSS_PHASES); until now the
 *     art did not know about any of them. Now the armour opens along authored
 *     fault lines, the plate spalls, and a core lights inside and throws its
 *     light back onto the creature's own bone and chrome.
 *   Separate animated parts: a jaw, a wing, a tail, an orbiting skull, a chain.
 *   A contre-jour rim in the boss's own colour, because the stage is near-black
 *     and a near-black creature on it is a hole, not a silhouette.
 *   An ENTRANCE: four beats, up through the floor, rim first, crown last.
 *
 * Fifteen colours, and this file now holds to it. The whole bestiary is inside
 * the budget — worst case fifteen exactly — which it was not before: the way
 * a boss carrying steel AND bone AND gold AND a tabard fits is that the dark
 * end of every hard material is ONE tone, the void and the outline are ONE
 * tone, and a chrome specular and a chain highlight are the same pixel. That
 * is rule 1 of docs/08-art-direction.md doing the job it is there to do.
 *
 * It reuses the sprites.js engine rather than reimplementing it. That matters:
 * ramp() is what makes generated art read as 16-bit instead of plastic, and a
 * second copy of it would drift.
 *
 * Determinism: every sprite is keyed on (archetype, colour, frame, phase, beat)
 * and cached. Wear, pitting and the fault lines come from rng(hash(key)), so
 * the Hash Titan has the same scars in every session forever and cracks in the
 * same places every time it is brought to its second phase. Nothing allocates
 * inside a render loop: a whole fight's working set is 45 canvases, warmBoss()
 * builds one phase of it in one call, and 3600 drawn frames after that cost
 * zero allocations.
 */

/* Single line on purpose: the project's parse check strips /^import.*$/ per
 * line, and a wrapped import statement leaves its own tail behind. */
import { ramp, mix, shade, rng, hash, drawGrid, applyRim, normalise, shiftRows, bobGrid, sinkRows, squashRows, widenRows, drawGroundShadow } from './sprites.js';

export const BOSS_ART_VERSION = 3;

/* One box height for every boss, so the battle layer never has to special-case
 * a vertical offset. Width is the only thing that varies: the winged and the
 * serpentine ones need the extra 32 columns or their wings get amputated. */
export const BOSS_H = 64;
export const BOSS_W = 64;
export const BOSS_WIDE_W = 96;

/* ---------------- glyph table ----------------
 * Every grid in this file draws from exactly this set. Anything else is a typo,
 * and drawGrid silently skips unknown glyphs, so the harness checks for them.
 *
 *   .    transparent
 *   o    hard outline, near-black bruised toward the body hue
 *   O    lit outline, upper left            (written by applyRim)
 *   Q    contre-jour rim in the boss colour (written by rimPass)
 *   B    undecided body mass                (resolved by applyRim)
 *   H L  lit tones, d D shadow tones        (resolved by applyRim, or authored)
 *   a A  accent base / accent light
 *   k    void black: eye sockets, a visor slit, an open maw
 *   e    eye socket rim   w eye white   W hot white
 *   g G n   steel: base / spec / shadow
 *   b C c   bone: base / lit / shadow
 *   t T s   cloth: base / lit / shadow
 *   r R f   ember: mid / hot / deep
 *   u U     rune glow in the boss colour / its white-hot core
 *   x X     blood crimson / its highlight
 *   z Z     gold / its highlight
 *   j J     bark and timber, dark / lit
 *   i       cold cyan: frost, a lens, a judging eye
 *   m M     iron chain, dark / spec
 *   l       leather strap
 */
export const BOSS_GLYPHS = 'oOQBHLdDaAkewWgGnbCctTsrRfuUxXzZjJimMl';

/* The palette is a superset of sprites.enemyPalette's, so a grid can move
 * between the two files without being recoloured. Materials that are not the
 * creature — steel, bone, gold — hold their own hue and do NOT take the boss
 * colour, otherwise every boss becomes a monochrome study and the accent stops
 * meaning anything. Only o/O/Q/u and the body ramp carry identity.
 *
 * `phase` is the third dimension, and it is where a fight stops looking like
 * one drawing with a health bar beside it. See BOSS_PHASE for what the three
 * states mean; here is what they do to the light:
 *
 *   whole    as authored. Cold metal, cold bone.
 *   cracked  the body ramp is scorched — shadows deepen and rotate toward the
 *            void, the rim cools, the tabard goes black with dried blood.
 *   core     something inside is burning and lighting the outside. The body
 *            ramp takes the accent, the contre-jour rim goes hot, and — the
 *            part that matters for the bible — bone and chrome pick that light
 *            up in their speculars while keeping their own hue. Chrome lit by
 *            a furnace is still chrome; chrome tinted the colour of a furnace
 *            is plastic.
 */
export function bossPalette(base, accentHex, phase = 0) {
  const ph = phase | 0;
  const cracked = ph === 1, lit = ph >= 2;
  const src = base || '#8a8f9c';
  const acc = accentHex || ramp(src).light2;
  const r = ramp(lit ? mix(src, acc, 0.22) : src);
  const a = ramp(acc);
  const heat = a.light2;
  const steel = ramp('#8d94a6');
  const bone = ramp('#d6d0bb');
  const cloth = ramp(mix(src, '#171320', cracked ? 0.66 : 0.58));
  const gold = ramp('#d9a63c');
  const blood = ramp('#8e1d28');
  const wood = ramp('#6a4d33');
  /* One knob, used everywhere a material should show that it is standing in
   * the core's light rather than being made of it. */
  const seen = (hex, t) => (lit ? mix(hex, heat, t) : cracked ? mix(hex, '#0c0a14', t * 0.9) : hex);
  /* The shared dark. Every hard material's deepest step collapses onto ONE
   * tone: steel's shadow, bone's shadow and an eye socket's rim are the same
   * pixel value. This is not a shortcut — it is rule 1 of the art direction
   * (docs/08), and it is what keeps a boss carrying steel AND bone AND gold
   * AND a tabard inside the fifteen-colour budget. Collapsing the dark ends is
   * also simply true: in a near-black ambient every material converges. */
  const deep = seen(mix(steel.shadow2, bone.shadow1, 0.5), 0.08);
  const spec = seen(steel.light2, 0.3);
  return {
    o: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),
    O: lit ? mix(r.rim, heat, 0.45) : r.rim,
    Q: lit ? mix(r.light1, heat, 0.55) : mix(r.light1, src, cracked ? 0.48 : 0.3),
    D: cracked ? mix(r.shadow2, '#07060c', 0.35) : r.shadow2,
    d: cracked ? mix(r.shadow1, '#0b0912', 0.28) : r.shadow1,
    B: r.base, L: r.light1, H: lit ? mix(r.light2, heat, 0.3) : r.light2,
    a: a.base, A: a.light2,
    // The void and the outline are one colour. Every sprite here pays for its
    // outline already; an eye socket, a visor slit, an open maw and a fresh
    // fissure are all the same absence of light, and charging a separate
    // palette slot for each of them is what puts a boss over budget.
    k: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),
    // e/c/n are one tone; w is bone-white; M is the steel specular. Six glyphs,
    // three colours, and no sprite pays for a distinction it never shows.
    e: deep, n: deep, c: deep,
    w: seen(bone.light2, 0.3), W: '#ffffff',
    g: seen(steel.base, 0.14), G: spec, M: spec,
    b: seen(bone.base, 0.14), C: seen(bone.light2, 0.3),
    t: cloth.base, T: cloth.light1, s: cracked ? mix(r.shadow2, '#07060c', 0.35) : r.shadow2,
    r: '#ff7a24', R: '#ffd473',
    u: lit ? mix(heat, '#ffffff', 0.42) : mix(r.light2, '#ffffff', cracked ? 0.2 : 0.34),
    U: '#ffffff',
    x: cracked ? mix(blood.base, '#140610', 0.3) : blood.base, X: blood.light2,
    f: cracked ? mix(blood.base, '#140610', 0.3) : blood.base,   // ember's deep step is the blood tone
    z: seen(gold.base, 0.18), Z: seen(gold.light2, 0.34),
    j: wood.shadow1, J: wood.light1,
    i: lit ? mix('#7fe6ff', heat, 0.35) : '#7fe6ff',
    m: mix(r.outline, '#08070d', cracked ? 0.74 : 0.62),          // chain shadow is the outline
    l: wood.shadow1,
  };
}

/* ---------------- grid surgery ----------------
 * sprites.js owns the shared operations. These four are specific to bosses:
 * bosses are assembled from a mirrored body plus independent parts, which mobs
 * never are.
 */
const T = '.';
const HALF = BOSS_W / 2;   // 32 authored columns become 64 drawn ones

function blank(w, h) {
  const row = T.repeat(w);
  return Array.from({ length: h }, () => row);
}

function fit(row, w) { return row.length >= w ? row.slice(0, w) : row + T.repeat(w - row.length); }

function rect(grid, w) {
  const width = w || Math.max(...grid.map(r => r.length));
  return grid.map(r => fit(r, width));
}

/* Half-grids are RIGHT-ALIGNED: the last character of a row is the centre seam,
 * and a short row is padded with transparent at the OUTER edge. That one choice
 * is what makes 700 rows of hand-authored art survivable — a row's length is
 * simply that row's half-width, a miscount costs one pixel at the silhouette's
 * edge instead of tearing a hole down the creature's spine, and no leading dots
 * ever have to be typed or counted. */
function padHalf(row, w) {
  return row.length >= w ? row.slice(row.length - w) : T.repeat(w - row.length) + row;
}

function halfRect(grid, w) { return grid.map(r => padHalf(r, w || HALF)); }

/* Left half plus its reflection. Every bilaterally symmetric boss is authored
 * once; the frame deformation is applied to the mirrored result, never before,
 * or a lean to the left comes back as a symmetric bulge outward. */
function mirror(half, hw) {
  const w = hw || HALF;
  return half.map(row => {
    const s = padHalf(row, w);
    return s + [...s].reverse().join('');
  });
}

function flipX(grid) { return grid.map(r => [...r].reverse().join('')); }

/* Draw src into dst at (ox, oy). `under` writes only into transparent cells,
 * which is how a wing sits behind a body without being hand-clipped. */
function stamp(dst, src, ox, oy, under) {
  for (let y = 0; y < src.length; y++) {
    const ty = y + (oy | 0);
    if (ty < 0 || ty >= dst.length) continue;
    const row = src[y];
    const cells = dst[ty].split('');
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === T || ch === ' ') continue;
      const tx = x + (ox | 0);
      if (tx < 0 || tx >= cells.length) continue;
      if (under && cells[tx] !== T) continue;
      cells[tx] = ch;
    }
    dst[ty] = cells.join('');
  }
  return dst;
}

function at(grid, y, x) {
  const row = grid[y];
  return row === undefined ? undefined : row[x];
}
const isEmpty = ch => ch === undefined || ch === T || ch === ' ';

/* applyRim lights the upper-left outline. This lights the opposite edge in the
 * boss's own colour. Contre-jour is the cheapest separation there is, and on a
 * stage this dark it is the difference between a silhouette and a hole. */
function rimPass(grid) {
  const w = Math.max(...grid.map(r => r.length));
  const g = normalise(grid, w);
  const out = g.map(r => r.split(''));
  for (let y = 0; y < g.length; y++) {
    for (let x = 0; x < w; x++) {
      if (g[y][x] !== 'o') continue;
      if (isEmpty(at(g, y + 1, x)) || isEmpty(at(g, y, x + 1))) out[y][x] = 'Q';
    }
  }
  return out.map(r => r.join(''));
}

/* Deterministic wear. Runs before applyRim so the speckles survive it: applyRim
 * only rewrites 'B', and a pitted pixel is no longer 'B'. Seeded from the art
 * key, so a boss carries the same scars in every session forever. */
function patina(grid, seed, amount, glyph) {
  const rand = rng(hash(seed) || 1);
  return grid.map(row => {
    const cells = row.split('');
    for (let x = 0; x < cells.length; x++) {
      if (cells[x] !== 'B') continue;
      if (rand() < amount) cells[x] = glyph;
    }
    return cells.join('');
  });
}

/* ---------------- damage as art ----------------
 * The phase system, at the grid level. The requirement is that a phase change
 * be legible with the health bar covered up: not a tint, but a different
 * object. Three passes do it, and they run in this order because each one
 * reads what the last one wrote.
 */

/* Every glyph that counts as the creature's own mass. Cracks run through these
 * and stop at bone-white teeth, at a lit core, and at the outline — a fissure
 * that crosses an eye socket reads as a drawing mistake, not as damage. */
const MASS = 'BLHdDgGnbCcaAxXzZjJ';   // cloth is not in it: robes tear, they do not crack
const isMass = ch => MASS.indexOf(ch) >= 0;

/* One fissure, walked downward from an anchor with a deterministic wobble.
 * The crack itself is void; the pixel on its lit side takes the glow glyph, so
 * at phase 2 the fissure is a seam of light rather than a black scratch. */
function fissure(cells, ox, oy, len, rand, glow, wide) {
  let x = ox;
  for (let i = 0; i < len; i++) {
    const y = oy + i;
    const row = cells[y];
    if (!row) break;
    if (i > 0) x += rand() < 0.36 ? (rand() < 0.5 ? -1 : 1) : 0;
    if (x < 1 || x >= row.length - 1) break;
    if (!isMass(row[x])) { if (row[x] === T || row[x] === 'o' || row[x] === 'O' || row[x] === 'Q') break; continue; }
    if (isMass(row[x - 1])) row[x - 1] = glow;
    row[x] = 'k';
    if (wide && i % 2 === 0 && isMass(row[x + 1])) row[x + 1] = 'k';
  }
}

/* Cracked armour. `faults` are authored anchors in assembled-grid coordinates:
 * the two or three places on THIS creature where a blow would actually open it
 * — a shoulder seam, a sternum, the join above a haunch. Scattering them by
 * rng instead would put a fissure through a horn. */
function fracture(grid, seed, phase, faults) {
  if (!phase || !faults || !faults.length) return grid;
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  const rand = rng(hash(`${seed}|fault`) || 7);
  const glow = phase >= 2 ? 'U' : 'u';
  for (let i = 0; i < faults.length; i++) {
    const f = faults[i];
    const len = (f[2] || 10) + (phase >= 2 ? 6 : 0);
    fissure(cells, f[0] | 0, f[1] | 0, len, rand, glow, phase >= 2);
    if (phase >= 2) fissure(cells, (f[0] | 0) + 2, (f[1] | 0) + 3, Math.round(len * 0.6), rand, glow, false);
  }
  /* Spall: chips knocked off the plate around each fault. Cheap, and it is
   * what stops the cracks reading as drawn-on lines. */
  for (const f of faults) {
    for (let n = 0; n < (phase >= 2 ? 7 : 4); n++) {
      const y = (f[1] | 0) + Math.floor(rand() * 12);
      const x = (f[0] | 0) - 3 + Math.floor(rand() * 7);
      const row = cells[y];
      if (!row || x < 1 || x >= row.length - 1) continue;
      if (isMass(row[x])) row[x] = rand() < 0.3 ? 'D' : 'k';
    }
  }
  return cells.map(r => r.join(''));
}

/* The core. Most of these creatures already carry one — the titan's vault
 * lock, the golem's furnace, the lich's soul in the ribs — so phase 2 promotes
 * what is there rather than pasting a second one on top: glow becomes core,
 * core becomes white. The ones that were authored cold get an anchor instead,
 * stamped only where there is already mass to burn through. */
const CORE_SEED = [
  '.ouo.',
  'ouUuo',
  'oUWUo',
  'ouUuo',
  '.ouo.',
];
const CORE_OPEN = [
  '..ouuo..',
  '.ouUUuo.',
  'ouUWWUuo',
  'uUWWWWUu',
  'ouUWWUuo',
  '.ouUUuo.',
  '..ouuo..',
];

/* Stamp that writes only over the creature's own mass, so a core opening in
 * the chest never sprays light outside the silhouette. */
function stampMasked(grid, src, ox, oy) {
  const w = Math.max(...grid.map(r => r.length));
  const cells = normalise(grid, w).map(r => r.split(''));
  for (let y = 0; y < src.length; y++) {
    const row = cells[y + (oy | 0)];
    if (!row) continue;
    for (let x = 0; x < src[y].length; x++) {
      const ch = src[y][x];
      if (ch === T || ch === ' ') continue;
      const tx = x + (ox | 0);
      if (tx < 0 || tx >= row.length) continue;
      if (!isMass(row[tx]) && row[tx] !== 'k' && row[tx] !== 'u' && row[tx] !== 'U') continue;
      row[tx] = ch;
    }
  }
  return cells.map(r => r.join(''));
}

function ignite(grid, phase, core) {
  if (phase < 2) return grid;
  const hot = grid.map(row => row.replace(/U/g, 'W').replace(/u/g, 'U'));
  return core ? stampMasked(hot, CORE_OPEN, core[0] - 3, core[1] - 3) : hot;
}

function ember(grid, phase, core) {
  if (phase !== 1 || !core) return grid;
  return stampMasked(grid, CORE_SEED, core[0] - 2, core[1] - 2);
}

/* Lean a row range progressively, one pixel per `every` rows. Necks, tails and
 * chains all bend rather than slide, and a uniform shiftRows cannot do that. */
function skewRows(grid, from, to, total) {
  const w = Math.max(...grid.map(r => r.length));
  const g = normalise(grid, w);
  const span = Math.max(1, to - from);
  const out = g.slice();
  for (let y = from; y <= to && y < g.length; y++) {
    const dx = Math.round(((y - from) / span) * total);
    if (dx === 0) continue;
    const row = g[y];
    out[y] = dx > 0 ? fit(T.repeat(dx) + row, w) : fit(row.slice(-dx) + T.repeat(-dx), w);
  }
  return out;
}

function filledBounds(grid) {
  let top = grid.length, bottom = 0;
  for (let y = 0; y < grid.length; y++) {
    if (/[^. ]/.test(grid[y])) { if (y < top) top = y; bottom = y; }
  }
  if (top > bottom) { top = 0; bottom = grid.length - 1; }
  return [top, bottom];
}

/* ================================================================
 * FRAMES
 * ================================================================
 * Five, not four. The fourth requirement was "idle breathing", and a single
 * idle frame does not breathe — it needs an exhale to breathe against. So the
 * idle loop is 0 <-> 1 and the fight states are 2, 3, 4.
 *
 * A frame that differs by six units of brightness is not a frame. Every pose
 * below moves actual mass: the chest drops, the weight shifts onto the back
 * foot, the whole body crosses three pixels of ground.
 */
export const BOSS_FRAME = Object.freeze({ IDLE: 0, BREATHE: 1, WINDUP: 2, ATTACK: 3, HURT: 4 });
export const BOSS_FRAME_NAMES = Object.freeze(['idle', 'breathe', 'windup', 'attack', 'hurt']);
export const BOSS_FRAME_COUNT = BOSS_FRAME_NAMES.length;

/* The table the battle layer drives. `hold` is in milliseconds; a hold of 0 on
 * windup means "use this boss's own telegraph length", because a lich winding
 * up and a behemoth winding up are not the same amount of warning. `loop` marks
 * the two frames that belong to the ambient idle cycle. */
export const BOSS_FRAME_TABLE = Object.freeze({
  idle:    Object.freeze({ index: 0, hold: 560, next: 'breathe', loop: true }),
  breathe: Object.freeze({ index: 1, hold: 560, next: 'idle', loop: true }),
  windup:  Object.freeze({ index: 2, hold: 0, next: 'attack', loop: false }),
  attack:  Object.freeze({ index: 3, hold: 240, next: 'idle', loop: false }),
  hurt:    Object.freeze({ index: 4, hold: 200, next: 'idle', loop: false }),
});

export function frameIndex(frame) {
  if (typeof frame === 'number') return ((frame | 0) % BOSS_FRAME_COUNT + BOSS_FRAME_COUNT) % BOSS_FRAME_COUNT;
  const row = BOSS_FRAME_TABLE[String(frame || 'idle').toLowerCase()];
  return row ? row.index : 0;
}

/* ================================================================
 * PHASES
 * ================================================================
 * The fight already has phases. gauntlet/world.py BOSS_PHASES names six of
 * them — recognize, explain, implement, edges, complexity, variant — and
 * fx.bossIntro lights one pip per phase before the first cast. Until now none
 * of that reached the art: the creature that opened the fight was, pixel for
 * pixel, the creature that closed it.
 *
 * Six art states would be six sprite sets nobody can tell apart. Three can be
 * read across a room, so the six fight phases fold onto three looks:
 *
 *   whole    intact. This is the thing that walked in.
 *   cracked  armour opened along its real seams, plate chipped, the light on
 *            it gone cold. It has been hurt and it is not hiding it.
 *   core     the fissures are lit from inside, the core is open, and the
 *            creature's own light is falling on its bone and its chrome.
 *
 * bossPhase() takes whatever the caller already has — a world.py phase key, a
 * phase index out of a count, fx's lit-pip count, or a health fraction — and
 * returns one of the three. Nothing new has to be plumbed for the art to start
 * answering the fight.
 */
export const BOSS_PHASE = Object.freeze({ WHOLE: 0, CRACKED: 1, CORE: 2 });
export const BOSS_PHASE_NAMES = Object.freeze(['whole', 'cracked', 'core']);
export const BOSS_PHASE_COUNT = BOSS_PHASE_NAMES.length;

/* The six fight phases of world.BOSS_PHASES, mapped onto the three looks. The
 * break lands where the fight's own difficulty breaks: naming and explaining
 * cost it nothing, implementing opens it, and the last two are fought against
 * something already burning. */
export const BOSS_PHASE_FOR_KEY = Object.freeze({
  recognize: 0, explain: 0,
  implement: 1, edges: 1,
  complexity: 2, variant: 2,
  // the encounter kinds, for a caller holding those instead
  pattern_encounter: 0, communication: 0, code_battle: 1,
  edge_case_trap: 1, complexity_duel: 2, memory_ambush: 2,
});

export function phaseIndex(phase) {
  if (typeof phase === 'number' && Number.isFinite(phase)) {
    return Math.max(0, Math.min(BOSS_PHASE_COUNT - 1, phase | 0));
  }
  const row = BOSS_PHASE_FOR_KEY[String(phase || '').toLowerCase()];
  return row === undefined ? 0 : row;
}

/* Accepts, in order of preference: an explicit art phase; a world.py phase key
 * or an index-out-of-count; fx's pipsLit/pips; a health fraction. Anything it
 * cannot read is phase 0, because a boss that arrives already cracked has
 * thrown away the only moment where cracking it means something. */
export function bossPhase(state) {
  if (state === undefined || state === null) return 0;
  if (typeof state === 'number') {
    // A bare number is a fraction of health remaining when it is in [0,1] and
    // not a whole number; otherwise it is an art phase index.
    if (state > 0 && state < 1) return state > 0.66 ? 0 : state > 0.33 ? 1 : 2;
    return phaseIndex(state);
  }
  if (typeof state === 'string') return phaseIndex(state);
  if (state.artPhase !== undefined) return phaseIndex(state.artPhase);
  if (state.phaseKey !== undefined) return phaseIndex(state.phaseKey);
  const of = (n, total) => {
    if (!(total > 1)) return 0;
    const t = Math.max(0, Math.min(1, n / (total - 1)));
    return t < 0.34 ? 0 : t < 0.7 ? 1 : 2;
  };
  if (typeof state.phase === 'string') return phaseIndex(state.phase);
  if (Number.isFinite(state.phase) && Number.isFinite(state.phases)) return of(state.phase, state.phases);
  if (Number.isFinite(state.pipsLit) && Number.isFinite(state.pips)) return of(state.pipsLit - 1, state.pips);
  if (Number.isFinite(state.hp) && Number.isFinite(state.hpMax) && state.hpMax > 0) {
    const left = state.hp / state.hpMax;
    return left > 0.66 ? 0 : left > 0.33 ? 1 : 2;
  }
  if (Number.isFinite(state.phase)) return phaseIndex(state.phase);
  return 0;
}

/* ---------------- the beat ----------------
 * Six sub-positions inside the idle loop. The five frames carry the POSE; the
 * beat carries the parts, and every part reads it at its own rate — a jaw at
 * 1.0, a wing at 0.5, a tail at 0.75, a chain at 1.5. That is the whole fix
 * for "uniform motion reads as cheap": with one clock and four rates nothing
 * on the creature is ever at the top of its arc at the same time as anything
 * else, and the eye cannot find the loop.
 *
 * Beats are quantised rather than continuous because a frame is a cached
 * canvas, not a transform. Six is the smallest number that still hides the
 * loop at the idle period the creatures run at, and it costs twelve cached
 * idle frames per boss per phase.
 */
export const BOSS_BEATS = 6;
const TAU = Math.PI * 2;

/* Beat 0 is the authored pose exactly — every drift is measured RELATIVE to
 * it. That is what keeps reduced motion, and every existing caller that never
 * passes a beat, looking like the art as drawn. */
function driftAt(d, beat) {
  if (!d || !beat) return [0, 0];
  const at = (b) => Math.sin(TAU * ((d.rate === undefined ? 1 : d.rate) * b / BOSS_BEATS + (d.phase || 0)));
  const k = at(beat) - at(0);
  return [Math.round((d.x || 0) * k), Math.round((d.y || 0) * k)];
}

/* ---------------- pose kit ----------------
 * Six motion styles cover fourteen creatures. Each takes the assembled,
 * already-mirrored body and returns the deformation for one frame. Horizontal
 * work happens here and not on the half, for the reason given at mirror().
 */
const POSES = {
  /* Anything with feet and too much mass to be quick about it. */
  heavy(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(widenRows(g, bottom - 4, bottom - 1), top, top + 5, 1);
    if (f === 2) return shiftRows(bobGrid(g, -1), top, mid + 2, -3);
    if (f === 3) return squashRows(shiftRows(g, top, mid + 4, 4), bottom - 6, bottom - 1);
    if (f === 4) return shiftRows(sinkRows(g, top, top + 3, 1), top, bottom, -3);
    return g;
  },
  /* No feet. The whole body rises and falls, and the lean is from the waist. */
  float(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return bobGrid(g, 1);
    if (f === 2) return shiftRows(bobGrid(g, -3), top, mid, -2);
    if (f === 3) return shiftRows(bobGrid(g, 2), top, mid + 3, 5);
    if (f === 4) return shiftRows(bobGrid(g, 1), top, bottom, -4);
    return g;
  },
  /* Winged. The exhale is a downbeat, the wind-up is a rear back. */
  flap(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(g, top, top + 8, 1);
    if (f === 2) return shiftRows(bobGrid(g, -2), top, mid, -3);
    if (f === 3) return shiftRows(bobGrid(g, 1), top, mid + 2, 6);
    if (f === 4) return shiftRows(bobGrid(g, 1), top, bottom, -4);
    return g;
  },
  /* Serpentine. Everything bends progressively rather than sliding. */
  coil(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return skewRows(g, top, bottom, 2);
    if (f === 2) return skewRows(g, top, mid, -4);
    if (f === 3) return skewRows(g, top, mid, 7);
    if (f === 4) return shiftRows(skewRows(g, top, bottom, -2), top, bottom, -3);
    return g;
  },
  /* Machinery. It does not breathe, it indexes. Motion is stepped and square. */
  tick(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return sinkRows(g, top, mid, 1);
    if (f === 2) return shiftRows(g, top, mid, -2);
    if (f === 3) return shiftRows(g, top, mid, 4);
    if (f === 4) return shiftRows(sinkRows(g, top, mid, 2), top, bottom, -2);
    return g;
  },
  /* Rooted. The base never moves; only the crown answers the wind. */
  root(g, f) {
    const [top, bottom] = filledBounds(g);
    const mid = Math.round((top + bottom) / 2);
    if (f === 1) return shiftRows(g, top, top + 10, 1);
    if (f === 2) return skewRows(g, top, mid, -4);
    if (f === 3) return skewRows(g, top, mid, 6);
    if (f === 4) return skewRows(shiftRows(g, top, mid, -2), top, mid, -3);
    return g;
  },
};

/* ================================================================
 * THE LICH
 * ================================================================
 * A robed skeletal caster that never touches the ground. The read, in order of
 * how fast the eye gets it: enormous skull, gold circlet, hollow sockets with
 * one point of cold light each, bone pauldrons spiked outward, a robe that
 * narrows to rags. Three independent parts — the staff, the rune it carries,
 * and the hem — so the silhouette is never rigid.
 *
 * Half-grid, right-aligned: the last character of each row is the centre seam.
 */
const LICH_BODY = [
  '',
  'o..o..o',
  'oZo.oZooZ',
  'oCZooCZCoC',
  'oCCCCCCCCC',
  'ozZzZzZzZz',
  'obbbbbbbbb',
  'obzzzzzzzz',
  'occcccbbbbb',
  'obkkkkbbbbb',
  'obkkukbbbbb',
  'obkkkkbbbbb',
  'obbkkbbbbbb',
  'obbbbbbbbbb',
  'occbbbbbbkk',
  'occzzzzzzkk',
  'obCbCbCbCb',
  'occcccccccc',
  'ooooooooo',
  'obCb',
  'obzb',
  'obCbb',
  'occbbbbb',
  'oZo....occbbbbb',
  'oZzo...occbbbbbb',
  'oZbzCoocbbbbbbbbb',
  'oczzzzzcbbbbbbbbbb',
  'oooooooootttttttttt',
  'ozzzzzzzzzzzzzzzzzz',
  'ottttttttttttttttt',
  'otttttttzzztttttt',
  'ottttttzZUZzttttt',
  'otttttuuZuutttttt',
  'ottttuUUUUuttttttt',
  'otttttuuZuuttttttt',
  'ottttttzzzttttttt',
  'ottttttttttttttt',
  'osttttttttttttttt',
  'osttttttttttttttt',
  'osstttttttttttttt',
  'osstttttttttttttttt',
  'ossttttttttttttttt',
  'osssttttttttttttttt',
  'osssttttttttttttttt',
  'ossssttttttttttttttt',
  'ossssttttttttttttttt',
  'osssssttttttttttttttt',
  'osssssttttttttttttttt',
  'ossssssttttttttttttttt',
  'ossssssttttttttttttttt',
  'osssssstttttttttttttttt',
  'osssssttttttttttttttttt',
  'oossssttzzzzzzzzzzzzzz',
  'ooooooooooooooooooooo',
];

/* The staff. Bone shaft, a claw at the head, a rune stone in the claw. Drawn
 * whole rather than mirrored because it lives on one side only. */
const LICH_STAFF = [
  '..ouo..',
  '.ouUuo.',
  'ouUUUuo',
  'ouUUUuo',
  '.ouUuo.',
  '..ouo..',
  '.oZoZo.',
  'oZo.oZo',
  'oZbbbZo',
  '.oZbZo.',
  '..ozo..',
  '..obo..',
  '..oCo..',
  '..obo..',
  '..ozo..',
  '..oCo..',
  '..obo..',
  '..obo..',
  '..ozo..',
  '..obo..',
  '..obo..',
  '..oCo..',
  '..ozo..',
  '..obo..',
  '..oCo..',
  '..obo..',
  '..ozo..',
  '..oCo..',
  '..obo..',
  '..obo..',
  '..ozo..',
  '..obo..',
  '..obo..',
  '..ozzo.',
  '..ooo..',
];

/* The rune stone, lit hotter, on the wind-up and the attack. */
const LICH_STAFF_LIT = LICH_STAFF.map((row, y) => (y > 5 ? row
  : row.replace(/u/g, 'U').replace(/o/g, 'u')));

/* Rags. Drawn under the body so the robe's own outline stays the read. */
const LICH_HEM = [
  '..o...oo....o..oo...o....oo..o..',
  '..o...oo....o..oo...o....oo..o..',
  '.os...os....os.os...os...os..os.',
  '.os...os....os.os...os...os..os.',
  '..o....o....os.os...o....os...o.',
  '..o....o.....o.o....o....o....o.',
  '..o.........o.o.....o.........o.',
  '............o.o...............o.',
];

/* An orbiting soul-light. Its own layer, its own path: it is the only thing on
 * the sprite that moves when the body does not. */
const LICH_ORB = [
  '..ouo..',
  '.ouUuo.',
  'ouUWUuo',
  'ouUUUuo',
  '.ouUuo.',
  '..ouo..',
];

/* ================================================================
 * THE DRAGON
 * ================================================================
 * 96x64, side-on, facing the hero. Five layers: a wing behind everything, the
 * tail behind the body, the torso and legs, the neck and skull, and a lower jaw
 * that drops on its own. Assembling it this way rather than as one grid is what
 * lets the neck lash forward on the attack while the haunches stay planted,
 * which is the entire difference between a dragon and a dragon-shaped statue.
 */
const DRAGON_BODY = [
  '.............ooooooo........',
  '..........oooBBBBBBBooo.....',
  '........ooBBnGGGGGnBBBBoo...',
  '.......oBBBnGGGGGGGGGnBBBo..',
  '......oBBBnGGnBBBBBnGGnBBBo.',
  '.....oBBBBnGnBBBBBBBnGnBBBBo',
  '....oBBBBBBBBBBBBBBBBBBBBBBo',
  '...oBBBBBBBBBBBBBBBBBBBBBBBo',
  '..oBBBBBBBBBBBBBBBBBBBBBBBBo',
  '..oBBBBBBBBBBBBBBBBBBBBBBBBo',
  '.oBBBBBBBBBBBBBBBBBBBBBBBBBo',
  '.oaaBBBBBBBBBBBBBBBBBBBBBBBo',
  '.oaaaBBBBBBBBBBBBBBBBBBBBBBo',
  '.oaaaaBBBBBBBBBBBBBBBBBBBBo.',
  '.oaaaaaBBBBBBBBBBBBBBBBBBBo.',
  '.oaaaaaaBBBBBBBBBBBBBBBBBBo.',
  '.oaaaaaaaBBBBBBBBBBBBBBBBBo.',
  '.oaaaaaaaaBBBBBBBBBBBBBBBBo.',
  '..oaaaaaaaBBBBBBBBBBBBBBBBo.',
  '..ooaaaaaaBBBBBBBBBBBBBBBo..',
  '....oaaaaaBBBBBBBBBBBBBBo...',
  '....oBBBBBBo.oBBBBBBBBBBo...',
  '....oBBBBBo...oBBBBBBBBBo...',
  '....oBBBBo.....oBBBBBBBBo...',
  '....oBBBo......oBBBBBBBBo...',
  '...oBBBBo......oBBBBBBBBBo..',
  '...oBBBBo......oBBBBBBBBBo..',
  '..oBBBBBo......oBBBBBBBBBBo.',
  '..oBBBBo........oBBBBBBBBBo.',
  '.oBBBBBo........oBBBBBBBBBBo',
  '.oBBBBBo........oBBBBBBBBBBo',
  'oGnGnGo..........oBBBBBBBBBo',
  'oGGGGGo..........oBCBCBCBBBo',
  'oooooo............oCCCCCCCoo',
  '...................oooooooo.',
];

/* Skull and neck. The neck is authored as a curve so the lash on frame 3 is a
 * skew of something already bent, not a straight rod pivoting. */
const DRAGON_NECK = [
  '...............oo......oo.......',
  '..............oCo.....oCo.......',
  '.............oCCo....oCCo.......',
  '........ooooooCCooooooCCo.......',
  '......ooBBBBBBBBBBBBBBCo........',
  '....ooBBBBBBBBBBBBBBBBo.........',
  '..ooBBBBBBBBBBBBBBBBBBo.........',
  '.oBBBBBBBBBBBBBBBBBBBBo.........',
  'oBBweBBBBBBweBBBBBBBBBBo........',
  'oBweeBBBBBweeBBBBBBBBBBo........',
  'oBBweBBBBBBweBBBBBBBBBBBo.......',
  'oBBnGGnBBBBBBBBBBBBBBBBBBo......',
  'oBBnGGnBBBBBBBBBBBBBBBBBBo......',
  '.oCoCoCoCoBBBBBBBBBBBBBBo.......',
  '..ooooooooBBBBBBBBBBBBBBo.......',
  '.........oBBBBBBBBBBBBBBGo......',
  '.........ooGGGGGGGGGGGGGGo......',
  '..........oaanGGGGGGGGGGGo......',
  '..........oaaaBBBBBBBBBBBGo.....',
  '...........oaaaBBBBBBBBBBGo.....',
  '...........oaaaaBBBBBBBBBGo.....',
  '............oaaaBBBBBBBBBBGo....',
  '............oaaaaBBBBBBBBBGo....',
  '.............oaaaBBBBBBBBBGo....',
  '.............oaaaaBBBBBBBBBGo...',
  '..............oaaaBBBBBBBBBGo...',
  '..............oaaaaBBBBBBBBBGo..',
  '...............oaaaBBBBBBBBBGo..',
  '...............oaaaaBBBBBBBBBGo.',
  '................oaaaBBBBBBBBBGo.',
];

/* The lower jaw is its own layer. On the attack it drops four pixels and the
 * throat behind it lights. */
const DRAGON_JAW = [
  'oooooooooo.....',
  'oCoCoCoCoBo....',
  'oBBBBBBBBBo....',
  '.oBBBBBBBBo....',
  '..oooooooo.....',
];

const DRAGON_JAW_OPEN = [
  'okkkkkkkkkko...',
  'ouukkkkkkkkBo..',
  'oUUuukkkkkkBo..',
  'oCoCoCoCoCoBo..',
  'oBBBBBBBBBBBo..',
  '.oBBBBBBBBBBo..',
  '..ooooooooooo..',
];

/* Membrane wing: four fingers, a clawed thumb at the leading edge, and a
 * membrane that is one tone darker than the body so it reads as translucent. */
const DRAGON_WING = [
  '..............................ono.....',
  '.........................ooooonGGo....',
  '.....................oooodDDDDnGo.....',
  '..................ooodDDDDDDDDdo......',
  '...............oooDDDDDDDDDDDdo.......',
  '.............ooDDDDDDDDDDDDDdo........',
  '...........ooDDDDDDDDDDDDDDBo.........',
  '.........ooDDDDDDDDDDDDDDDBo..........',
  '.......ooDDDDDDDDDDDDDDDDBo...........',
  '.....ooDDDDDDGoDDDDDDDDDBo............',
  '....oDDDDDDDGo.oDDDDDDDGo.............',
  '...oDDDDDDDGo...oDDDDDGBo.............',
  '..oDDDDDDDGo....oDDDDDGo..............',
  '..oDDDDDDGo.....oDDDDGo...............',
  '.oDDDDDDGo......oDDDDGo...............',
  '.oDDDDDDGo......oDDDGo................',
  'oDDDDDDGo.......oDDDGo................',
  'oDDDDDGo........oDDGo.................',
  'oDDDDGo.........oDDGo.................',
  'oDDDGo..........oDGo..................',
  'oDDGo...........oDGo..................',
  'oDGoo...........oGo...................',
  'oGdo............oGo...................',
  'oodo.............oo...................',
  '.oo...................................',
];

/* Tail, tapering to a bladed fluke. Skewed per frame, so it trails. */
const DRAGON_TAIL = [
  '....................ooo.....',
  '.................oooBBBoo...',
  'oooo...........ooBBBBBBBBo..',
  'oBBBoo......oooBBBBBBBBBBo..',
  'oBBBBBoooooBBBBBBBBBBBBBo...',
  '.oBBBBBBBBBBBBBBBBBBBBBo....',
  '..oGnGnGnGnGoBBBBBBBBoo.....',
  '...ooooooooooooooooooo......',
];

/* ================================================================
 * THE KNIGHT  —  worn by The Interviewer
 * ================================================================
 * Full plate, a great helm with nothing behind the visor slit but a cold light,
 * a tower shield and a greatsword. The final boss of a game about interviews is
 * a faceless thing in mirror-polished armour holding a rubric, so the shield
 * carries a graded sigil and the tabard is blood over bone.
 *
 * Steel does not take the boss colour — g/G/n hold their own hue. Only the rim,
 * the visor light and the tabard shift with it, which is what keeps chrome
 * reading as chrome instead of as tinted plastic.
 */
const KNIGHT_BODY = [
  '',
  'o..o..o',
  'oCooCCoC',
  'oCCGGGGGG',
  'oGGGGGGGGG',
  'ogggggggggg',
  'ogGGGGGGGGgg',
  'onmMmggggggg',
  'okkkkkkkkkkk',
  'okkiWikkkkkk',
  'onmMmggggggg',
  'onnggggggggg',
  'onngggkikgggg',
  'onnggMMMggggg',
  'onngggkikgggg',
  'onnggggggggggg',
  'onnnggggggggg',
  'ooonggggggg',
  'onnggggg',
  'oGo...onngggggg',
  'oGGGo..onnggMMgggg',
  'oGGGGGoonnggMMggggg',
  'oggggGGGonngggggggggg',
  'ongggggGGGonngggggggggg',
  'onngggggggGGonnggggggggggg',
  'onnnggggggggGonnggggggggggggg',
  'oonnggggggggonnggggggggggggggg',
  'oonnggggggonnxxxxxxxxxxxxxxxx',
  'oonnggggonnxxxxxxxxxxxxxxxxx',
  'oonngggonnxxxxxxxxxxxxxxxxx',
  'oonnggonnxxxxxxxxzzzxxxxxxx',
  'ooooonnxxxxxxxzZZZzxxxxxx',
  'oonnxxxxxxxzZZZzxxxxxx',
  'oonnxxxxxxxxzzzxxxxxxx',
  'oonngxxxxxxxxxxxxxxxxx',
  'oonnggxxxxxxxxxxxxxxxx',
  'oonngggxxxxxxxxxxxxxxx',
  'oonnggggxxxxxxxxxxxxxx',
  'oonngggggxxxxxxxxxxxxx',
  'oonngggggxxxxxxxxxxxxx',
  'oonnggggggxxxxxxxxxxxx',
  'oonggggggxxxxxxxxxxxx',
  'ooggggggxxxxxxxxxxxx',
  'oggggggo..xxxxxxxxxx',
  'ognMMngo..oxxxxxxxxx',
  'ognMMngo...oxxxxxxxx',
  'ognMMngo....oxxxxxxx',
  'ognMMngo.....oxxxxxx',
  'ognMMngo......oxxxxx',
  'ognMMngo.......oxxxx',
  'ognMMngo........oxxo',
  'oggggggo.........oo.',
  'ongggggno...........',
  'onggMMggno..........',
  'onggMMggno..........',
  'onnggggggno.........',
  'oGGGGGGGGGo.........',
  'oggggggggggo........',
  'oooooooooooo........',
];

/* Tower shield. Its own layer so it can be raised into a guard on the hurt
 * frame — a boss that only ever attacks is a punching bag with a health bar. */
const KNIGHT_SHIELD = [
  'oooooooooooooo',
  'oGGGGGGGGGGGGo',
  'ogggggggggggGo',
  'ogzzzzzzzzzzgo',
  'ogzxxxxxxxxzgo',
  'ogzxggggggxzgo',
  'ogzxgooooGxzgo',
  'ogzxgoiWoGxzgo',
  'ogzxgoWioGxzgo',
  'ogzxgooooGxzgo',
  'ogzxgGGGGGxzgo',
  'ogzxxxxxxxxzgo',
  'ogzzzzzzzzzzgo',
  'oggggggggggggo',
  'ogggggggggggGo',
  'oonggggggggGoo',
  '..onnggggGGo..',
  '...onnggGGo...',
  '....onnGGo....',
  '.....oooo.....',
];

/* Greatsword. Point-down in the guard, overhead on the wind-up, driven through
 * the floor on the attack. */
const KNIGHT_SWORD = [
  '..ooo..',
  '.oGGGo.',
  '.ozZzo.',
  '.ozZzo.',
  '.oGGGo.',
  'ooooooo',
  'oGGGGGo',
  '.oggo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '.oGGo..',
  '..oGo..',
  '..oo...',
];

/* Same blade, edge lit — the telegraph. A held weapon that does not change
 * value between wind-up and swing reads as a still image with motion lines. */
const KNIGHT_SWORD_LIT = KNIGHT_SWORD.map(row => row.replace(/G/g, 'W').replace(/g/g, 'i'));

/* ================================================================
 * THE TITAN  —  Hash Titan, and the shape the others are measured against
 * ================================================================
 * A walking vault: iron mask with no face behind it, shoulders wider than the
 * head is tall, a ring of keys on a chain that never stops swinging. The chain
 * is a separate layer for exactly that reason.
 */
const TITAN_BODY = [
  '',
  'oGo......oo',
  'oGGo....oGGo',
  'oGGooooGGGo',
  'oGGGGGGGGo',
  'ogggggggggg',
  'ogGGGGGGGGgg',
  'oggggggggggg',
  'okkkkkkkkkkkk',
  'okkuuukkkkkkk',
  'okkkkkkkkkkkk',
  'ogggggggggggg',
  'ogGGGGGGGGGGgg',
  'oggggggggggggg',
  'oooooooooooooo',
  'ozzzzzzzzzz',
  'ozzzzzzzzzz',
  'ooooo..ogggggggg',
  'oGGGGooogGGGGGGggg',
  'oGGGGGGGGggggggggggg',
  'oggggggggggggggggggggg',
  'onggggggggggggggggggggg',
  'onngggggggoBBBBBBBBBBBBB',
  'onnnggggggoBBBBBBBBBBBBBB',
  'onnnggGGggoBBBzzzzzzzzzBBB',
  'onnnggggggoBBBzBBBBBBBzBBB',
  'oonnggggggoBBBzBuuuuBzBBBB',
  'oonnggggggoBBBzuUUUUuzBBBB',
  'ooonnggggoBBBBzBuuuuBzBBBB',
  'oonnggggoBBBBBzBBBBBBzBBBB',
  'oonngggoBBBBBBzzzzzzzzBBBB',
  'oonggggoBBBBBBBBBBBBBBBBBB',
  'oogggggoBBBBBBBBBBBBBBBBBB',
  'ogggggoBBBBBBBBBBBBBBBBBBB',
  'ooooooooBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBB',
  'ozzzzzzzzzzzzzzzzz',
  'ozzzzzzzzzzzzzzzzz',
  'oBBBBBBBBBBBBBBBB',
  'oBBBgggggggggBBBB',
  'oBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBB',
  'ooooooooooooo',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oggggggggo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oggggggggo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBo.....',
  'oBBBBBBBBBo....',
  'oBBBBBBBBBo....',
  'ozzzzzzzzzo....',
  'oBBBBBBBBBBo...',
  'oBBBBBBBBBBo...',
  'ooooooooooooo..',
];

/* Vault keys on a chain, swinging off the right shoulder. */
const TITAN_CHAIN = [
  'oMo',
  'omo',
  'oMo',
  'omo',
  'oMo',
  'omo',
  'oMo',
  'omo',
  'ozo',
  'ozzo',
  'ozZzo',
  'ozzzzo',
  'ozZzzo',
  '.ozzo.',
  '..ozzo',
  '...ozo',
  '...ozo',
  '..ooo.',
];

/* ================================================================
 * THE COLOSSUS  —  the Rolling Titan
 * ================================================================
 * Two bosses in world.py share the sprite key "titan", and two identical
 * silhouettes in one playthrough is a bug the player sees. This is the second:
 * hunched, asymmetric, a drum of wound cable for a shoulder and a maul it drags
 * rather than carries.
 */
const COLOSSUS_BODY = [
  '',
  '..........oo',
  '.........oGGo',
  '........oGGGGo',
  '.......oggggggo',
  '.......ogkkkkkgo',
  '.......ogkuuukggo',
  '.......ogkkkkkggg',
  '.......oggggggggg',
  '.......oGGGGGGGGG',
  '.......ooggggggggg',
  '.........oooooooooo',
  '............ozzzzzzz',
  'oooo........ozzzzzzz',
  'oMMMoo......oBBBBBBBB',
  'oMmmMMoooooooBBBBBBBBB',
  'oMmmmmMMMMMMMBBBBBBBBBB',
  'oMmmmmMoooooooBBBBBBBBBBB',
  'oMmmmMo......oBBBBBBBBBBBBB',
  'oMMMMo.......oBBBBBBBBBBBBBB',
  '.oooo........oBBBBBBBBBBBBBBB',
  '.............oBBBBuuuuuBBBBBBB',
  '............oBBBuUUUUUuBBBBBBB',
  '............oBBBBuuuuuBBBBBBBB',
  '............oBBBBBBBBBBBBBBBBB',
  '...........oBBBBBBBBBBBBBBBBBB',
  '...........oBBBBBBBBBBBBBBBBBB',
  '..........oBBBBBBBBBBBBBBBBBBB',
  '..........ogggggggggggggggggggg',
  '.........oggggggggggggggggggggg',
  '.........oggggggggggggggggggggg',
  '........oonnggggggggggggggggggg',
  '.......oonnnggggggggggggggggggg',
  '......oonnnngggggggggggggggggg',
  '......onnnnggggggggggggggggg',
  '......onnnggggggggggggggg',
  '......ooogggggggggggggg',
  '........oggggggggggggo',
  '........oooooooooooooo',
  'oggggggggo.....',
  'oggggggggo.....',
  'onnggggggo.....',
  'onnggggggo.....',
  'onnnggggggo....',
  'onnnggggggo....',
  'oGGGGGGGGGo....',
  'oggggggggggo...',
  'ogggggggggggo..',
  'ooooooooooooo..',
];

/* The maul. Dragged on idle, hauled up on the wind-up, through the floor on 3. */
const COLOSSUS_MAUL = [
  '.ooooooooo.',
  'oMMMMMMMMMo',
  'oMnnnnnnnMo',
  'oMnggggGnMo',
  'oMnggggGnMo',
  'oMnnnnnnnMo',
  'oMMMMMMMMMo',
  '.ooonnnooo.',
  '...ongno...',
  '...ongno...',
  '...ongno...',
  '...onGno...',
  '...ongno...',
  '...ongno...',
  '...ongno...',
  '...onnno...',
  '....ooo....',
];

/* ================================================================
 * THE HYDRA  —  96x64
 * ================================================================
 * A low serpentine torso and three necks, each its own layer on its own phase.
 * The whole point of the creature is that the heads are not synchronised: cut
 * the animation down to one rigid grid and it stops being a hydra.
 */
const HYDRA_BODY = [
  '.................oooooo.................',
  '..............ooooBBBBBoooo.............',
  '...........oooBBBBBBBBBBBBBooo..........',
  '.........ooBBBBBBBBBBBBBBBBBBBoo........',
  '.......ooBBBBBBBBBBBBBBBBBBBBBBBoo......',
  '......oBBBBBBBBBBBBBBBBBBBBBBBBBBBo.....',
  '.....oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo....',
  '....oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo...',
  '...oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo..',
  '..oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo.',
  '..oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo.',
  '.oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo',
  '.oBBBBBBBBBBBBaaaaaaaaaaaaaBBBBBBBBBBBBo',
  '.oBBBBBBBBBBaaaaaaaaaaaaaaaaaBBBBBBBBBBo',
  '.oBBBBBBBBBaaaaaaaaaaaaaaaaaaaBBBBBBBBBo',
  '.oBBBBBBBBaaaaaaaaaaaaaaaaaaaaaBBBBBBBBo',
  '.oBBBBBBBaaaaaaaaaaaaaaaaaaaaaaaBBBBBBBo',
  '..oBBBBBBaaaaaaaaaaaaaaaaaaaaaaaBBBBBBo.',
  '..oBBBBBBBaaaaaaaaaaaaaaaaaaaaaBBBBBBBo.',
  '...oBBBBBBBaaaaaaaaaaaaaaaaaaaBBBBBBBo..',
  '....oBBBBBBBBaaaaaaaaaaaaaaaBBBBBBBBo...',
  '.....oBBBBBBBBBBaaaaaaaaaBBBBBBBBBBo....',
  '...oooBBBBBBBBBBBBBBBBBBBBBBBBBBBooo....',
  '..oBBBoooBBBBBBBBBBBBBBBBBBBooooBBBoo...',
  '..oBBBBBooooBBBBBBBBBBBBBoooBBBBBBBBBo..',
  '..oCoCoCoooooooooooooooooooCoCoCoCoCoo..',
  '...ooooo...................ooooooooo....',
];

/* One neck. Drawn once, drawn three times, at three offsets and three phases. */
const HYDRA_NECK = [
  '..ooooooo..',
  '.oBBBBBBBo.',
  'oBBweBBBBBo',
  'oBweeBBBBBo',
  'oBBweBBBBBo',
  'oBBBBBBBBBo',
  'oBCoCoCoBBo',
  '.ooooooBBBo',
  '.....oBBBBo',
  '.....oBBBBo',
  '....oBBBBo.',
  '....oBBBBo.',
  '....oBBBo..',
  '....oBBBo..',
  '...oBBBBo..',
  '...oBBBBo..',
  '...oBBBBo..',
  '...oBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBBo.',
  '..oBBBBBBo.',
  '.oBBBBBBBo.',
];

const HYDRA_NECK_BITE = [
  'ooooooooo..',
  'oBBBBBBBBo.',
  'oBweBBBBBo.',
  'oweeBBBBBo.',
  'oBweBBBBBBo',
  'oBBBBBBBBBo',
  'oCoCoCoBBBo',
  'okkkkkoBBBo',
  'oCoCoCoBBBo',
  '.ooooooBBBo',
  '.....oBBBBo',
  '.....oBBBBo',
  '....oBBBBo.',
  '....oBBBBo.',
  '....oBBBo..',
  '....oBBBo..',
  '...oBBBBo..',
  '...oBBBBo..',
  '...oBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBo..',
  '..oBBBBBBo.',
  '.oBBBBBBBo.',
];

/* ================================================================
 * THE WRAITH
 * ================================================================
 * A hood with nothing in it but two points of light, skeletal hands, and a
 * shroud that never resolves into legs. The shroud tails are separate layers
 * with separate phases, which is what stops it reading as a bell.
 */
const WRAITH_BODY = [
  '',
  '.......ooooo',
  '.....ootttttt',
  '....ottttttttt',
  '...ottttttttttt',
  '..otttsssssttttt',
  '..ottsskkkksstttt',
  '.ottsskkkkkksstttt',
  '.ottskkkkkkkkkstttt',
  '.otsskkkukkkkkkkttt',
  '.otsskkkkkkkkkkkkkt',
  '.ottskkkkkkkkkkkkkt',
  '.ottsskkkkkkkkkkkkt',
  '.otttsskkkkkkkkkkkt',
  '.ottttsskkkkkkkkkkt',
  '.otttttssskkkkkkkkt',
  '.ottttttsssskkkkkkt',
  '.otttttttttsssskkkt',
  '.ottttttttttttssskt',
  '.otttttttttttttttst',
  'oCCo.ottttttttttttt',
  'oCCCo.ottttttttttttt',
  'oCbCCo.ottttttttttttt',
  'oCbbCCo.ottttttttttttt',
  '.oCbbCo..ottttttttttttt',
  '..oCCo....otttttttttttttt',
  '...oo.....ottttttttttttttt',
  '..........ottttttttttttttts',
  '.........ottttttttttttttttts',
  '.........otttttttttttttttttts',
  '........ottttttttttttttttttts',
  '........otttttttttttttttttttt',
  '.......osttttttttttttttttttttt',
  '.......osstttttttttttttttttttt',
  '......ossstttttttttttttttttttt',
  '......ossstttttttttttttttttttt',
  '.....osssstttttttttttttttttttt',
  '.....osssstttttttttttttttttttt',
  '....ossssstttttttttttttttttttt',
  '....osssssstttttttttttttttttt',
  '...osssssssttttttttttttttttt',
  '...ossssssstttttttttttttttt',
  '..osssssssstttttttttttttt',
  '..osssssssstttttttttttt',
  '.ooosssssssttttttttt',
  '...oosssssstttttt',
  '.....oossssttt',
  '.......ooooo',
];

const WRAITH_TAIL = [
  '..o....o.....o..',
  '..o....o.....o..',
  '.os...os....os..',
  '.os...os....os..',
  '.os...os....os..',
  '..o...os.....o..',
  '..o....o.....o..',
  '..o....o........',
  '.......o........',
];

/* ================================================================
 * THE BEHEMOTH
 * ================================================================
 * Front-on quadruped. The head sits LOW, under the shoulder line, with tusks
 * that clear the jaw and a row of plates running up the spine behind it. That
 * one relationship — head below shoulders — is what makes it read as an animal
 * instead of a person in a costume, and it is the only boss in the file built
 * that way.
 */
const BEHEMOTH_BODY = [
  '',
  '',
  'oaao',
  'oaaao......oao',
  'oaaaao....oaaao',
  'oBBBBBoo.ooaaaao',
  'oBBBBBBBoooBBBBBBo',
  'ooBBBBBBBBBBBBBBBBoo',
  'oBBBBBBBBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBBBBBBBBBBBo',
  'oBBBBaaaBBBBBBBBBBBBBBBBo',
  'oBBBaaaaaBBBBBBBBBaaaBBBBo',
  'oBBBaaaaaBBBBBBBBaaaaaBBBBo',
  'oBBBBaaaBBBBBBBBBaaaaaBBBBB',
  'oBBBBBBBBBBBBBBBBBaaaBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBoooooooooo',
  'oBBBBBBBBBBBBBBBoobbbbbbbbbb',
  'oBBBBBBBBBBBBBBobbbbbbbbbbbb',
  'oBBBBBBBBBBBBBobbbkkkbbbbbbb',
  'oBBBBBBBBBBBBobbbbkrkbbbbbbb',
  'oBBBBBBBBBBBobbbbbkkkbbbbbbb',
  'oBBBBBBBBBBobbbbbbbbbbbbbbbb',
  'oBBBBBBBBBoobbbbbbbbbbbbbbbb',
  'oCoBBBBBBBoobbbbbbbbbbbbbbbb',
  'oCCoBBBBBBoobbbbbbbbbbbbbbbb',
  'oCCCoBBBBBoobbCoCoCoCoCoCoCo',
  'oCCCCoooooooobokkkkkkkkkkkkk',
  '.oCCCCCoooooobbCoCoCoCoCoCoC',
  '..oCCCCCoobbbbbbbbbbbbbbbbbb',
  '...ooooooobbbbbbbbbbbbbbbbbb',
  'oBBBBoooooobbbbbbbbbbbbbbbbb',
  'oBBBBBBBooobbbbbbbbbbbbbbbbb',
  'oBBBBBBBBBoooooooooooooooooo',
  'oBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBo....oBBBBBBBBBBBB',
  'oBBBBBBBBBo.....oBBBBBBBBBBBB',
  'oBBBBBBBBBo.....oBBBBBBBBBBBB',
  'oBBBBBBBBBo.....oBBBBBBBBBBBB',
  'oBBBBBBBBBo.....oBBBBBBBBBBBB',
  'oggggggggo......ogggggggggggo',
  'oBBBBBBBBo......oBBBBBBBBBBBo',
  'oCoCoCoCo.......oCoCoCoCoCoCo',
  'ooooooooo.......ooooooooooooo',
];

/* Tail, whipping behind the right haunch. */
const BEHEMOTH_TAIL = [
  '...........ooo',
  '.........ooBBo',
  '.......ooBBBo.',
  '.....ooBBBBo..',
  '...ooBBBBo....',
  '.ooBBBBo......',
  'oBBBBo........',
  'oBBBo.........',
  'oaao..........',
  'oao...........',
  'oo............',
];

/* ================================================================
 * THE GOLEM
 * ================================================================
 * Quarried, not grown. Slab head with no face, a core burning between the
 * shoulders, and two rune tablets that orbit on their own layer — the only
 * thing about it that looks alive.
 */
const GOLEM_BODY = [
  '',
  '..........ooooooooooo',
  '.........oBBBBBBBBBBB',
  '.........oBBBDBBBBBBB',
  '.........oBBBBBBBBBBB',
  '.........oBBBBoooooooo',
  '.........oBBBBokkkkkkk',
  '.........oBBBBokuuuuuu',
  '.........oBBBBokkkkkkk',
  '.........oBBBBoooooooo',
  '.........oBBBDBBBBBBBB',
  '.........oBBBBBBBBBBBB',
  '.........ooooooooooooo',
  '............oBBBBBBBBB',
  '............ooooooooooo',
  'oooooo......oBBBBBBBBBBB',
  'oBBBBBooooooBBBDBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBDBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBDBBBBBBB',
  'ooooooBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBoooBBBBBBBBBBBB',
  'oBBBBBBBBBBo.oBBBBooooooooo',
  'oBBBDBBBBBBo.oBBBokuuuuuuuu',
  'oBBBBBBBBBBo.oBBBokuUUUUUUU',
  'oBBBBBBBBBo..oBBBokuUUWWWWW',
  'oooooBBBBBo..oBBBokuUUUUUUU',
  'oBBBBBBBBBo..oBBBokuuuuuuuu',
  'oBBBBBBBBo...oBBBooooooooooo',
  'oBBBBBBBBo...oBBBBBBBBBBBBBB',
  'oBBBDBBBBo...oBBBBBBBBBBBBBB',
  'oBBBBBBBo....oBBBDBBBBBBBBBB',
  'ooooooooo....oBBBBBBBBBBBBBB',
  'oBBBBBBo.....oBBBBBBBBBBBBBB',
  'oBBBBBBo.....ooooooooooooooo',
  'oBBBBBBo.......oBBBBBBBBBBBB',
  'oBBBBBBo.......oBBBDBBBBBBBB',
  'oBBBBBBo.......oBBBBBBBBBBBB',
  'ooooooo........oBBBBBBBBBBBB',
  '...............ooooooooooooo',
  'oBBBBBBBBBBo......',
  'oBBBDBBBBBBo......',
  'oBBBBBBBBBBo......',
  'ooooooooooooo.....',
  'oBBBBBBBBBBBo.....',
  'oBBBBBDBBBBBo.....',
  'oBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBBo...',
  'oooooooooooooo....',
];

/* Rune tablets. They orbit; the body does not. */
const GOLEM_RUNE = [
  'oooooo',
  'oBuuBo',
  'ouUUuo',
  'oBuuBo',
  'oBBBBo',
  'oooooo',
];

/* ================================================================
 * THE ENT
 * ================================================================
 * A tree that noticed you. Root legs spread wider than the trunk, a face read
 * out of a knot in the bark, and a canopy that carries the whole silhouette.
 * Rooted motion: the base never moves, only the crown answers.
 */
const ENT_BODY = [
  '',
  '.........oo...oo..oo',
  '......oooaaoooaaooaao',
  '....ooaaaaBaaaaaBaaaao',
  '...oaaaaaaaBaaaaBaaaaao',
  '..oaaaBBaaaaaaaaaaaBBaao',
  '.oaaaBBBaaaaaaaaaaBBBaaa',
  'oaaaaBBaaaaaaBBaaaaBBaaaa',
  'oaaaaaaaaaaaBBBBaaaaaaaaa',
  'oaaBBaaaaaaaaBBaaaaaBBaaa',
  'oaBBBBaaaaaaaaaaaaaBBBBaa',
  'oaaBBaaaaaaBBaaaaaaaBBaaa',
  '.oaaaaaaaaaBBBaaaaaaaaaaa',
  '..oaaaaBBaaaBBaaaaBBaaaaa',
  '...ooaaBBBaaaaaaaaBBaaaaa',
  '.....ooaaBaaaaaaaaaaaaaaa',
  '.......oooaaaaaaaaaaaaaaa',
  '..........ooaaaaBBaaaaaaa',
  '...........oooaaaaaaaaaaa',
  '..............oooaaaaaaaa',
  '................ojjjjjjjj',
  '...............ojjjjjjjjj',
  '..............ojjjjjjjjjj',
  '.............ojjjjjjjjjjj',
  '.............ojjokkojjjjj',
  '............ojjokrrkojjjj',
  '............ojjokkkkojjjj',
  '............ojjjokkojjjjj',
  '...........ojjjjjjjjjjjjj',
  '...........ojjjjjJJjjjjjj',
  '...........ojjjjjjjjjjjjj',
  '..........ojjjooooooooooo',
  '..........ojjokCkCkCkCkCk',
  '..........ojjokkkkkkkkkkk',
  '..........ojjjokCkCkCkCkC',
  '.........ojjjjjooooooooooo',
  '.........ojjjjjjjjjjjjjjjj',
  '........ojjjjJjjjjjjJjjjjj',
  '........ojjjjJjjjjjjJjjjjj',
  '.......ojjjjjJjjjjjjJjjjjj',
  '.......ojjjjjJjjjjjjJjjjjj',
  '......ojjjjjjJjjjjjjJjjjjj',
  '......ojjjjjjJjjjjjjJjjjjj',
  '.....ojjjjjjjJjjjjjjJjjjjj',
  '.....ojjjjjjjJjjjjjjJjjjjj',
  '....ojjjjjjjjJjjjjjjJjjjjj',
  '....ojjjjoojjjjjjjjjjjjjjj',
  '...ojjjjo..ojjjjjjjjjjjjjj',
  '..ojjjjo....ojjjjjjjjjjjjj',
  '..ojjjo......ojjjjjjjjjjjj',
  '.ojjjo........ojjjjjjjjjjj',
  'ojjjo..........ojjjjjjjjjj',
  'ojjo............ojjjjjjjjj',
  'ojo.............ojjjjjjjjj',
  'oo..............ojjjjjjjjj',
  '................ooooooooooo',
];

/* A branch arm, hung off the trunk and swinging on its own period. */
const ENT_BRANCH = [
  'ooo...........',
  'ojo...........',
  'ojjoo.........',
  '.ojjjoo.......',
  '..ojjjjoo.....',
  '...oojjjjoo...',
  '.....oojjjjo..',
  '.......oojjjo.',
  '.........ojjjo',
  '.........oaajo',
  '........oaaao.',
  '........oaao..',
  '.........oo...',
];

/* ================================================================
 * THE NECROMANCER
 * ================================================================
 * The lich's living predecessor: a hood with a face still under it, a grimoire
 * held open, and a summoned skull orbiting the free hand. Deliberately smaller
 * in the shoulders than the lich, so the two read apart at a glance even though
 * they share a robe.
 */
const NECRO_BODY = [
  '',
  '............oooo',
  '..........ootttto',
  '.........otttttttt',
  '........ottttttttt',
  '.......ottttttttttt',
  '.......ottttsssssstt',
  '......ottsskkkkkksst',
  '......ottskkkkkkkkks',
  '......otskkkuukkkkkk',
  '......otskkkkkkkkkkk',
  '......ottskkkkkkkkkk',
  '......ottsskkkkkkkkk',
  '.......ottssskkkkkkk',
  '.......otttssssskkkk',
  '........ottttttsssss',
  '.........ootttttttttt',
  '............ottttttttt',
  '...........otttttttttttt',
  '.........oottttttttttttttt',
  '.......ootttttttttttttttttt',
  '......ottttttttttttttttttttt',
  '.....otttttttttttttttttttttt',
  '.....ottttttttttttttttttttttt',
  'ooo..ottttttttttttttttttttttt',
  'ojjo.ottttttttttttttttttttttt',
  'ojJjooottttttuuuuutttttttttttt',
  'ojJJjooottttuUUUUUuttttttttttt',
  'ojJJJjootttttuuuuutttttttttttt',
  'ojJJjoo.ottttttttttttttttttttt',
  'ojjoo...osttttttttttttttttttttt',
  'ooo.....osstttttttttttttttttttt',
  '........ossstttttttttttttttttttt',
  '.......ossssttttttttttttttttttt',
  '.......osssstttttttttttttttttt',
  '......ossssstttttttttttttttttt',
  '......ossssstttttttttttttttttt',
  '.....osssssstttttttttttttttttt',
  '.....osssssstttttttttttttttttt',
  '....ossssssstttttttttttttttttt',
  '....ossssssstttttttttttttttttt',
  '...osssssssstttttttttttttttttt',
  '...osssssssstttttttttttttttttt',
  '..ossssssssstttttttttttttttttt',
  '..ossssssssstttttttttttttttttt',
  '.osssssssssstttttttttttttttttt',
  '.osssssssssstttttttttttttttttt',
  'ooooooooooooooooooooooooooooo',
];

/* The summoned skull. It orbits the free hand and it is the one thing on the
 * sprite that is not made of cloth. */
const NECRO_SKULL = [
  '.oooooo.',
  'obbbbbbo',
  'obkkbkkb',
  'obkkbkkb',
  'obbbbbbo',
  'obCbCbCo',
  '.oooooo.',
];

/* ================================================================
 * THE AUTOMATON
 * ================================================================
 * Brass, rivets and one cold lens. It does not breathe — the pose kit gives it
 * `tick`, stepped motion with no easing — and the only organic thing about the
 * silhouette is that the gear in its chest never stops turning. The gear and
 * the piston arm are separate layers so they can run at different rates, which
 * is what sells "machine" rather than "robot suit".
 */
const AUTOMATON_BODY = [
  '',
  '..........oooooooo',
  '.........oggggggggo',
  '.........ogGGGGGGGgo',
  '.........ognnnnnnngo',
  '.........ognkkkkkngo',
  '.........ognkiiikngo',
  '.........ognkiWikngo',
  '.........ognkiiikngo',
  '.........ognkkkkkngo',
  '.........ogGGGGGGGgo',
  '.........oggggggggggo',
  '..........oooooooooooo',
  '............omomomomom',
  '............omomomomom',
  '..........ooogggggggggg',
  'ooooo....oogggggggggggggo',
  'oggggoooogggggggggggggggggo',
  'ogGGGggggggggggggggggggggggo',
  'ognnnggggggggggggggggggggggg',
  'ognggggggggggggggggggggggggg',
  'ogggggggggooooooooooggggggggg',
  'ogggggggggo........ogggggggggg',
  'onngggggggo........ogggggggggg',
  'onnggggggo..........ogggggggggg',
  'onnggggggo..........ogggggggggg',
  'onnnggggo...........ogggggggggg',
  'onnnggggo...........ogggggggggg',
  'ooonggggo..........ogggggggggg',
  '..ongggggo.........ogggggggggg',
  '..onggggggoooooooooggggggggggg',
  '..onggggggggggggggggggggggggg',
  '..onnggggggggggggggggggggggg',
  '...onnggggggggggggggggggggg',
  '...oonnnggggggggggggggggggg',
  '.....ooonnggggggggggggggggg',
  '........ooogggggggggggggggg',
  '..........ozzzzzzzzzzzzzzzz',
  '..........ozzzzzzzzzzzzzzzz',
  '..........ogggggggggggggggg',
  '.........oggggggggo....ogggo',
  '.........oggggggggo....ogggo',
  '........oggggggggo.....ogggo',
  '........omomomomo......ogggo',
  '........omomomomo......ogggo',
  '........oggggggggo.....ogggo',
  '.......oggggggggggo....ogggo',
  '.......oggggggggggo....ogggo',
  '.......ogGGGGGGGGgo....ogggo',
  '......ogggggggggggo...oggggo',
  '......oooooooooooo....ooooo',
];

/* A real gear: teeth on the rim, spokes across the bore. Four rotations, one
 * per quarter turn, indexed by frame. Rotating it at draw time would mean a
 * transform per frame; four authored grids mean none. */
const AUTOMATON_GEAR = [
  '..ozo..ozo..',
  '.ozZo.ozZo..',
  'oozzooozzoo.',
  'ozzzzzzzzzzo',
  'ozzooozzozzo',
  'ozzo.ozzo.zo',
  'ozzooozzooZo',
  'ozzzzzzzzzzo',
  'oozzooozzoo.',
  '.ozZo.ozZo..',
  '..ozo..ozo..',
];

const AUTOMATON_GEAR_TURNED = [
  '.ozo..ozo...',
  'ozZoo.ozZo..',
  'ozzzzoozzzo.',
  'oozzzzzzzzoo',
  '.ozzooozzzzo',
  'ozzoo.ozzozo',
  'ozzzoozzzoZo',
  'oozzzzzzzzoo',
  '.ozzzooozzo.',
  '.ozZo.ozZoo.',
  '..ozo..ozo..',
];

/* The piston arm: a rod in a sleeve. Extends four pixels on the attack. */
const AUTOMATON_PISTON = [
  'ooooo',
  'ogGgo',
  'ogngo',
  'ogngo',
  'ooooo',
  '.ono.',
  '.oMo.',
  '.ono.',
  '.oMo.',
  '.ono.',
  '.oMo.',
  'ooooo',
  'ogGgo',
  'ogngo',
  'ooooo',
];

/* ================================================================
 * THE DEMON
 * ================================================================
 * Horns out rather than up, a mane of live ember, a chest built like a ribcage
 * and digitigrade legs ending in hoof. Two wings and a chain flail, all three
 * on their own layers. The ember tones (r/R/f) hold their own hue against the
 * body colour on purpose: fire that takes the creature's tint stops being fire.
 */
const DEMON_BODY = [
  '',
  'oCo..............oCo',
  'oCCo............oCCo',
  '.oCCo..........oCCo',
  '..oCCo........oCCo',
  '...oCCoo....ooCCo',
  '....oCCCooooCCCo',
  '.....oCCCCCCCCCo.......rr',
  '......oCCCCCCCo.....rrRRrr',
  '.......ooooooo....rrRRRRRr',
  '.................rrRRfffRr',
  '................rrRRffffffr',
  '...............rrRRfffffffff',
  '..............rrRffffBBBBBBB',
  '.............rrRffBBBBBBBBBB',
  '............rrRfBBBBBBBBBBBB',
  '...........rrRfBBBBBBBBBBBBB',
  '..........rrRfBBoooBBBBBBBBB',
  '..........rRfBBoRRRoBBBBBBBB',
  '.........rRfBBBoRWRoBBBBBBBB',
  '.........rRfBBBBoRoBBBBBBBBB',
  '........orfBBBBBBBBBBBBBBBBB',
  '........orfBBBBBBBBBBBBBBBBB',
  '........orfBBBBBBBBoooooooooo',
  '.........ofBBBBBBBoCkCkCkCkCk',
  '.........oooBBBBBBokkkkkkkkkk',
  '...........oBBBBBBoCkCkCkCkCk',
  'ooo........oBBBBBBoooooooooooo',
  'oBBoo.....ooBBBBBBBBBBBBBBBBBB',
  'oBBBBoooooBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
  'oBBBBBBBBBBBBBBoooooBBBBBBBBBB',
  'oBBBBBBBBBBBBBoxxxxxoBBBBBBBBB',
  'oBBBBBBBBBBBBoxXXXXXxoBBBBBBBB',
  'oBBBBBBBBBBBBoxXXXXXxoBBBBBBBB',
  'oBBBBBBBBBBBBoxxxxxxxoBBBBBBBB',
  '.oBBBBBBBBBBBoxxxxxxoBBBBBBBBB',
  '..oBBBBBBBBBBBoxxxxoBBBBBBBBBB',
  '...oBBBBBBBBBBBoooooBBBBBBBBBB',
  '....oBBBBBBBBBBBBBBBBBBBBBBBBB',
  '.....oBBBBBBBBBBBBBBBBBBBBBBBB',
  '......oBBBBBBBBo....oBBBBBBBBBB',
  '......oBBBBBBBo......oBBBBBBBBB',
  '.....oBBBBBBBo.......oBBBBBBBBB',
  '.....oBBBBBBo........oBBBBBBBBB',
  '....oBBBBBBBo.......oBBBBBBBBBB',
  '....oBBBBBBBo.......oBBBBBBBBBB',
  '...oBBBBBBBBo......oBBBBBBBBBBB',
  '...oBBBBBBBo.......oBBBBBBBBBBo',
  '...oCCCCCCo........oCCCCCCCCCCo',
  '...oCCCCCo.........oCCCCCCCCCo',
  '...ooooooo.........ooooooooooo',
];

/* Bat-frame wing, drawn once and flipped for the other side. The membrane is
 * two tones under the body so it reads as skin stretched thin. */
const DEMON_WING = [
  '.......................oooo',
  '....................oooDDDo',
  '.................oooDDDDDBo',
  '..............oooDDDDDDDdo.',
  '...........oooDDDDDDDDDdo..',
  '.........ooDDDDDDDDDDDBo...',
  '.......ooDDDDDDDDDDDDBo....',
  '.....ooDDDDDDDDDDDDDBo.....',
  '....oDDDDDDDDDDDDDDBo......',
  '...oDDDDDDDdoDDDDDBo.......',
  '..oDDDDDDDdo.oDDDDBo.......',
  '..oDDDDDDdo..oDDDDBo.......',
  '.oDDDDDDdo...oDDDDBo.......',
  '.oDDDDDDdo...oDDDBo........',
  'oDDDDDDdo....oDDDBo........',
  'oDDDDDdo.....oDDBo.........',
  'oDDDDdo......oDDBo.........',
  'oDDDdo.......oDBo..........',
  'oDDdo........oDBo..........',
  'oDdo.........oBo...........',
  'oddo.........oBo...........',
  'oodo.........oo............',
  '.oo........................',
];

/* Chain and flail head. Swings wide on the wind-up and lands on 3. */
const DEMON_FLAIL = [
  'omo',
  'oCo',
  'omo',
  'oCo',
  'omo',
  'oCo',
  'ooooo',
  'oxXXo',
  'oXrRo',
  'oxXXo',
  'ooooo',
];

/* ================================================================
 * THE WYRM  —  96x64
 * ================================================================
 * No legs, no wings, and therefore no obvious way to read scale except by the
 * coils. So it is built out of coils: one authored ring stamped three times at
 * three offsets, a neck, a frilled skull and a jaw that unhinges. The `coil`
 * pose bends every row progressively, so the whole animal swims.
 */
const WYRM_COIL = [
  '.......oooooooooooo.......',
  '....oooBBBBBBBBBBBBooo....',
  '..ooBBBBBBBBBBBBBBBBBBoo..',
  '.oBBBBBBBBBBBBBBBBBBBBBBo.',
  'oBBBBBBoooooooooooBBBBBBBo',
  'oBBBBBo...........oBBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBo.............oBBBBBo',
  'oBBBBBo...........oBBBBBBo',
  'oaaaaaBoooooooooooBaaaaaao',
  'oaaaaaaaaaaaaaaaaaaaaaaaao',
  '.oaaaaaaaaaaaaaaaaaaaaaao.',
  '..ooaaaaaaaaaaaaaaaaaaoo..',
  '....oooaaaaaaaaaaaaooo....',
  '.......oooooooooooo.......',
];

const WYRM_NECK = [
  '....oooooo....',
  '..ooBBBBBBoo..',
  '.oBBBBBBBBBBo.',
  'oBBBBBBBBBBBBo',
  'oBBBBBBBBBBBBo',
  'oaaaaaaaaaaaao',
  'oaaaaaaaaaaaao',
  '.oaaaaaaaaaao.',
  '..oooooooooo..',
];

const WYRM_HEAD = [
  '..........oo.......oo.....',
  '.........oCo......oCo.....',
  '........oCCo.....oCCo.....',
  '.......oCCo.....oCCo......',
  '.oooooCCooooooooCCo.......',
  'oBBBBBBBBBBBBBBBBBoo......',
  'oBBBBBBBBBBBBBBBBBBBo.....',
  'oBBweBBBBBweBBBBBBBBo.....',
  'oweeBBBBBweeBBBBBBBBBo....',
  'oBweBBBBBBweBBBBBBBBBo....',
  'oBBBBBBBBBBBBBBBBBBBBo....',
  'oBBBBBBBBBBBBBBBBBBBBBo...',
  'oCoCoCoCoCoBBBBBBBBBBBo...',
  '.ooooooooooBBBBBBBBBBBBo..',
  '...........oBBBBBBBBBBBBo.',
  '............oaaaaaaaaaaaao',
];

const WYRM_JAW = [
  'ooooooooooo.',
  'oCoCoCoCoBo.',
  'oBBBBBBBBBo.',
  '.ooooooooo..',
];

const WYRM_JAW_OPEN = [
  'ooooooooooo.',
  'okkkkkkkkBo.',
  'oikkkkkkkBo.',
  'oiikkkkkkBBo',
  'oCoCoCoCoBBo',
  'oBBBBBBBBBBo',
  '.ooooooooooo',
];

/* A crest of fins along the spine, the only part of the wyrm that is not the
 * wyrm's own colour. */
const WYRM_FIN = [
  '..o..o...o..',
  '.oio.oio.oio',
  'oiio.oiio.io',
  'oiioooiiooio',
];

/* ================================================================
 * REGISTRY
 * ================================================================
 * One entry per archetype. `body` is the authored mass; `parts` are the layers
 * that move independently, each carrying its own five-frame offset table and,
 * where the pose genuinely changes shape rather than position, its own
 * alternate grid. `behind: true` puts a layer under the body.
 *
 * Motion metadata is not decoration. `telegraph` is how long the wind-up frame
 * is held, in milliseconds, and it is per-boss on purpose: a lich that gives
 * 900ms of warning and a demon that gives 320ms are different fights before a
 * single number changes. `scale` is what the battle stage should draw it at.
 */
const ART = {
  lich: {
    name: 'Lich', wide: false, colour: '#8f3f6f', accent: '#c7a6ff', anim: 'float',
    body: { half: LICH_BODY, oy: 1, drift: { x: 0, y: 1, rate: 1, phase: 0.25 } }, wear: 0.05,
    motion: { bob: 3, sway: 2, phase: 0.50, period: 2600, telegraph: 900 },
    stage: { scale: 1.75, sink: 11, bias: -8 },
    core: null,                                       // the reliquary is authored in the ribs
    faults: [[26, 8, 12], [38, 8, 12], [19, 26, 7], [45, 26, 7]],
    parts: [
      { name: 'hem', grid: LICH_HEM, ox: 16, oy: 53, behind: true,
        frames: [[0, 0], [0, 1], [-1, -1], [2, 2], [-2, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0.10 } },
      { name: 'staff', grid: LICH_STAFF, ox: 3, oy: 12,
        frames: [[0, 0], [0, 1], [1, -4], [4, 3], [-3, 2]],
        drift: { x: 1, y: 2, rate: 0.75, phase: 0.30 },
        alt: { 2: LICH_STAFF_LIT, 3: LICH_STAFF_LIT } },
      { name: 'soul', grid: LICH_ORB, ox: 52, oy: 20,
        frames: [[0, 0], [1, 2], [4, -4], [-8, 5], [3, 4]],
        drift: { x: 4, y: 3, rate: 1.5, phase: 0 } },
    ],
  },
  dragon: {
    name: 'Dragon', wide: true, colour: '#3f9c5a', accent: '#d8c07a', anim: 'flap',
    body: { grid: DRAGON_BODY, ox: 40, oy: 28, drift: { x: 0, y: 1, rate: 1, phase: 0.20 } }, wear: 0.04,
    motion: { bob: 3, sway: 1, phase: 0.30, period: 1500, telegraph: 520 },
    stage: { scale: 1.5, sink: 4, bias: 0 },
    core: [55, 40],                                   // furnace behind the sternum
    faults: [[30, 26, 12], [52, 34, 14], [60, 46, 10]],
    parts: [
      // The wing is the slowest thing on the creature and the jaw the fastest.
      // One clock, four rates: nothing is ever at the top of its arc twice.
      { name: 'wing', grid: DRAGON_WING, ox: 46, oy: 6, behind: true,
        frames: [[0, 0], [1, 3], [-2, -3], [3, 6], [2, 2]],
        drift: { x: 3, y: 2, rate: 0.5, phase: 0 },
        skew: [0, 2, -3, 5, 0] },
      { name: 'tail', grid: DRAGON_TAIL, ox: 62, oy: 48, behind: true,
        frames: [[0, 0], [0, 1], [2, -1], [-2, 2], [3, 1]],
        drift: { x: 2, y: 1, rate: 0.75, phase: 0.35 },
        skew: [0, 3, -4, 6, -2] },
      { name: 'neck', grid: DRAGON_NECK, ox: 13, oy: 8,
        frames: [[0, 0], [0, 1], [-3, -2], [4, 3], [-4, 2]],
        drift: { x: 1, y: 1, rate: 1, phase: 0.15 },
        skew: [0, 1, -3, 5, -2] },
      { name: 'jaw', grid: DRAGON_JAW, ox: 13, oy: 21,
        frames: [[0, 0], [0, 1], [-3, -1], [4, 6], [-4, 3]],
        drift: { x: 0, y: 1, rate: 1.5, phase: 0.5 },
        alt: { 3: DRAGON_JAW_OPEN } },
    ],
  },
  knight: {
    name: 'Knight', wide: false, colour: '#d8d8e0', accent: '#8e1d28', anim: 'heavy',
    body: { half: KNIGHT_BODY, oy: 4, drift: { x: 0, y: 1, rate: 1, phase: 0 } }, wear: 0.06,
    motion: { bob: 1, sway: 0, phase: 0.90, period: 3000, telegraph: 760 },
    stage: { scale: 1.75, sink: 9, bias: -8 },
    core: [32, 29],                                   // the reactor under the breastplate
    faults: [[24, 23, 14], [40, 23, 14], [32, 44, 12]],
    parts: [
      { name: 'shield', grid: KNIGHT_SHIELD, ox: 1, oy: 29,
        frames: [[0, 0], [0, 1], [-1, -2], [2, 2], [-3, -4]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0.20 } },
      { name: 'sword', grid: KNIGHT_SWORD, ox: 55, oy: 25,
        frames: [[0, 0], [0, 1], [1, -12], [-3, 6], [4, 3]],
        drift: { x: 1, y: 2, rate: 0.75, phase: 0.60 },
        alt: { 2: KNIGHT_SWORD_LIT, 3: KNIGHT_SWORD_LIT } },
    ],
  },
  titan: {
    name: 'Titan', wide: false, colour: '#e8a33d', accent: '#f0d79a', anim: 'heavy',
    body: { half: TITAN_BODY, oy: 6, drift: { x: 0, y: 1, rate: 1, phase: 0.5 } }, wear: 0.07,
    motion: { bob: 2, sway: 0, phase: 0.00, period: 2800, telegraph: 820 },
    stage: { scale: 1.75, sink: 10, bias: -8 },
    core: null,
    faults: [[22, 28, 14], [43, 28, 14]],
    parts: [
      { name: 'keys', grid: TITAN_CHAIN, ox: 46, oy: 27,
        frames: [[0, 0], [1, 1], [-2, -1], [3, 3], [-3, 2]],
        drift: { x: 3, y: 2, rate: 1.5, phase: 0 },
        skew: [0, 2, -3, 4, -2] },
    ],
  },
  colossus: {
    name: 'Colossus', wide: false, colour: '#3f7f9c', accent: '#a8c8d8', anim: 'heavy',
    body: { half: COLOSSUS_BODY, oy: 13, drift: { x: 0, y: 1, rate: 1, phase: 0.1 } }, wear: 0.09,
    motion: { bob: 2, sway: 1, phase: 0.62, period: 2200, telegraph: 700 },
    stage: { scale: 1.75, sink: 10, bias: -8 },
    core: null,
    faults: [[20, 30, 14], [45, 32, 12]],
    parts: [
      { name: 'maul', grid: COLOSSUS_MAUL, ox: 1, oy: 44,
        frames: [[0, 0], [0, 1], [2, -18], [6, 4], [-4, 2]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0.25 } },
    ],
  },
  hydra: {
    name: 'Hydra', wide: true, colour: '#4fb783', accent: '#d8e87a', anim: 'coil',
    body: { grid: HYDRA_BODY, ox: 28, oy: 35, drift: { x: 0, y: 1, rate: 1, phase: 0.4 } }, wear: 0.04,
    motion: { bob: 2, sway: 2, phase: 0.20, period: 1700, telegraph: 480 },
    stage: { scale: 1.5, sink: 4, bias: 0 },
    core: [48, 46],
    faults: [[36, 44, 12], [60, 44, 12]],
    parts: [
      // Three heads on three rates and three phases. Synchronise them and the
      // creature stops being a hydra and becomes a hat rack.
      { name: 'neckL', grid: HYDRA_NECK, ox: 32, oy: 18, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [-4, 3], [-3, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0 },
        skew: [-2, -3, -5, -8, -4], alt: { 3: HYDRA_NECK_BITE } },
      { name: 'neckC', grid: HYDRA_NECK, ox: 43, oy: 13,
        frames: [[0, 0], [-1, 1], [1, -3], [2, 4], [0, 2]],
        drift: { x: 1, y: 2, rate: 1, phase: 0.33 },
        skew: [0, 1, -2, 3, -1], alt: { 3: HYDRA_NECK_BITE } },
      { name: 'neckR', grid: HYDRA_NECK, ox: 53, oy: 18, flip: true, behind: true,
        frames: [[0, 0], [-1, 2], [2, -2], [5, 3], [3, 1]],
        drift: { x: 2, y: 2, rate: 1.25, phase: 0.66 },
        skew: [2, 3, 5, 8, 4], alt: { 3: HYDRA_NECK_BITE } },
    ],
  },
  wraith: {
    name: 'Wraith', wide: false, colour: '#7f6ad6', accent: '#d8d0ff', anim: 'float',
    body: { half: WRAITH_BODY, oy: 8, drift: { x: 1, y: 1, rate: 1, phase: 0.3 } }, wear: 0.03,
    motion: { bob: 4, sway: 3, phase: 0.40, period: 2300, telegraph: 560 },
    stage: { scale: 1.75, sink: 12, bias: -8 },
    core: null,
    faults: [[16, 30, 10], [46, 30, 10]],
    parts: [
      { name: 'ragL', grid: WRAITH_TAIL, ox: 12, oy: 50, behind: true,
        frames: [[0, 0], [1, 1], [-2, -1], [3, 2], [-2, 1]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0 } },
      { name: 'ragR', grid: WRAITH_TAIL, ox: 36, oy: 52, behind: true, flip: true,
        frames: [[0, 0], [-1, 2], [2, -1], [-3, 1], [2, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0.4 } },
    ],
  },
  behemoth: {
    name: 'Behemoth', wide: false, colour: '#c4553f', accent: '#f0a86a', anim: 'heavy',
    body: { half: BEHEMOTH_BODY, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.15 } }, wear: 0.08,
    motion: { bob: 2, sway: 1, phase: 0.60, period: 2000, telegraph: 600 },
    stage: { scale: 1.75, sink: 10, bias: -8 },
    core: [32, 30],
    faults: [[14, 24, 14], [50, 24, 14]],
    parts: [
      { name: 'tail', grid: BEHEMOTH_TAIL, ox: 0, oy: 34, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [3, 2], [-3, 3]],
        drift: { x: 3, y: 2, rate: 0.75, phase: 0.2 },
        skew: [0, 2, -3, 5, -3] },
    ],
  },
  golem: {
    name: 'Golem', wide: false, colour: '#8a8f9c', accent: '#5a9ec4', anim: 'heavy',
    body: { half: GOLEM_BODY, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.5 } }, wear: 0.14,
    motion: { bob: 1, sway: 0, phase: 0.10, period: 3200, telegraph: 980 },
    stage: { scale: 1.75, sink: 9, bias: -8 },
    core: null,
    faults: [[14, 32, 14], [48, 32, 14]],
    parts: [
      { name: 'runeA', grid: GOLEM_RUNE, ox: 5, oy: 21,
        frames: [[0, 0], [0, 2], [2, -4], [-4, 6], [1, 3]],
        drift: { x: 3, y: 3, rate: 1.25, phase: 0 } },
      { name: 'runeB', grid: GOLEM_RUNE, ox: 53, oy: 35,
        frames: [[0, 0], [0, -2], [-2, -5], [5, 4], [2, 2]],
        drift: { x: 3, y: 3, rate: 1.5, phase: 0.5 } },
    ],
  },
  ent: {
    name: 'Ent', wide: false, colour: '#6b8f3f', accent: '#9fd05a', anim: 'root',
    body: { half: ENT_BODY, oy: 8, drift: { x: 1, y: 0, rate: 1, phase: 0.25 } }, wear: 0.10,
    motion: { bob: 1, sway: 2, phase: 0.70, period: 3400, telegraph: 880 },
    stage: { scale: 1.75, sink: 9, bias: -8 },
    core: [32, 36],
    faults: [[22, 44, 14], [42, 44, 14]],
    parts: [
      { name: 'branch', grid: ENT_BRANCH, ox: 4, oy: 34,
        frames: [[0, 0], [1, 1], [-2, -2], [4, 3], [-3, 1]],
        drift: { x: 2, y: 2, rate: 0.5, phase: 0.15 },
        skew: [0, 2, -4, 6, -3] },
    ],
  },
  necromancer: {
    name: 'Necromancer', wide: false, colour: '#6a4f8f', accent: '#b0e0c0', anim: 'float',
    body: { half: NECRO_BODY, oy: 14, drift: { x: 0, y: 1, rate: 1, phase: 0.2 } }, wear: 0.04,
    motion: { bob: 2, sway: 1, phase: 0.50, period: 2500, telegraph: 700 },
    stage: { scale: 1.75, sink: 10, bias: -8 },
    core: null,
    faults: [[10, 25, 8], [50, 25, 8]],
    parts: [
      { name: 'skullA', grid: NECRO_SKULL, ox: 48, oy: 24,
        frames: [[0, 0], [1, 2], [3, -3], [-7, 4], [2, 3]],
        drift: { x: 3, y: 3, rate: 1.25, phase: 0.1 } },
      { name: 'skullB', grid: NECRO_SKULL, ox: 8, oy: 32,
        frames: [[0, 0], [-1, -2], [-3, -2], [6, 5], [-2, 2]],
        drift: { x: 3, y: 3, rate: 1.5, phase: 0.6 } },
    ],
  },
  automaton: {
    name: 'Automaton', wide: false, colour: '#b0763f', accent: '#7fe6ff', anim: 'tick',
    body: { half: AUTOMATON_BODY, oy: 11, drift: { x: 0, y: 1, rate: 0.5, phase: 0.25 } }, wear: 0.11,
    motion: { bob: 1, sway: 0, phase: 0.80, period: 1800, telegraph: 400 },
    stage: { scale: 1.75, sink: 9, bias: -8 },
    core: [32, 30],
    faults: [[16, 32, 14], [48, 32, 14]],
    parts: [
      // The gear indexes a quarter turn on every beat, so it keeps turning
      // while the rest of the machine is standing still. That is the whole
      // difference between a machine and a robot suit.
      { name: 'gear', grid: AUTOMATON_GEAR, ox: 26, oy: 35,
        frames: [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
        drift: { x: 1, y: 1, rate: 0.5, phase: 0.6 },
        altBeat: AUTOMATON_GEAR_TURNED,
        alt: { 1: AUTOMATON_GEAR_TURNED, 3: AUTOMATON_GEAR_TURNED } },
      { name: 'piston', grid: AUTOMATON_PISTON, ox: 4, oy: 29,
        frames: [[0, 0], [0, 1], [-2, 0], [6, 2], [-3, 1]],
        drift: { x: 0, y: 3, rate: 0.75, phase: 0.1 } },
    ],
  },
  demon: {
    name: 'Demon', wide: false, colour: '#c43f4f', accent: '#ff9d4a', anim: 'flap',
    body: { half: DEMON_BODY, oy: 11, drift: { x: 0, y: 1, rate: 1, phase: 0.35 } }, wear: 0.05,
    motion: { bob: 2, sway: 1, phase: 0.15, period: 1500, telegraph: 320 },
    stage: { scale: 1.75, sink: 10, bias: -8 },
    core: [32, 33],
    faults: [[18, 40, 12], [46, 40, 12]],
    parts: [
      // The two wings run at the same rate half a turn apart, so the downbeat
      // of one is the upbeat of the other and the thing never looks pinned.
      { name: 'wingL', grid: DEMON_WING, ox: -6, oy: 7, behind: true,
        frames: [[0, 0], [1, 3], [-2, -3], [2, 5], [1, 2]],
        drift: { x: 3, y: 2, rate: 0.5, phase: 0 },
        skew: [0, 2, -3, 4, 0] },
      { name: 'wingR', grid: DEMON_WING, ox: 43, oy: 7, behind: true, flip: true,
        frames: [[0, 0], [-1, 3], [2, -3], [-2, 5], [-1, 2]],
        drift: { x: 3, y: 2, rate: 0.5, phase: 0.5 },
        skew: [0, -2, 3, -4, 0] },
      { name: 'flail', grid: DEMON_FLAIL, ox: 52, oy: 33,
        frames: [[0, 0], [1, 1], [4, -6], [-8, 8], [3, 3]],
        drift: { x: 4, y: 3, rate: 1.5, phase: 0.25 },
        skew: [0, 1, 4, -5, 2] },
    ],
  },
  wyrm: {
    name: 'Wyrm', wide: true, colour: '#3f6f9c', accent: '#7fe6ff', anim: 'coil',
    body: { grid: WYRM_COIL, ox: 54, oy: 47 }, wear: 0.04,
    motion: { bob: 2, sway: 3, phase: 0.35, period: 1900, telegraph: 540 },
    stage: { scale: 1.5, sink: 4, bias: 0 },
    core: [62, 44],
    faults: [[50, 38, 12], [64, 52, 12]],
    parts: [
      // The coils run slow and a third of a turn apart, so the animal swims
      // along its own length instead of pulsing like a ring.
      { name: 'coilMid', grid: WYRM_COIL, ox: 45, oy: 33, behind: true,
        frames: [[0, 0], [1, 0], [-2, -1], [3, 1], [-3, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0 },
        skew: [0, 2, -3, 4, -2] },
      { name: 'coilTop', grid: WYRM_COIL, ox: 34, oy: 21, behind: true,
        frames: [[0, 0], [2, 0], [-3, -1], [5, 1], [-4, 1]],
        drift: { x: 2, y: 1, rate: 0.5, phase: 0.33 },
        skew: [0, 3, -4, 6, -3] },
      { name: 'neck', grid: WYRM_NECK, ox: 24, oy: 19,
        frames: [[0, 0], [1, 1], [-3, -2], [5, 2], [-4, 2]],
        drift: { x: 2, y: 2, rate: 0.75, phase: 0.5 },
        skew: [0, 2, -4, 6, -3] },
      { name: 'fin', grid: WYRM_FIN, ox: 40, oy: 17, behind: true,
        frames: [[0, 0], [1, 1], [-2, -2], [4, 2], [-3, 1]],
        drift: { x: 1, y: 1, rate: 1.25, phase: 0 } },
      { name: 'head', grid: WYRM_HEAD, ox: 4, oy: 13,
        frames: [[0, 0], [1, 1], [-4, -2], [6, 3], [-5, 3]],
        drift: { x: 2, y: 2, rate: 1, phase: 0.15 },
        skew: [0, 1, -3, 4, -2] },
      { name: 'jaw', grid: WYRM_JAW, ox: 4, oy: 25,
        frames: [[0, 0], [1, 1], [-4, -1], [6, 7], [-5, 4]],
        drift: { x: 1, y: 2, rate: 1.5, phase: 0.4 },
        alt: { 3: WYRM_JAW_OPEN } },
    ],
  },
};

/* ---------------- key resolution ----------------
 * world.py names a sprite per boss. Two notes on the mapping:
 *   - "interviewer" resolves to the knight. The final boss of a game about
 *     interviews is a faceless thing in mirror armour holding a rubric; making
 *     it the knight is the strongest read available and costs one line to undo.
 *   - two entries in world.BOSSES share the key "titan", and two identical
 *     silhouettes in one playthrough is a defect the player can see. BOSS_ART_FOR_ID
 *     sends the Rolling Titan to the colossus instead. Art-only override; nothing
 *     about the fight changes.
 */
export const BOSS_ARCHETYPES = Object.freeze(Object.keys(ART));

export const BOSS_SHAPE_FOR = Object.freeze({
  titan: 'titan', hydra: 'hydra', wraith: 'wraith', behemoth: 'behemoth',
  golem: 'golem', dragon: 'dragon', ent: 'ent', necromancer: 'necromancer',
  automaton: 'automaton', lich: 'lich', demon: 'demon', wyrm: 'wyrm',
  interviewer: 'knight', knight: 'knight', colossus: 'colossus',
});

export const BOSS_ART_FOR_ID = Object.freeze({
  rolling_titan: 'colossus',
});

export function resolveBoss(spriteKeyOrId) {
  const k = String(spriteKeyOrId || '');
  return BOSS_ART_FOR_ID[k] || BOSS_SHAPE_FOR[k] || (ART[k] ? k : 'titan');
}

/* Art for a world.BOSSES row: the id override wins, then the sprite key. */
export function bossArtKey(boss) {
  if (!boss) return 'titan';
  if (typeof boss === 'string') return resolveBoss(boss);
  return BOSS_ART_FOR_ID[boss.id] || resolveBoss(boss.sprite);
}

export function bossSize(key) {
  const art = ART[resolveBoss(key)];
  return { w: art.wide ? BOSS_WIDE_W : BOSS_W, h: BOSS_H };
}

/* ---------------- motion metadata ----------------
 * Everything the battle scene needs to drive the fight without reaching into
 * the art: how far it bobs, how long the telegraph runs, what to draw it at,
 * how wide its shadow is, and whether it touches the ground at all.
 */
export const BOSS_MOTION = Object.freeze(Object.fromEntries(
  BOSS_ARCHETYPES.map(k => {
    const art = ART[k];
    const floats = art.anim === 'float';
    return [k, Object.freeze({
      key: k,
      name: art.name,
      bob: art.motion.bob,
      sway: art.motion.sway,
      phase: art.motion.phase,
      period: art.motion.period,
      telegraph: art.motion.telegraph,
      anim: art.anim,
      wide: !!art.wide,
      floats,
      /* What the battle stage should draw it at, and how far its feet go under
       * the floor. A 64-box boss at 1.75 stands 112 tall against a 72-tall
       * hero and fills the stage from just under its ceiling down through the
       * ground line — which is the whole point, and is why `sink` exists: the
       * feet are meant to be under the floor, not standing on a shelf. */
      scale: (art.stage && art.stage.scale) || 1.5,
      sink: (art.stage && art.stage.sink) || 0,
      bias: (art.stage && art.stage.bias) || 0,
      parts: (art.parts || []).length,
      phases: BOSS_PHASE_COUNT,
      shadow: art.wide ? 44 : 30,
      colour: art.colour,
      accent: art.accent,
    })];
  }),
));

export function bossMotion(key) {
  return BOSS_MOTION[resolveBoss(key)] || BOSS_MOTION.titan;
}

/* The stage default, and the value fx.js passes. It is deliberately still 1.5:
 * a caller that asks for "the stage scale" gets a number that is safe for any
 * box, and drawBoss then refines it per archetype (BOSS_MOTION[key].scale) so
 * a 64-box creature is drawn at 1.75 and a 96-box one stays at 1.5. Passing a
 * scale that is NOT this constant means the caller has its own opinion — the
 * overworld draws bosses at 1 on a 16px tile map — and is honoured verbatim.
 *
 * Why 1.75 for the 64-box: 64 * 1.75 = 112, which against STAGE.enemyX = 136
 * on a 192-wide stage is exactly the width available, and against the hero's
 * 72 makes the boss half again as tall as the thing fighting it. Destination
 * coordinates must be rounded or the half-pixel lands between two source rows.
 */
export const BOSS_STAGE_SCALE = 1.5;

/* The scale a given archetype actually wants on the battle stage. */
export function bossStageScale(key) {
  return (BOSS_MOTION[resolveBoss(key)] || BOSS_MOTION.titan).scale;
}

/* Lighting for the scene, so the stage can be tinted to the creature standing
 * on it. Returned as plain hex strings; fx.js can drop them straight into a
 * gradient or a withAlpha(). */
export function bossLighting(key, colour) {
  const art = ART[resolveBoss(key)];
  const base = colour || art.colour;
  const r = ramp(base);
  const a = ramp(art.accent);
  return {
    key: resolveBoss(key),
    colour: base,
    accent: art.accent,
    rim: r.light1,
    glow: mix(r.light2, '#ffffff', 0.3),
    ember: a.light1,
    ambient: mix(r.shadow2, '#0a0910', 0.55),
    fog: mix(r.shadow1, '#0e0c16', 0.72),
    floor: mix(r.shadow2, '#141220', 0.6),
    tint: shade(base, -40),
  };
}

export const BOSS_PALETTES = Object.freeze(Object.fromEntries(
  BOSS_ARCHETYPES.map(k => [k, Object.freeze(bossLighting(k, ART[k].colour))]),
));

/* ================================================================
 * ASSEMBLY
 * ================================================================
 * Layers go down in one order and one order only: parts marked `behind`, the
 * posed body, then the parts in front. The whole stack is merged into a single
 * character grid BEFORE shading, which is the point — applyRim derives light
 * from the silhouette, and a wing shaded separately from the body it overlaps
 * would be lit as if the body were not there.
 */
function partGrid(part, frame, beat) {
  let g = (part.alt && part.alt[frame])
    || (part.altBeat && (beat & 1) ? part.altBeat : null)
    || part.grid;
  if (part.flip) g = flipX(g);
  if (part.skew && part.skew[frame]) {
    const [top, bottom] = filledBounds(g);
    g = skewRows(g, top, bottom, part.skew[frame]);
  }
  return g;
}

function partOffset(part, frame, beat) {
  const f = (part.frames && part.frames[frame]) || [0, 0];
  const [dx, dy] = driftAt(part.drift, beat);
  return [(part.ox | 0) + (f[0] | 0) + dx, (part.oy | 0) + (f[1] | 0) + dy];
}

function assemble(key, frame, beat) {
  const art = ART[key];
  const w = art.wide ? BOSS_WIDE_W : BOSS_W;
  const canvasGrid = blank(w, BOSS_H);

  let body = art.body.half
    ? mirror(halfRect(art.body.half, HALF), HALF)
    : rect(art.body.grid);
  body = (POSES[art.anim] || POSES.heavy)(body, frame);
  /* The body gets a beat too, one pixel of it, so the parts are not drifting
   * against something nailed down. It is the smallest amount of motion that
   * still reads, which is the point: the parts are the performance. */
  const bd = driftAt(art.body.drift, beat);

  const parts = art.parts || [];
  for (const p of parts) {
    if (!p.behind) continue;
    const [ox, oy] = partOffset(p, frame, beat);
    stamp(canvasGrid, partGrid(p, frame, beat), ox, oy);
  }
  stamp(canvasGrid, body, (art.body.ox | 0) + bd[0], (art.body.oy | 0) + bd[1]);
  for (const p of parts) {
    if (p.behind) continue;
    const [ox, oy] = partOffset(p, frame, beat);
    stamp(canvasGrid, partGrid(p, frame, beat), ox, oy);
  }
  return canvasGrid;
}

/* ---------------- rasterising ---------------- */
function offscreen(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

const spriteCache = new Map();
/* A fight's working set is ONE creature: two idle frames x six beats, plus the
 * three action frames, all of it x three phases = 45 canvases. The bound that
 * actually matters is the pathological one — a caller warming every archetype
 * at every phase, which is 14 x 3 x 15 = 630 — so the cap sits just above it
 * and nothing any caller can legitimately ask for ever thrashes. */
const CACHE_CAP = 640;

/* True LRU rather than insertion order. With three phases in play the oldest
 * INSERTED entry is frequently the current phase's idle frame, and evicting
 * that would regenerate a sprite every time the idle loop came round. */
function cacheGet(key) {
  const hit = spriteCache.get(key);
  if (hit === undefined) return undefined;
  spriteCache.delete(key);
  spriteCache.set(key, hit);
  return hit;
}

function cachePut(key, value) {
  if (spriteCache.size >= CACHE_CAP) {
    const coldest = spriteCache.keys().next().value;
    spriteCache.delete(coldest);
  }
  spriteCache.set(key, value);
  return value;
}

/* One boss, one frame, one colour. Deterministic and cached forever: the same
 * Hash Titan carries the same pitting in every session. */
export function bossSprite(spriteKey, colour, frame = 0, opts = {}) {
  const key = resolveBoss(spriteKey);
  const art = ART[key];
  const base = colour || art.colour;
  const f = frameIndex(frame);
  const ph = bossPhase(opts && opts.phase !== undefined ? opts.phase : 0);
  /* Beats only run on the two idle frames. The action frames already move
   * every part to an authored extreme, and giving them a sub-beat would
   * multiply the cache to hide a difference nobody can see in 240ms. */
  const beat = (f <= BOSS_FRAME.BREATHE && opts && opts.beat)
    ? (((opts.beat | 0) % BOSS_BEATS) + BOSS_BEATS) % BOSS_BEATS : 0;
  const cacheKey = `${key}|${base}|${f}|${ph}|${beat}`;
  const hit = cacheGet(cacheKey);
  if (hit) return hit;

  let grid = assemble(key, f, beat);
  if (art.wear) grid = patina(grid, `${key}:${base}:${f}`, art.wear + ph * 0.05, 'd');
  // Damage before shading: applyRim derives light from the silhouette, and a
  // fissure opened after the fact would be lit as if the plate were still shut.
  grid = fracture(grid, `${key}:${f}:${ph}`, ph, art.faults);
  grid = ember(grid, ph, art.core);
  grid = ignite(grid, ph, art.core);
  grid = rimPass(applyRim(grid));

  const w = art.wide ? BOSS_WIDE_W : BOSS_W;
  const { canvas, ctx } = offscreen(w, BOSS_H);
  drawGrid(ctx, grid, bossPalette(base, art.accent, ph));
  return cachePut(cacheKey, canvas);
}

/* All five frames of one boss, in table order. Call once at fight start and the
 * render loop never touches the generator again. */
export function bossFrames(spriteKey, colour, opts = {}) {
  return BOSS_FRAME_NAMES.map((_, i) => bossSprite(spriteKey, colour, i, opts));
}

/* Every canvas one phase of one fight can ask for, built in one go. A caller
 * that warms this at phase change never generates inside the render loop. */
export function warmBoss(spriteKey, colour, phase = 0) {
  let n = 0;
  for (let f = 0; f < BOSS_FRAME_COUNT; f++) {
    const beats = f <= BOSS_FRAME.BREATHE ? BOSS_BEATS : 1;
    for (let b = 0; b < beats; b++) { bossSprite(spriteKey, colour, f, { phase, beat: b }); n++; }
  }
  return n;
}

export function clearBossCache() { spriteCache.clear(); flashCache = new WeakMap(); }

/* Flat-colour silhouette for the hit flash, keyed on the source canvas in a
 * WeakMap so it dies with the sprite and a long session cannot accumulate one
 * flash canvas per frame drawn. */
let flashCache = new WeakMap();
function silhouette(img, colour) {
  let byColour = flashCache.get(img);
  if (!byColour) { byColour = new Map(); flashCache.set(img, byColour); }
  const hit = byColour.get(colour);
  if (hit) return hit;
  const { canvas, ctx } = offscreen(img.width, img.height);
  ctx.drawImage(img, 0, 0);
  ctx.globalCompositeOperation = 'source-atop';
  ctx.fillStyle = colour;
  ctx.fillRect(0, 0, img.width, img.height);
  byColour.set(colour, canvas);
  return canvas;
}

/* ---------------- ambient pose ----------------
 * Same contract as sprites.idlePose, so a caller that already drives mobs needs
 * no new vocabulary: dx/dy in sprite pixels, plus which idle frame to hold.
 */
export function bossPose(spriteKey, timeMs, seed = 0) {
  const m = bossMotion(spriteKey);
  const t = (timeMs / m.period) + m.phase + seed * 0.137;
  const cycle = t - Math.floor(t);
  const wave = Math.sin(cycle * Math.PI * 2);
  return {
    dx: Math.round(Math.cos(cycle * Math.PI * 2) * m.sway),
    dy: -Math.round(Math.abs(wave) * m.bob),
    frame: cycle < 0.5 ? BOSS_FRAME.IDLE : BOSS_FRAME.BREATHE,
    /* The sub-position inside the idle loop. The frame flips twice per period;
     * the beat advances BOSS_BEATS times, and each part reads it at its own
     * rate. This is the field that makes the parts stop marching in step. */
    beat: Math.floor(cycle * BOSS_BEATS) % BOSS_BEATS,
    cycle,
  };
}

/* Which frame a state machine should be showing, given when the state started.
 * Returns the frame index and whether the state has run out, so the caller can
 * advance without duplicating the table. */
export function bossFrameAt(spriteKey, state, elapsedMs) {
  const row = BOSS_FRAME_TABLE[String(state || 'idle').toLowerCase()];
  if (!row) return { index: 0, done: true, next: 'idle' };
  const hold = row.hold || bossMotion(spriteKey).telegraph;
  return { index: row.index, done: elapsedMs >= hold, next: row.next, hold };
}

/* ================================================================
 * DRAW
 * ================================================================
 * x is the horizontal centre, y is the ground line — feet, not sprite origin,
 * matching how fx.js places the hero. A floating boss is authored with its own
 * gap above the baseline, so the same call site works for both without a flag.
 */
/* The floor eats the last few rows. A boss is drawn with its feet BELOW the
 * ground line — see `sink` — and without this it reads as a sprite whose legs
 * were cut off rather than as a creature standing in front of, and partly
 * inside, the floor. Four hard bands, darkening downward, in the stage's own
 * near-black: the same trick as an aerial-perspective haze, run vertically. */
function floorVeil(ctx, left, right, groundY, depth, tone) {
  if (depth <= 0) return;
  const bands = 4;
  for (let i = 0; i < bands; i++) {
    const y0 = groundY + Math.round((depth * i) / bands);
    const y1 = groundY + Math.round((depth * (i + 1)) / bands);
    if (y1 <= y0) continue;
    ctx.globalAlpha = 0.3 + 0.7 * ((i + 1) / bands);
    ctx.fillStyle = tone;
    ctx.fillRect(left, y0, right - left, y1 - y0);
  }
  ctx.globalAlpha = 1;
}

export function drawBoss(ctx, key, x, y, opts = {}) {
  const artKey = resolveBoss(key);
  const m = BOSS_MOTION[artKey];
  const art = ART[artKey];
  const colour = opts.colour || art.colour;
  const reduced = !!opts.reducedMotion;
  const time = opts.time || 0;

  /* An entrance is a different animal: it owns the staging, the reveal and the
   * light. One number turns this call into that one. */
  if (opts.entrance !== undefined && opts.entrance !== null && opts.entrance < 1) {
    return drawBossEntrance(ctx, artKey, x, y, opts.entrance, opts);
  }

  const pose = reduced ? { dx: 0, dy: 0, frame: BOSS_FRAME.IDLE, beat: 0 }
    : bossPose(artKey, time, opts.seed || 0);

  let frame = opts.frame;
  if (frame === undefined || frame === null) frame = pose.frame;
  const phase = bossPhase(opts.phase);
  const beat = reduced ? 0 : (opts.beat === undefined ? pose.beat : opts.beat);
  const img = bossSprite(artKey, colour, frame, { phase, beat });
  if (!img) return null;

  /* Scale. A caller that passes nothing, or that passes the stage default,
   * is asking for "however big this creature should be on the battle stage"
   * and gets the per-archetype answer. A caller with its own number — the
   * overworld map, at 1 — is taken at its word and nothing is applied on top,
   * including the sink, which only means anything against a ground line. */
  const staged = opts.scale === undefined || opts.scale === BOSS_STAGE_SCALE;
  const scale = staged ? m.scale : opts.scale;
  const sink = staged ? (opts.sink === undefined ? m.sink : opts.sink) : 0;
  const bias = staged ? (opts.bias === undefined ? m.bias : opts.bias) : 0;

  const w = Math.round(img.width * scale);
  const h = Math.round(img.height * scale);

  // The ambient bob is applied here rather than baked into a frame: it is
  // continuous, the frames are not, and a boss that only moved on frame change
  // would step rather than drift. The horizontal half is capped: something
  // this heavy does not slide five pixels sideways, and the cap is also what
  // keeps a 112-wide creature inside a 192-wide stage at every phase of it.
  const dx = Math.max(-3, Math.min(3, Math.round(pose.dx * scale)));
  const dy = Math.round(pose.dy * scale);
  const foot = Math.round(y + sink * scale);
  const left = Math.round(x + bias - w / 2) + dx;
  const top = foot - h + dy;

  if (opts.shadow !== false) {
    const squeeze = m.floats ? 0.7 : 1;
    drawGroundShadow(ctx, Math.round(x + bias + dx * 0.4), Math.round(y + 1),
      Math.round(m.shadow * scale * 0.5 * squeeze),
      Math.round(m.shadow * scale * 0.17 * squeeze),
      m.floats ? 0.22 : 0.36);
  }

  const alpha = opts.alpha === undefined ? 1 : opts.alpha;
  if (alpha !== 1) { ctx.save(); ctx.globalAlpha = alpha; }
  ctx.drawImage(img, left, top, w, h);
  const flash = opts.flash || 0;
  if (flash > 0.01) {
    const sil = silhouette(img, opts.flashColour || '#ffffff');
    const prev = ctx.globalAlpha;
    ctx.globalAlpha = alpha * Math.min(1, flash);
    ctx.drawImage(sil, left, top, w, h);
    ctx.globalAlpha = prev;
  }
  if (alpha !== 1) ctx.restore();

  // Everything below the ground line goes into the floor.
  const below = top + h - Math.round(y);
  if (opts.occlude !== false && sink > 0 && below > 0) {
    const light = BOSS_PALETTES[artKey] || bossLighting(artKey, colour);
    floorVeil(ctx, left, left + w, Math.round(y), below,
      opts.floorTone || light.floor);
  }

  return { x: left, y: top, w, h, frame, phase, beat, key: artKey };
}

/* ================================================================
 * THE ENTRANCE
 * ================================================================
 * A boss that fades up at 40% opacity is a creature that was always there and
 * that the renderer got around to. This is four beats, and the creature is not
 * whole until the last one:
 *
 *   0.00-0.28  THE FLOOR ANSWERS. Nothing is visible but the ground giving
 *              way: a widening scar under the feet and dust thrown off it.
 *   0.22-0.62  THE RISE. The creature comes up through that scar, clipped at
 *              the ground line, so it is genuinely emerging rather than
 *              sliding in from off-frame. Its own rim light arrives first.
 *   0.55-0.80  THE CROWN LIGHTS. A flare in the creature's own colour washes
 *              the silhouette, brightest at the top — the contre-jour hitting
 *              the highest thing on the stage before anything else.
 *   0.75-1.00  THE SETTLE. It drops the last pixels onto the ground line, the
 *              shadow snaps in hard, and dust comes back off the impact.
 *
 * Deterministic in k: same progress, same frame, forever. Allocates nothing —
 * the only canvases are the cached sprite and its cached silhouette.
 */
export const BOSS_ENTRANCE_MS = 2200;

/* What the entrance wants from the caller at a given progress: how hard to
 * shake, how hard to flash the stage, and whether the impact has landed yet.
 * A caller drives its camera from this rather than guessing at the timing. */
export function bossEntrance(key, k = 0) {
  const t = Math.max(0, Math.min(1, k));
  const impact = 0.78;
  const hit = t >= impact && t < impact + 0.08;
  return {
    key: resolveBoss(key),
    duration: BOSS_ENTRANCE_MS,
    t,
    beat: t < 0.28 ? 'floor' : t < 0.62 ? 'rise' : t < 0.8 ? 'crown' : 'settle',
    impactAt: impact,
    landed: t >= impact,
    shake: hit ? 9 : t < 0.28 ? 2 + t * 6 : t < 0.62 ? 3 : 1,
    flash: hit ? 0.85 : t > 0.55 && t < impact ? (t - 0.55) * 1.2 : 0,
  };
}

function dustRing(ctx, cx, groundY, spread, rise, a, colour) {
  // Twelve hard chips on a fixed lattice. No rng in a draw path, ever.
  for (let i = 0; i < 12; i++) {
    const s = (i % 2 ? 1 : -1) * (0.25 + (i % 6) * 0.15);
    const px = Math.round(cx + s * spread);
    const py = Math.round(groundY - rise * (0.3 + ((i * 7) % 10) * 0.07));
    const size = i % 3 === 0 ? 2 : 1;
    ctx.globalAlpha = a * (i % 3 === 0 ? 0.9 : 0.55);
    ctx.fillStyle = colour;
    ctx.fillRect(px, py, size, size);
  }
  ctx.globalAlpha = 1;
}

export function drawBossEntrance(ctx, key, x, y, k, opts = {}) {
  const artKey = resolveBoss(key);
  const m = BOSS_MOTION[artKey];
  const colour = opts.colour || ART[artKey].colour;
  const light = bossLighting(artKey, colour);
  const beat = bossEntrance(artKey, k);
  const t = beat.t;
  const reduced = !!opts.reducedMotion;

  const staged = opts.scale === undefined || opts.scale === BOSS_STAGE_SCALE;
  const scale = staged ? m.scale : opts.scale;
  const sink = staged ? m.sink : 0;
  const bias = staged ? m.bias : 0;

  /* Phase during an entrance is always whole: the thing has not been hit yet,
   * and a boss that arrives already cracked has thrown away the one moment
   * where cracking it means anything. */
  const img = bossSprite(artKey, colour, t < beat.impactAt ? BOSS_FRAME.WINDUP : BOSS_FRAME.IDLE, { phase: 0, beat: 0 });
  if (!img) return null;
  const w = Math.round(img.width * scale);
  const h = Math.round(img.height * scale);
  const groundY = Math.round(y);
  const foot = Math.round(y + sink * scale);
  const left = Math.round(x + bias - w / 2);

  // 1. the floor answers — a scar opening under the feet
  const scar = Math.min(1, t / 0.28);
  if (scar > 0) {
    const half = Math.round(m.shadow * scale * 0.5 * scar);
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = light.ambient;
    ctx.fillRect(x + bias - half, groundY - 1, half * 2, 3);
    ctx.globalAlpha = 0.5 + 0.4 * scar;
    ctx.fillStyle = light.glow;
    ctx.fillRect(x + bias - Math.round(half * 0.7), groundY, Math.round(half * 1.4), 1);
    ctx.globalAlpha = 1;
    if (!reduced) dustRing(ctx, x + bias, groundY, half * 1.4, 10 * scar, 0.5 * scar, light.ember);
  }

  // 2. the rise — clipped at the ground line so it comes UP through the floor
  const rise = Math.max(0, Math.min(1, (t - 0.22) / 0.4));
  if (rise > 0) {
    const lift = Math.round((1 - (rise * rise * (3 - 2 * rise))) * h);   // smoothstep
    const top = foot - h + lift;
    ctx.save();
    ctx.beginPath();
    ctx.rect(left - 8, top, w + 16, Math.max(0, (foot - top) - (t < beat.impactAt ? 0 : 0)));
    ctx.clip();
    ctx.globalAlpha = Math.min(1, 0.35 + rise * 0.75);
    ctx.drawImage(img, left, top, w, h);
    // Its own rim arrives before the body does: a hot silhouette under a dim one.
    if (rise < 1) {
      const sil = silhouette(img, light.rim);
      ctx.globalAlpha = (1 - rise) * 0.8;
      ctx.drawImage(sil, left, top, w, h);
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  // 3. the crown lights — a wash in the creature's own colour, hottest at the top
  const crown = Math.max(0, Math.min(1, (t - 0.55) / 0.25));
  if (crown > 0 && crown < 1 && !reduced) {
    const sil = silhouette(img, light.glow);
    const top = foot - h;
    ctx.globalAlpha = Math.sin(crown * Math.PI) * 0.7;
    ctx.drawImage(sil, left, top, w, h);
    ctx.globalAlpha = 1;
  }

  // 4. the settle — shadow snaps in, dust comes back off the impact
  if (t >= beat.impactAt) {
    const s = Math.min(1, (t - beat.impactAt) / (1 - beat.impactAt));
    const squeeze = m.floats ? 0.7 : 1;
    drawGroundShadow(ctx, Math.round(x + bias), groundY + 1,
      Math.round(m.shadow * scale * 0.5 * squeeze),
      Math.round(m.shadow * scale * 0.17 * squeeze),
      (m.floats ? 0.22 : 0.36) * s);
    if (!reduced) {
      dustRing(ctx, x + bias, groundY, m.shadow * scale * (0.5 + s * 0.9),
        18 * (1 - s), (1 - s) * 0.8, light.ember);
    }
    const below = foot - groundY;
    if (sink > 0 && below > 0) floorVeil(ctx, left, left + w, groundY, below, light.floor);
  }

  return { x: left, y: foot - h, w, h, frame: BOSS_FRAME.IDLE, phase: 0, beat: 0,
           key: artKey, entrance: beat };
}

/* Everything a caller needs about one archetype in a single object, for a
 * bestiary screen or a debug overlay. */
export function bossInfo(key) {
  const artKey = resolveBoss(key);
  const art = ART[artKey];
  return {
    key: artKey,
    name: art.name,
    size: bossSize(artKey),
    motion: BOSS_MOTION[artKey],
    lighting: BOSS_PALETTES[artKey],
    parts: (art.parts || []).map(p => p.name),
    frames: BOSS_FRAME_NAMES.slice(),
    phases: BOSS_PHASE_NAMES.slice(),
    beats: BOSS_BEATS,
    core: art.core ? art.core.slice() : null,
    faults: (art.faults || []).length,
    entrance: BOSS_ENTRANCE_MS,
  };
}
