/* Reproducible Pages studies from the production raster renderers; no save. */
import fs from 'node:fs';
import {createRequire} from 'node:module';
// Development-only renderer. Install @napi-rs/canvas or point this variable at
// an existing package. The game itself remains dependency-free.
const require=createRequire(import.meta.url);
const {createCanvas}=require(process.env.GAUNTLET_CANVAS_MODULE||'@napi-rs/canvas');
globalThis.document={createElement:()=>createCanvas(1,1),body:{appendChild(){}},documentElement:{style:{}}};
globalThis.window=globalThis;
globalThis.OffscreenCanvas=function(w,h){return createCanvas(w,h);};
globalThis.requestAnimationFrame=()=>0;globalThis.cancelAnimationFrame=()=>{};
globalThis.devicePixelRatio=1;globalThis.matchMedia=()=>({matches:false,addEventListener(){}});
const {combatFrame}=await import('../web/js/battlehero.js');
const B=await import('../web/js/bosses.js'),S=await import('../web/js/sprites.js');
const T=await import('../web/js/tiles.js'),M=await import('../web/js/monsterart.js');
const Stage=await import('../web/js/battlescene.js');
const {createCinema}=await import('../web/js/cinema.js');
function canvas(w,h){const c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').imageSmoothingEnabled=false;return c;}
function write(name,c){
  fs.writeFileSync(new URL(`../docs/assets/${name}.png`,import.meta.url),c.toBuffer('image/png'));
  console.log(`${name}: ${c.width}x${c.height}`);
}
const look={class_id:'warden',body:'b',armor:{helmet:75,chestplate:75,boots:75,gauntlets:75,shield:75}};
for(const [name,region,boss] of [['boss','binary_tree_canopy','dragon'],['guided','python_village',null]]){
  const c=canvas(256,224),ctx=c.getContext('2d'),scene=Stage.createScene({region,biome:M.REGION_BIOME[region]||'grass',key:region});
  Stage.drawScene(ctx,scene,1.2);
  if(boss)B.drawBoss(ctx,boss,184,175,{time:1200,phase:2,reducedMotion:true});
  else{const mob=M.monsterFrame('slime',0);ctx.drawImage(mob,172,175-mob.height*2,mob.width*2,mob.height*2);}
  ctx.drawImage(combatFrame('ready',0,look),28,79,80,96);Stage.drawForeground(ctx,scene,1.2);write(name,c);Stage.destroyScene(scene);
}
const town=canvas(480,270),tc=town.getContext('2d');
const regions=[['python_village','dawn'],['array_caverns','amber'],['binary_tree_canopy','verdant'],['graph_wastes','ash']];
regions.forEach(([region,palette],i)=>{const set=T.terrainSet(region,palette,3,M.REGION_BIOME[region]);const ox=(i%2)*240,oy=Math.floor(i/2)*135;
  for(let y=0;y<9;y++)for(let x=0;x<15;x++)tc.drawImage(set.ground[(x+y)%set.ground.length],ox+x*16,oy+y*16);
  for(let tier=0;tier<4;tier++)for(let type=0;type<3;type++)tc.drawImage(set.building[tier][type],ox+tier*56+6,oy+type*40+5);
});write('world',town);
const sheet=canvas(384,256),ctx=sheet.getContext('2d');ctx.fillStyle='#171c29';ctx.fillRect(0,0,384,256);
S.HERO_CLASSES.forEach((id,i)=>{['ready','cast','strike'].forEach((pose,j)=>ctx.drawImage(combatFrame(pose,0,{...look,class_id:id}),i*64+12,j*50));});
// Portraits and creatures occupy a second band below three hero pose rows.
S.PORTRAIT_KEYS.slice(0,8).forEach((id,i)=>ctx.drawImage(S.portraitAt(id,'neutral',0),i*48+8,159));
['wolf','skeleton','goblin','slime','bat','mimic','spider','imp'].forEach((id,i)=>{const m=M.monsterFrame(id,0);ctx.drawImage(m,i*48+12,246-m.height);});write('art-room',sheet);
const fixtures=JSON.parse(fs.readFileSync(new URL('../web/art/cinematic-scenes.json',import.meta.url),'utf8'));
const scene=fixtures.scenes.find(r=>r.id==='pass_two_rosters')?.scene||fixtures.scenes[1].scene;
const film=createCinema(scene,{look}),c=canvas(480,270),beat=scene.beats.find(b=>b.id==='forming_up');film.draw(c.getContext('2d'),480,270,beat.at_ms+beat.duration_ms*.7);write('cinematic',c);film.dispose();
