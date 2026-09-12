/* The forge, measured in pixels.
 *
 * gauntlet/forge.py ships fifty-four objects and an art brief that states the
 * problem in numbers rather than as an aspiration: across the six hero rungs
 * the old weapon ladder produced six distinct frames and ZERO changes to the
 * alpha mask — the outline with colour thrown away. "A rung-nine weapon that
 * is a rung-one weapon in a different grey is the single biggest gap between
 * this feature and the word the player used, which was epic."
 *
 * So nothing in here counts draw calls. Every check is a claim about pixels:
 *
 *   0. VOCABULARY. The art side's lists and forge.py's are the same lists.
 *      forgeart.json is generated from that module and checked in beside
 *      vocab.json, exactly like the rest of the harnesses here.
 *   1. SILHOUETTE. Every blade, every adjacent pair of its nine rungs, driven
 *      by the REAL art dict, as pixels of binary mask that differ. A zero is a
 *      build failure. Also measured on the 6x12 art the hero holds, reported
 *      separately because seventy-two pixels is a smaller budget than a
 *      thousand and averaging the two would hide it.
 *   2. BUDGET. Fifteen colours plus transparent, counted off the RASTER and
 *      not off the palette dict.
 *   3. MATERIAL. A rung forged of one metal must not be the same pixels as the
 *      same rung forged of another, and the six lines must not be four grids.
 *   4. MOTION. Rungs 1-4 still, 5-9 moving, frame 0 the quiet one, `frames: 1`
 *      and the `stillness` aura both able to pin it, reduced motion honoured.
 *   5. DETERMINISM. Byte-identical cold and warm, in any build order.
 *   6. FALLBACK. Nothing forge.py can send may throw.
 *   7. STEADY STATE. A forged weapon on screen allocates no canvases.
 */
import fs from 'fs';
import { installRaster, RASTER, pixelDiff, silhouetteDiff, colourCount, frameHash } from './raster.mjs';
installRaster();

const F = JSON.parse(fs.readFileSync(new URL('./forgeart.json', import.meta.url), 'utf8'));
const L = await import('../../web/js/lootart.js');

const fail = [];
const note = (m) => fail.push(m);
const ctx = (() => { const c = document.createElement('canvas'); c.width = 128; c.height = 128; return c.getContext('2d'); })();
const V = L.forgeVocabulary();
const TIERS = []; for (let t = F.min_tier; t <= F.max_tier; t++) TIERS.push(t);

function shot(spec, frame = 0) {
  const c = document.createElement('canvas');
  c.width = L.FORGE_SIZE; c.height = L.FORGE_SIZE;
  c.getContext('2d').drawImage(L.forgeSprite(spec, frame), 0, 0);
  return c;
}
/* The spec a caller builds from forge.art_at() plus the blade id. */
const look = (b, t) => ({ blade: b.id, tier: t, ...b.art[t - 1] });

/* ---------------- 0. vocabulary ---------------- */
console.log('=== 0. VOCABULARY: the art side and gauntlet/forge.py name the same things ===');
const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
if (V.tiers !== F.max_tier) note(`VOCAB lootart has ${V.tiers} rungs, forge.py has ${F.max_tier}`);
if (!same([...V.motifs].sort(), F.motifs)) note('VOCAB motif tables differ');
if (!same([...V.auras].sort(), F.auras)) note('VOCAB aura tables differ');
for (const m of F.materials) if (!V.materials.includes(m)) note(`VOCAB no ramp for material "${m}"`);
for (const m of F.metals) {
  const mine = V.metals.find(x => x.key === m.id);
  if (!mine) { note(`VOCAB metal "${m.id}" is missing`); continue; }
  if (mine.rung !== m.rung) note(`VOCAB metal ${m.id} rung ${mine.rung} vs ${m.rung}`);
  if (mine.colour !== m.colour) note(`VOCAB metal ${m.id} colour ${mine.colour} vs ${m.colour}`);
  if (F.region_metal[mine.region] !== m.id) note(`VOCAB metal ${m.id} claims region ${mine.region}`);
}
for (const b of F.blades) if (!V.blades.find(x => x.id === b.id)) note(`VOCAB blade "${b.id}" is missing`);
console.log('  rungs', V.tiers, '| blades', V.blades.length, '| metals', V.metals.length,
  '| motifs', V.motifs.length, '| auras', V.auras.length, '| generic families', V.weapons.length);
const fams = V.blades.map(b => b.family);
console.log('  the six lines map to:', fams.join(' '));
if (new Set(fams).size !== fams.length) note(`SHAPE the six lines share grids: ${fams.join(',')}`);
console.log('  distinct silhouettes for six lines:', new Set(fams).size + '/6',
  '(forge.py ships them as ' + new Set(F.blades.map(b => b.shape)).size + ' shapes)');

/* ---------------- 1. silhouette ---------------- */
console.log('');
console.log('=== 1. SILHOUETTE: pixels of outline that change per rung, colour discarded ===');
console.log('    driven by forge.art_at() — real motif, aura, material, accent, silhouette hint');
console.log('');
console.log('blade                 1>2 2>3 3>4 4>5 5>6 6>7 7>8 8>9   min   1>9  ink@1 ink@9  px1>9');
let worstStep = Infinity, worstWho = '';
for (const b of F.blades) {
  const masks = TIERS.map(t => shot(look(b, t)));
  const ink = (cv) => { let n = 0; for (let i = 3; i < cv.data.length; i += 4) if (cv.data[i]) n++; return n; };
  const steps = [];
  for (let i = 0; i + 1 < masks.length; i++) steps.push(silhouetteDiff(masks[i], masks[i + 1]));
  const total = silhouetteDiff(masks[0], masks[masks.length - 1]);
  const px = pixelDiff(masks[0], masks[masks.length - 1]);
  const min = Math.min(...steps);
  if (min < worstStep) { worstStep = min; worstWho = b.id; }
  if (min === 0) note(`SILHOUETTE ${b.id}: a rung does not change the outline — ${steps.join(',')}`);
  console.log(b.id.padEnd(21), steps.map(n => String(n).padStart(3)).join(' '),
    String(min).padStart(5), String(total).padStart(5),
    String(ink(masks[0])).padStart(5), String(ink(masks[8])).padStart(5), String(px).padStart(6));
}
console.log('');
console.log('  weakest single rung on a real blade:', worstStep, 'px of outline  (' + worstWho + ')');

console.log('');
console.log('=== 1b. every generic family, so a shape the backend adds later is covered ===');
console.log('family    1>2 2>3 3>4 4>5 5>6 6>7 7>8 8>9   min   1>9');
let gWorst = Infinity;
for (const w of V.weapons.map(x => x.key)) {
  const s = L.forgeSpread(w);
  if (s.min === 0) note(`SILHOUETTE ${w}: a rung does not change the outline — ${s.steps.join(',')}`);
  if (s.min < gWorst) gWorst = s.min;
  console.log(w.padEnd(9), s.steps.map(n => String(n).padStart(3)).join(' '),
    String(s.min).padStart(5), String(s.total).padStart(5));
}
console.log('  weakest anywhere:', gWorst, 'px');

console.log('');
console.log('=== 1c. the 6x12 art the hero holds — 72 pixels total, reported separately ===');
console.log('family    1>2 2>3 3>4 4>5 5>6 6>7 7>8 8>9   min   1>9');
for (const w of V.weapons.map(x => x.key)) {
  const s = L.forgeHandSpread(w);
  if (s.min === 0) note(`HAND ${w}: a rung does not change the held outline — ${s.steps.join(',')}`);
  console.log(w.padEnd(9), s.steps.map(n => String(n).padStart(3)).join(' '),
    String(s.min).padStart(5), String(s.total).padStart(5));
}

/* ---------------- 2. colour budget ---------------- */
console.log('');
console.log('=== 2. BUDGET: distinct opaque colours painted, counted off the raster ===');
let worst = 0, worstKey = '', sweep = 0;
for (const b of F.blades) {
  for (const t of TIERS) {
    const spec = look(b, t);
    for (let f = 0; f < L.forgeFrameCount(t, spec); f++) {
      const n = colourCount(shot(spec, f));
      sweep++;
      if (n > worst) { worst = n; worstKey = `${b.id}/r${t}/f${f}`; }
      if (n > 15) note(`BUDGET ${b.id} r${t} f${f} painted ${n} colours (max 15)`);
    }
  }
}
console.log('  the fifty-four real rungs, every frame:', sweep, 'sprites, worst', worst, 'colours at', worstKey);
let gw = 0, gk = '';
for (const w of V.weapons.map(x => x.key)) {
  for (const m of V.metals.map(x => x.key)) {
    for (const t of TIERS) {
      const n = colourCount(shot({ weapon: w, tier: t, metal: m }, 0));
      if (n > gw) { gw = n; gk = `${w}/${m}/r${t}`; }
      if (n > 15) note(`BUDGET ${w}/${m}/r${t} painted ${n} colours`);
    }
  }
}
console.log('  every family in every metal:', gw, 'colours at', gk);
let mw = 0, mk = '';
for (const mo of V.motifs) for (const au of V.auras) {
  const n = colourCount(shot({ weapon: 'sword', tier: 9, metal: 'nullsteel', motif: mo, aura: au }, 3));
  if (n > mw) { mw = n; mk = `${mo}/${au}`; }
  if (n > 15) note(`BUDGET motif ${mo} + aura ${au} painted ${n} colours`);
}
console.log('  all', V.motifs.length * V.auras.length, 'motif x aura pairs:', mw, 'colours at', mk);
let hw = 0, hk = '';
for (const b of F.blades) for (const t of TIERS) {
  const n = colourCount(L.forgeWeaponOverlay(look(b, t), { facing: 'down' }).canvas);
  if (n > hw) { hw = n; hk = `${b.id}/r${t}`; }
  if (n > 15) note(`BUDGET hand ${b.id} r${t} painted ${n} colours`);
}
console.log('  held art:', hw, 'colours at', hk);

/* ---------------- 3. material ---------------- */
console.log('');
console.log('=== 3. MATERIAL: a metal that only changes a caption is a metal that does not exist ===');
const base = shot({ weapon: 'sword', tier: 7, metal: V.metals[0].key });
let minD = Infinity, near = '';
for (const m of V.metals.slice(1)) {
  const d = pixelDiff(base, shot({ weapon: 'sword', tier: 7, metal: m.key }));
  if (d < minD) { minD = d; near = m.key; }
  if (d === 0) note(`MATERIAL ${m.key} renders identically to ${V.metals[0].key}`);
}
console.log('  sword r7 across eleven metals: closest pair differs by', minD, 'px (' + near + ')');
const ramps = new Set(V.metals.map(m => m.ramp));
console.log('  palette.js ramps the metals are made of:', [...ramps].join(' '));
/* Two rungs of one blade differ in accent alone at least once; prove that shows. */
let accentMin = Infinity;
for (const b of F.blades) {
  for (let t = 1; t < F.max_tier; t++) {
    const a = b.art[t - 1], c = b.art[t];
    if (a.material !== c.material || a.motif !== c.motif) continue;
    const d = pixelDiff(shot(look(b, t)), shot(look(b, t + 1)));
    if (d < accentMin) accentMin = d;
  }
}
console.log('  smallest change between two rungs sharing a material and a motif:', accentMin, 'px');

/* ---------------- 4. motion ---------------- */
console.log('');
console.log('=== 4. MOTION ===');
for (const t of TIERS) {
  const spec = look(F.blades[0], t);
  const n = L.forgeFrameCount(t, spec);
  const seen = new Set();
  for (let f = 0; f < n; f++) seen.add(frameHash(shot(spec, f)));
  const still = t < V.firstAnimated;
  if (still && n !== 1) note(`MOTION rung ${t} should be still, has ${n} frames`);
  if (!still && seen.size < 4) note(`MOTION rung ${t} has ${n} frames but only ${seen.size} distinct`);
  console.log(`  rung ${t} ${L.forgeTierName(t).padEnd(12)} frames ${String(n).padStart(2)}  distinct ${seen.size}   ${F.blades[0].names[t - 1]}`);
}
const pinned = L.forgeFrameCount(9, { frames: 1 });
const stilled = L.forgeFrameCount(9, { aura: 'stillness' });
console.log('  `frames: 1` pins an animated rung:', pinned === 1, ' the `stillness` aura pins it:', stilled === 1);
if (pinned !== 1) note('MOTION frames:1 did not pin the rung');
if (stilled !== 1) note('MOTION the stillness aura did not pin the rung');
const quiet = L.forgeGrid({ weapon: 'sword', tier: 9 }, 0).join('').split('W').length - 1;
let loud = 0;
for (let f = 1; f < L.FORGE_FRAMES; f++) loud = Math.max(loud, L.forgeGrid({ weapon: 'sword', tier: 9 }, f).join('').split('W').length - 1);
console.log('  specular pixels on frame 0:', quiet, ' busiest frame:', loud);
if (quiet >= loud) note('MOTION frame 0 is not the quiet frame');
const r1 = L.forgeWeaponOverlay(look(F.blades[0], 9), { facing: 'down', time: 0, reducedMotion: true });
const r2 = L.forgeWeaponOverlay(look(F.blades[0], 9), { facing: 'down', time: 900, reducedMotion: true });
console.log('  reducedMotion pins the held frame:', frameHash(r1.canvas) === frameHash(r2.canvas));
if (frameHash(r1.canvas) !== frameHash(r2.canvas)) note('MOTION reducedMotion does not pin the held frame');

/* ---------------- 5. determinism ---------------- */
console.log('');
console.log('=== 5. DETERMINISM ===');
const before = [];
for (const b of F.blades) for (const t of TIERS) before.push(frameHash(shot(look(b, t), 2)));
L.clearLootArtCache();
const after = [];
for (const b of [...F.blades].reverse()) for (const t of [...TIERS].reverse()) after.push(frameHash(shot(look(b, t), 2)));
after.reverse();
let drift = 0;
for (let i = 0; i < before.length; i++) if (before[i] !== after[i]) drift++;
console.log(' ', before.length, 'sprites, cold cache vs warm cache in reverse build order:', drift, 'differ');
if (drift) note(`DETERMINISM ${drift} sprites changed with build order`);

/* ---------------- 6. fallback ---------------- */
console.log('');
console.log('=== 6. FALLBACK: nothing gauntlet/forge.py can send may throw ===');
const junk = [
  undefined, null, '', 0, -1, 99, NaN, {}, [], 'nonsense_weapon',
  { weapon: 'trebuchet', tier: 0, metal: 'cheese' },
  { blade: 'analysts_calipers', tier: 99, metal: 'iron' },
  { blade: 'recall_chain', tier: 4.7, metal: 'NULL-STEEL' },
  { shape: 'relic', tier: 5, material: 'tungsten', accent: 'not-a-colour' },
  { blade: 'draft_axe', tier: 6, motif: '__no_such_motif__', aura: '__no_such_aura__' },
  { id: 'toolwrights_spanner', forge_tier: 6 },
  { icon: 'sabers', rung: 3, material: 'steel', silhouette: 'enormous' },
  { weapon: { nested: true }, tier: [], frames: 'yes' },
];
let ok = 0;
for (const j of junk) {
  try {
    const spec = L.forgeSpec(j);
    L.forgeInfo(j);
    const img = L.forgeSprite(j, 5);
    L.drawForgeWeapon(ctx, j, 4, 4, { scale: 2, time: 500 });
    L.forgeWeaponOverlay(j, { facing: 'left', pose: 'idle' });
    if (!img || img.width !== L.FORGE_SIZE) note(`FALLBACK ${JSON.stringify(j)} produced no sprite`);
    if (!V.weapons.find(w => w.key === spec.weapon)) note(`FALLBACK ${JSON.stringify(j)} -> unknown family`);
    if (spec.tier < 1 || spec.tier > F.max_tier) note(`FALLBACK ${JSON.stringify(j)} -> tier ${spec.tier}`);
    ok++;
  } catch (e) {
    note(`FALLBACK THREW on ${JSON.stringify(j)}: ${e.constructor.name}: ${e.message}`);
  }
}
console.log(' ', ok + '/' + junk.length, 'junk inputs resolved to a real blade without throwing');
for (const b of F.blades) {
  const got = L.forgeWeaponKey(b.id);
  if (!V.weapons.find(w => w.key === got)) note(`RESOLVE ${b.id} -> ${got}`);
}
const CLASSY = { archivist: 'chain', berserker: 'axe', seer: 'dagger', analyst: 'calipers', warden: 'hammer', artificer: 'spanner' };
let mapped = 0;
for (const [k, want] of Object.entries(CLASSY)) {
  if (L.forgeWeaponKey(k) === want) mapped++;
  else note(`RESOLVE class ${k} -> ${L.forgeWeaponKey(k)}, expected ${want}`);
}
console.log(' ', mapped + '/6 class ids reach their own line;',
  F.blades.length + '/' + F.blades.length, 'blade ids resolve');
console.log('  metal ladder:', V.metals.map(m => `${m.rung}:${m.key}`).join(' '));

/* ---------------- 6b. through the item dict ---------------- */
console.log('');
console.log('=== 6b. IN THE HAND: the dict the backend sends, through the existing gear path ===');
const mkItem = (b, t) => ({ id: b.id, name: b.names[t - 1], slot: 'weapon', rarity: 'LEGENDARY', icon: b.shape, forge: { tier: t, ...b.art[t - 1] } });
/* The number gauntlet/forge.py's art brief reports as zero. It measures the
 * OTHER hero path — sprites.heroFrame()'s own weapon grid, which this module
 * does not own and must not touch — and finds six distinct frames and no
 * change to the alpha mask at any rung. This is the same measurement on the
 * path lootart owns and INTEGRATION tells the game to use: heroGearLayers()
 * composited onto the hero. Both numbers are printed because they are both
 * true and they are about different code. */
const FACINGS = ['down', 'up', 'left', 'right'];
for (const b of F.blades) {
  const per = {};
  for (const f of FACINGS) per[f] = TIERS.map(t => L.equippedHeroFrame(f, 1, { weapon: mkItem(b, t) }, null, 'idle'));
  const u = new Set(per.down.map(frameHash)).size;
  /* A rung counts as visible if it moves the hero's outline at ANY facing.
   * Requiring it at every facing would be asking the weapon to escalate on the
   * side the body is standing in front of, which no amount of authoring can
   * deliver — half of the box is behind the hero and that is what holding a
   * weapon looks like. */
  let anywhere = 0, everyFacingBest = 0;
  const rows = [];
  for (let i = 0; i + 1 < TIERS.length; i++) {
    const d = {}; let any = 0;
    for (const f of FACINGS) { d[f] = silhouetteDiff(per[f][i], per[f][i + 1]); if (d[f] > 0) any++; }
    if (any > 0) anywhere++;
    everyFacingBest = Math.max(everyFacingBest, any);
    rows.push(Math.max(...FACINGS.map(f => d[f])));
  }
  if (u !== F.max_tier) note(`HAND ${b.id}: only ${u}/${F.max_tier} rungs produce a distinct hero frame`);
  if (anywhere !== F.max_tier - 1) note(`HAND ${b.id}: only ${anywhere}/${F.max_tier - 1} rungs change the hero's OUTLINE at any facing — a recolour is not an upgrade`);
  console.log(' ', b.id.padEnd(21), 'distinct frames', u + '/' + F.max_tier,
    ' rungs that move the hero outline', anywhere + '/' + (F.max_tier - 1),
    ' best px per step', rows.join(','));
}
const routed = L.drawItem(ctx, mkItem(F.blades[0], 7), 0, 0, { scale: 2, time: 440 });
const plain = L.drawItem(ctx, { id: 'iron_circlet', slot: 'head', rarity: 'RARE', icon: 'crown' }, 0, 0, { scale: 2 });
console.log('  drawItem routes a forged item to the forge pipeline:', routed.width + 'x' + routed.height,
  '| an ordinary item is untouched:', plain.width + 'x' + plain.height);
if (routed.width !== L.FORGE_SIZE) note('drawItem did not route a forged item');
if (plain.width !== L.ITEM_SIZE) note('drawItem mis-routed an ordinary item into the forge');
const bare = colourCount(L.equippedHeroFrame('down', 1, null, null, 'idle'));
const ladder = colourCount(L.equippedHeroFrame('down', 1, { weapon: { id: 'x', slot: 'weapon', rarity: 'LEGENDARY', icon: 'sword' } }, null, 'idle'));
let forged = 0;
for (const b of F.blades) for (const t of TIERS) forged = Math.max(forged, colourCount(L.equippedHeroFrame('down', 1, { weapon: mkItem(b, t) }, null, 'idle')));
console.log('  composited hero colours — bare', bare + ', rarity-ladder weapon', ladder + ', forged (worst rung)', forged);
if (forged > ladder) note(`HAND a forged weapon composites to ${forged} colours, worse than the ${ladder} the rarity ladder already costs`);

/* ---------------- 7. steady state ---------------- */
console.log('');
console.log('=== 7. STEADY STATE: a forged weapon on screen must not allocate ===');
L.clearLootArtCache();
const loadout = look(F.blades[0], 9);
RASTER.counting = true;
let a = RASTER.canvases;
for (let i = 0; i < 300; i++) { L.drawForgeWeapon(ctx, loadout, 8, 8, { scale: 3, time: i * 16 }); L.forgeWeaponOverlay(loadout, { facing: 'down', frameIndex: i % 4, time: i * 16 }); }
const cold = RASTER.canvases - a;
a = RASTER.canvases;
for (let i = 0; i < 900; i++) { L.drawForgeWeapon(ctx, loadout, 8, 8, { scale: 3, time: i * 16 }); L.forgeWeaponOverlay(loadout, { facing: 'down', frameIndex: i % 4, time: i * 16 }); }
const warm = RASTER.canvases - a;
RASTER.counting = false;
console.log('  frames 1-300 canvases:', cold, '  frames 301-1200 canvases:', warm);
if (warm !== 0) note(`STEADY ${warm} canvases allocated in the warm draw loop`);

console.log('');
if (fail.length) { console.log('FAIL (' + fail.length + ')'); for (const f of fail) console.log('  - ' + f); process.exitCode = 1; }
else console.log('PASS — every rung of every blade moves the outline, every sprite is inside the colour budget, nothing throws.');
