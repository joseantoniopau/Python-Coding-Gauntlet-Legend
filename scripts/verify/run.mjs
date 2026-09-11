import { installStub, REC, newCtx, newCanvas, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();
import fs from 'fs';
const V = JSON.parse(fs.readFileSync(new URL('./vocab.json', import.meta.url), 'utf8'));

const B  = await import('../../web/js/bosses.js');
const L  = await import('../../web/js/lootart.js');
const S  = await import('../../web/js/spellfx.js');
const SC = await import('../../web/js/battlescene.js');
const FX = await import('../../web/js/fx.js');

const ctx = newCtx(640, 360);
const fail = [];
const note = (m) => fail.push(m);
function run(label, fn) {
  setWhere(label);
  try { return fn(); }
  catch (e) { note(`THROW ${label}: ${e.constructor.name}: ${e.message}`); return undefined; }
}

/* ---------------- 1. bosses: every archetype, every frame ---------------- */
let bossDrawn = 0;
for (const key of B.BOSS_ARCHETYPES) {
  for (let f = 0; f < B.BOSS_FRAME_COUNT; f++) {
    const img = run(`bossSprite(${key},${f})`, () => B.bossSprite(key, '#c43f4f', f));
    if (!img || !img.width || !img.height) note(`bossSprite(${key},${f}) -> bad image ${img && img.width}x${img && img.height}`);
  }
  run(`bossFrames(${key})`, () => B.bossFrames(key, '#c43f4f'));
  run(`bossInfo(${key})`,   () => B.bossInfo(key));
  run(`bossSize(${key})`,   () => B.bossSize(key));
  run(`bossMotion(${key})`, () => B.bossMotion(key));
  run(`bossLighting(${key})`, () => B.bossLighting(key, '#c43f4f'));
  run(`bossPalette(${key})`, () => B.bossPalette(key, '#c43f4f'));
  for (const st of ['idle','breathe','windup','attack','hurt','walk','cast','die','__nonsense__']) {
    run(`bossFrameAt(${key},${st})`, () => B.bossFrameAt(key, st, 500));
  }
  for (let t = 0; t < 2000; t += 250) {
    run(`bossPose(${key},${t})`, () => B.bossPose(key, t, 7));
    const r = run(`drawBoss(${key},${t})`, () => B.drawBoss(ctx, key, 320, 300, { time: t, flash: t % 500 ? 0 : 0.8, alpha: 0.9, seed: 3 }));
    if (r) bossDrawn++;
  }
}
// reduced motion + defaults + garbage
run('drawBoss reduced', () => B.drawBoss(ctx, 'lich', 100, 200, { reducedMotion: true }));
run('drawBoss noopts',  () => B.drawBoss(ctx, 'dragon', 100, 200));
run('drawBoss garbage', () => B.drawBoss(ctx, '__no_such_boss__', 100, 200, {}));
run('frameIndex junk',  () => B.frameIndex('nonsense'));

/* every world.py boss row must resolve to real art */
const bossUnresolved = [];
for (const b of V.bosses) {
  const k = run(`bossArtKey(${b.id})`, () => B.bossArtKey(b));
  if (!k || !B.BOSS_ARCHETYPES.includes(k)) bossUnresolved.push(`${b.id}/${b.sprite} -> ${k}`);
  const img = run(`bossSprite for ${b.id}`, () => B.bossSprite(k, b.colour, 0));
  if (!img || !img.width) bossUnresolved.push(`${b.id} produced no image`);
}

/* ---------------- 2. lootart: every real item ---------------- */
const itemUnresolved = [], iconMiss = [], slotMiss = [];
for (const it of V.items) {
  const shape = run(`resolveShape(${it.id})`, () => L.resolveShape(it));
  if (!shape || !L.SHAPE_KEYS.includes(shape)) itemUnresolved.push(`${it.id} icon=${it.icon} slot=${it.slot} -> ${shape}`);
  const n = run(`itemFrameCount(${it.id})`, () => L.itemFrameCount(it)) || 1;
  for (let f = 0; f < n; f++) {
    const img = run(`itemSprite(${it.id},${f})`, () => L.itemSprite(it, f));
    if (!img || !img.width || !img.height) itemUnresolved.push(`${it.id} frame ${f} bad image`);
  }
  run(`itemFrames(${it.id})`, () => L.itemFrames(it));
  run(`drawItem(${it.id})`, () => L.drawItem(ctx, it, 40, 40, { scale: 2, time: 900 }));
  run(`lootCard(${it.id})`, () => L.lootCard(it));
  run(`drawLootCard(${it.id})`, () => L.drawLootCard(ctx, it, 10, 10, { time: 400 }));
  run(`drawLootDrop(${it.id})`, () => L.drawLootDrop(ctx, it, 200, 300, { time: 400 }));
  run(`frameFor(${it.id})`, () => L.frameFor(it, { time: 700 }));
}
// icon-only and slot-only resolution (a bare icon string, a bare slot)
for (const icon of [...new Set(V.items.map(i => i.icon))]) {
  const s = run(`resolveShape icon:${icon}`, () => L.resolveShape({ icon }));
  if (!s || !L.SHAPE_KEYS.includes(s)) iconMiss.push(`${icon} -> ${s}`);
}
for (const slot of [...new Set(V.items.map(i => i.slot))]) {
  const s = run(`resolveShape slot:${slot}`, () => L.resolveShape({ slot }));
  if (!s || !L.SHAPE_KEYS.includes(s)) slotMiss.push(`${slot} -> ${s}`);
}
// every rarity through every treatment
const rarityMiss = [];
for (const r of Object.keys(V.rarities)) {
  const st = run(`rarityStyle(${r})`, () => L.rarityStyle(r));
  if (!st || !st.colour) rarityMiss.push(`rarityStyle(${r})`);
  if (L.RARITY_COLOUR[r] === undefined) rarityMiss.push(`RARITY_COLOUR missing ${r}`);
  run(`rarityPalette(${r})`, () => L.rarityPalette('steel', r));
  run(`lootBeam(${r})`, () => L.lootBeam(r));
  run(`drawLootBeam(${r})`, () => L.drawLootBeam(ctx, r, 200, 300, { time: 300 }));
  run(`rarityBurst(${r})`, () => L.rarityBurst(r));
  run(`drawRarityBurst(${r})`, () => L.drawRarityBurst(ctx, r, 200, 200, { time: 300 }));
}
run('rarityStyle garbage', () => L.rarityStyle('__NOPE__'));
run('resolveShape empty',  () => L.resolveShape({}));
run('resolveShape null',   () => L.resolveShape(null));
// every shape key directly, at every rarity
for (const sk of L.SHAPE_KEYS) {
  run(`shapeMaterial(${sk})`, () => L.shapeMaterial(sk));
  for (const r of L.RARITY_KEYS) {
    const img = run(`shapeSprite(${sk},${r})`, () => L.shapeSprite(sk, r));
    if (!img || !img.width) itemUnresolved.push(`shapeSprite ${sk}/${r} bad`);
    run(`shapeGrid(${sk},${r})`, () => L.shapeGrid(sk, r));
  }
}
// hero gear overlays
const gear = { weapon: V.items.find(i => i.slot === 'weapon'), offhand: V.items.find(i => i.slot === 'offhand'),
               head: V.items.find(i => i.slot === 'head'), chest: V.items.find(i => i.slot === 'chest') };
for (const k of ['weapon','offhand','head','chest']) {
  run(`gearOverlay(${k})`, () => L.gearOverlay(k, gear[k]));
}
run('heroWeaponOverlay', () => L.heroWeaponOverlay(gear.weapon));
run('heroShieldOverlay', () => L.heroShieldOverlay(gear.offhand));
run('heroHelmOverlay',   () => L.heroHelmOverlay(gear.head));
run('heroCloakOverlay',  () => L.heroCloakOverlay(gear.chest));
run('heroWeaponKeyFor',  () => L.heroWeaponKeyFor(gear.weapon));
const layers = run('heroGearLayers', () => L.heroGearLayers(gear));
run('drawHeroGear', () => L.drawHeroGear(ctx, layers, 50, 50, 2));
run('heroWithGear', () => L.heroWithGear(newCanvas(16, 24), gear));
run('heroGearLayers empty', () => L.heroGearLayers({}));
run('drawHeroGear null', () => L.drawHeroGear(ctx, null, 0, 0, 1));
run('setReducedMotion', () => { L.setReducedMotion(true); L.setReducedMotion(false); });
run('lootArtStats', () => L.lootArtStats());

/* ---------------- 3. spellfx: every spell, every damage kind ---------------- */
const spellMiss = [], kindMiss = [];
for (const sp of V.spells) {
  if (!S.SPELL_ANIMATIONS[sp]) spellMiss.push(`SPELL_ANIMATIONS missing ${sp}`);
  if (!S.SPELL_COLOURS[sp])    spellMiss.push(`SPELL_COLOURS missing ${sp}`);
  const e = run(`createEffect(${sp})`, () => S.createEffect(sp, { x: 320, y: 200 }));
  if (!e) { spellMiss.push(`createEffect(${sp}) -> null`); continue; }
  run(`effectDuration(${sp})`, () => S.effectDuration(sp));
  run(`toFxEffect(${sp})`, () => S.toFxEffect(e));
  const dur = S.effectDuration(sp) || 1;
  enterLoop(`spell:${sp}`);
  for (let t = 0; t <= dur * 1000 + 100; t += 33) {
    if (e.update) e.update(0.033);
    if (e.draw) e.draw(ctx, t / 1000);
  }
  exitLoop();
}
for (const kind of Object.values(FX.DAMAGE_KIND)) {
  if (!S.ATTACK_ANIMATIONS[kind]) kindMiss.push(`ATTACK_ANIMATIONS missing ${kind}`);
  if (!S.ATTACK_COLOURS[kind])    kindMiss.push(`ATTACK_COLOURS missing ${kind}`);
  const e = run(`createEffect(${kind})`, () => S.createEffect(kind, { x: 320, y: 200 }));
  if (!e) { kindMiss.push(`createEffect(${kind}) -> null`); continue; }
  enterLoop(`attack:${kind}`);
  for (let t = 0; t < 1200; t += 33) { if (e.update) e.update(0.033); if (e.draw) e.draw(ctx, t / 1000); }
  exitLoop();
}
run('createEffect garbage', () => S.createEffect('__nope__', {}));
run('effectDuration garbage', () => S.effectDuration('__nope__'));
run('warmCache', () => S.warmCache(V.spells));
run('warmCache all', () => S.warmCache(Object.keys(S.EFFECT_INDEX)));
// reducedMotion path
for (const sp of V.spells) {
  const e = run(`createEffect reduced ${sp}`, () => S.createEffect(sp, { x: 100, y: 100, reducedMotion: true }));
  if (e) { enterLoop(`reduced:${sp}`); for (let t = 0; t < 900; t += 33) { e.update && e.update(0.033); e.draw && e.draw(ctx, t / 1000); } exitLoop(); }
}

/* ---------------- 4. battlescene: every biome, field + boss ---------------- */
const biomeMiss = [];
const regionBiomes = [...new Set(V.regions.map(r => r.biome))];
for (const bi of regionBiomes) {
  if (!SC.BIOME_KEYS.includes(bi)) biomeMiss.push(`BIOME_KEYS missing ${bi}`);
}
SC.resetSceneStats();
const scenes = [];
for (const r of V.regions) {
  for (const bossRow of [null, V.bosses.find(b => b.region === r.id) || V.bosses[0]]) {
    const sc = run(`createScene(${r.id}${bossRow ? '/boss' : ''})`, () => SC.createScene({
      biome: r.biome, palette: r.palette, boss: bossRow, key: r.id + (bossRow ? '|boss' : ''),
    }));
    if (!sc) { biomeMiss.push(`createScene(${r.id}) -> null`); continue; }
    scenes.push(sc);
    run(`sceneAnchors(${r.id})`, () => SC.sceneAnchors(sc));
    const cam = run('createCamera', () => SC.createCamera());
    enterLoop(`scene:${r.biome}`);
    for (let t = 0; t < 2000; t += 33) {
      if (cam && cam.update) cam.update(0.033);
      SC.applyCamera(ctx, cam, sc.stage);
      SC.drawScene(ctx, sc, t / 1000, cam);
      SC.drawForeground(ctx, sc, t / 1000, cam);
    }
    exitLoop();
    run(`drawRimLight(${r.id})`, () => SC.drawRimLight(ctx, sc, newCanvas(64, 64), 100, 100, {}));
    run(`drawFigureShadow(${r.id})`, () => SC.drawFigureShadow(ctx, sc, 100, 40, {}));
  }
}
const allocAfterBuild = SC.sceneStats().canvases;
// draw-loop allocation probe: run more frames, see if the counter moves
const probeScene = scenes[0];
const before = SC.sceneStats().canvases;
enterLoop('alloc-probe');
for (let t = 0; t < 3000; t += 16) { SC.drawScene(ctx, probeScene, t / 1000, null); SC.drawForeground(ctx, probeScene, t / 1000, null); }
exitLoop();
const after = SC.sceneStats().canvases;
run('createScene garbage biome', () => SC.createScene({ biome: '__nope__' }));
run('createScene empty', () => SC.createScene({}));
run('drawScene null', () => SC.drawScene(ctx, null, 0, null));
run('destroyScene', () => { for (const s of scenes) SC.destroyScene(s); });
run('reducedMotion scene', () => {
  const s = SC.createScene({ biome: 'dungeon', reducedMotion: true });
  for (let t = 0; t < 500; t += 33) SC.drawScene(ctx, s, t / 1000, null);
  SC.destroyScene(s);
});

/* ---------------- report ---------------- */
const snap = snapshot();
console.log(JSON.stringify({
  snap,
  bossDrawn,
  sceneAllocDuringBuild: allocAfterBuild,
  sceneAllocDuringDraw: after - before,
  counts: {
    throws: fail.length, bossUnresolved: bossUnresolved.length,
    itemUnresolved: itemUnresolved.length, iconMiss: iconMiss.length, slotMiss: slotMiss.length,
    rarityMiss: rarityMiss.length, spellMiss: spellMiss.length, kindMiss: kindMiss.length,
    biomeMiss: biomeMiss.length,
  },
  detail: {
    throws: fail.slice(0, 25), bossUnresolved, itemUnresolved: itemUnresolved.slice(0, 20),
    iconMiss, slotMiss, rarityMiss, spellMiss, kindMiss, biomeMiss,
    nullImage: REC.nullImage.slice(0, 12), nonFinite: REC.nonFinite.slice(0, 12),
    badPaint: REC.badPaint.slice(0, 12), allocInLoop: REC.allocInLoop.slice(0, 8),
  },
}, null, 1));
