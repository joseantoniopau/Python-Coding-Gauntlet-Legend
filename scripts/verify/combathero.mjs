import assert from 'node:assert/strict';
import { installRaster, colourCount, pixelDiff, frameHash, RASTER } from './raster.mjs';
installRaster();
const { combatFrame, combatGrid, combatSet, COMBAT_POSES, BATTLE_HERO } = await import('../../web/js/battlehero.js');
const { HERO_CLASSES, HERO_WEAPON_KEYS, heroPalette } = await import('../../web/js/sprites.js');
let sampled=0, worst=0;
const classes=new Set();
for(const cls of HERO_CLASSES) {
  const base={class_id:cls,armor:{helmet:75,chestplate:75,gauntlets:75,boots:75,shield:75}};
  classes.add(frameHash(combatFrame('ready',0,base)));
  assert(pixelDiff(combatFrame('ready',0,base),combatFrame('ready',0,{...base,body:'b'}))>0,`${cls}: body choice disappeared`);
  for(const body of ['a','b']) for(const weapon of HERO_WEAPON_KEYS) for(const rung of [0,3,5]) {
    const look={...base,body,weapon,_weapon:{rung}};
    const poses=new Set();
    for(const pose of COMBAT_POSES) for(const f of [0,1]) {
      const grid=combatGrid(pose,f,look), pal=heroPalette(look), image=combatFrame(pose,f,look);
      assert.equal(image.width,40);assert.equal(image.height,48);
      for(const row of grid){assert.equal(row.length,40);for(const glyph of row)assert(glyph==='.'||pal[glyph],`undefined material ${glyph}`);}
      assert(/[^.]/.test(grid[47]),'feet must reach the standing baseline');
      const colours=colourCount(image);worst=Math.max(worst,colours);assert(colours<=15,`palette budget ${colours}`);
      if(f===0)poses.add(frameHash(image));
      sampled++;
    }
    assert.equal(poses.size,6,`${cls}/${weapon}/${rung}: repeated pose`);
  }
}
assert.equal(classes.size,6,'class identities must survive a full suit of armor');
for(const piece of ['helmet','chestplate','gauntlets','boots','shield','legendary']) {
  assert(pixelDiff(combatFrame('ready',0,{}),combatFrame('ready',0,{armor:{[piece]:100}}))>0,`${piece} must be visible`);
}
const look={class_id:'analyst'};
const set=combatSet(look);RASTER.counting=true;const before=RASTER.canvases;
for(let n=0;n<1000;n++)for(const p of COMBAT_POSES)assert.equal(combatFrame(p,n%2,look),set[p][n%2]);
assert.equal(RASTER.canvases,before,'warm frames must not allocate');
assert.equal(BATTLE_HERO.height*BATTLE_HERO.scale,96,'keep the existing actor/effect vertical scale');
console.log(`PASS combat hero: ${sampled} frames; ${worst} colors max; six distinct equipped classes, six poses, both body choices, every armor slot, cached playback.`);
