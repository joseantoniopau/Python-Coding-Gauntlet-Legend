/* A read-only visual QA surface. Uses production renderers, never game state. */
import * as S from './sprites.js';
import * as M from './monsterart.js';
import * as B from './bosses.js';
import * as T from './tiles.js';
import * as P from './petart.js';
import * as Stage from './battlescene.js';
import { BATTLE_HERO, COMBAT_POSES, combatFrame } from './battlehero.js';
import {createCinema, createTitleArt} from './cinema.js';
import {playScene} from './finaleui.js';

const $=s=>document.querySelector(s), jobs=[];
const sizes=new ResizeObserver(entries=>{
  for(const {target} of entries){const c=target.querySelector('canvas');if(c)c.style.width=`${c.width*Math.max(1,Math.min(Number(c.dataset.scale),Math.floor(target.clientWidth/c.width)))}px`;}
});
const regionPalettes=['dawn','spring','amber','verdant','stone','moss','slate','ember','royal','dusk','moss','ash','gold','iron','azure','sun','void'];
let playing=false, raf=0, collection='', last=0, artTime=0, generation=0, specimens=null, currentFilm=null;
function card(name, detail, w, h, scale, draw) {
  const figure=document.createElement('figure'), mount=document.createElement('div'), canvas=document.createElement('canvas'), caption=document.createElement('figcaption');
  canvas.width=w;canvas.height=h;canvas.dataset.scale=String(scale);canvas.style.width=`${w*scale}px`;canvas.setAttribute('aria-label',name);mount.className='art';
  const strong=document.createElement('strong'), small=document.createElement('small');strong.textContent=name;small.textContent=detail;
  const download=document.createElement('button');download.type='button';download.className='export-study';download.textContent='Export PNG';download.setAttribute('aria-label',`Export ${name} as PNG`);
  download.onclick=()=>{figure.querySelector('.exported-image')?.remove();const link=document.createElement('a'),image=document.createElement('img');link.className='exported-image';link.download=name.toLowerCase().replace(/[^a-z0-9]+/g,'-')+'.png';link.href=canvas.toDataURL('image/png');image.src=link.href;image.alt=`Captured frame: ${name}. Select to save the PNG.`;image.style.cssText='max-width:100%;image-rendering:pixelated';link.append(image);figure.append(link);};
  caption.append(strong,small,download);mount.append(canvas);figure.append(mount,caption);$('#gallery').append(figure);
  sizes.observe(mount);
  const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
  const job={figure,draw(t){ctx.clearRect(0,0,w,h);draw(ctx,t);}};
  jobs.push(job);job.draw(artTime);return job;
}
function sprite(name,detail,w,h,build) { card(name,detail,w,h,3,(ctx,t)=>{const image=build(t);ctx.drawImage(image,Math.floor((w-image.width)/2),h-image.height);}); }
function clear() { sizes.disconnect();for(const j of jobs)if(j.dispose)j.dispose(); jobs.length=0;$('#gallery').replaceChildren(); }
async function render() {
  const pass=++generation;clear();collection=$('#collection').value;artTime=0;
  $('#status').className='';$('#film-controls').hidden=collection!=='cinema';
  try {
    if(collection==='heroes') {
      for(const cls of S.HERO_CLASSES) for(const body of S.HERO_BODY_TYPES) {
        const look={class_id:cls,body,armor:{helmet:75,chestplate:75,boots:75,gauntlets:75,shield:50}};
        card(`${cls} · body ${body}`,'Field directions + six authored combat poses',128,128,2,(ctx,t)=>{
          for(let i=0;i<4;i++)ctx.drawImage(S.heroFrame(['down','left','up','right'][i],Math.floor(t*5)%4,look),12+i*28,2);
          COMBAT_POSES.forEach((p,i)=>ctx.drawImage(combatFrame(p,Math.floor(t*2)%2,look),i%3*42,29+Math.floor(i/3)*48));
        });
      }
      for(const key of S.PORTRAIT_KEYS)sprite(key,'Dialogue portrait · expressive production frames',32,32,t=>S.portraitAt(key,['neutral','alarmed','delighted'][Math.floor(t/2)%3],t*1000));
    } else if(collection==='monsters') {
      for(const key of M.MONSTER_KEYS) {const n=M.monsterSize(key);sprite(key,`${M.MONSTERS[key].rank||'mob'} · ${n} source pixels`,Math.max(64,n),64,t=>M.monsterFrame(key,Math.floor(t*4)%4));}
    } else if(collection==='bosses') {
      for(const key of B.BOSS_ARCHETYPES)for(const phase of [0,2,5]){
        sprite(`${key} · phase ${phase+1}`,'Production boss body, material and transformation',112,144,t=>B.bossSprite(key,null,Math.floor(t*2)%5,{phase}));
      }
    } else if(collection==='towns') {
      Object.entries(M.REGION_BIOME).forEach(([region,biome],i)=>{
        const set=T.terrainSet(region,regionPalettes[i],3,biome);
        card(region,'Four reconstruction stages · four building types',160,160,2,(ctx,t)=>{
          for(let y=0;y<10;y++)for(let x=0;x<10;x++)ctx.drawImage(set.ground[(x+y)%set.ground.length],x*16,y*16);
          for(let tier=0;tier<4;tier++)for(let v=0;v<4;v++)ctx.drawImage(set.building[tier][v],v*40,tier*40);
        });
      });
    } else if(collection==='regions') {
      Object.entries(M.REGION_BIOME).forEach(([region,biome],i)=>{
        const scene=Stage.createScene({region,biome,palette:regionPalettes[i],key:region});
        card(region,`${biome} · production scene layers + live creature`,256,224,2,(ctx,t)=>{
          Stage.drawScene(ctx,scene,t);ctx.drawImage(combatFrame('ready',Math.floor(t*2)%2),64-BATTLE_HERO.footX*2,175-BATTLE_HERO.footY*2,BATTLE_HERO.width*2,BATTLE_HERO.height*2);
          const mob=M.monsterFrame(M.rosterFor(region)[0],Math.floor(t*4)%4);ctx.drawImage(mob,174,175-mob.height*2,mob.width*2,mob.height*2);
          Stage.drawForeground(ctx,scene,t);
        });jobs[jobs.length-1].dispose=()=>Stage.destroyScene(scene);
      });
    } else if(collection==='cinema') {
      if(!specimens)specimens=await (await fetch('./art/cinematic-scenes.json')).json();
      if(pass!==generation)return;
      if(!$('#film').options.length)for(const row of specimens.scenes){const option=document.createElement('option');option.value=row.id;option.textContent=row.label;$('#film').append(option);}
      currentFilm=specimens.scenes.find(row=>row.id===$('#film').value)||specimens.scenes[0];
      $('#shot').replaceChildren();
      for(const beat of currentFilm.scene.beats){const option=document.createElement('option');option.value=String(beat.at_ms);option.textContent=beat.id.replaceAll('_',' ');$('#shot').append(option);}
      const film=createCinema(currentFilm.scene),lines=document.createElement('div');lines.className='film-lines';let lastBeat=-1;
      const job=card(currentFilm.label,'Fictional demonstration · live cinematic renderer · use Jump to beat to inspect every shot',480,270,2,(ctx,t)=>{
        const frame=film.draw(ctx,480,270,t*1000%Math.max(1,currentFilm.scene.duration_ms));
        if(frame.index!==lastBeat){lastBeat=frame.index;lines.replaceChildren();for(const line of frame.beat.lines||[]){const p=document.createElement('p');p.textContent=(line.name?line.name+': ':'')+(line.text||'');lines.append(p);}}
      });job.figure.classList.add('film-study');job.figure.append(lines);job.dispose=()=>film.dispose();
      const title=createTitleArt();const vista=card('Citadel at the edge of the realm','Original title plate · distant mountain planes, aqueduct, fluted columns and river',480,270,2,(ctx,t)=>title.draw(ctx,480,270,t,!playing));vista.figure.classList.add('film-study');
    } else if(collection==='pets') {
      for(const key of P.PET_ANIMALS)sprite(key,'Companion · four movement frames',48,48,t=>P.petFrame(key,'right',Math.floor(t*5)%4));
    }
    $('#status').textContent=`${jobs.length} live studies · ${playing?'animation playing':'paused at frame zero'}`;
  } catch(error) {$('#status').textContent=`Renderer failure: ${error.message}`;$('#status').className='error';console.error(error);}
}
function tick(now) {
  raf=0;if(!playing||document.hidden)return;
  if(now-last>=1000/12) {
    artTime+=last?Math.min(.25,(now-last)/1000):0;
    for(const j of jobs){const r=j.figure.getBoundingClientRect();if(r.bottom>0&&r.top<innerHeight)j.draw(artTime);}
    last=now;
  }
  raf=requestAnimationFrame(tick);
}
$('#collection').onchange=render;
$('#film').onchange=render;
$('#shot').onchange=()=>{artTime=Number($('#shot').value)/1000;last=0;for(const j of jobs)j.draw(artTime);$('#status').textContent=`${jobs.length} live studies · ${playing?'playing from':'paused at'} ${$('#shot').selectedOptions[0].textContent}`;};
$('#preview-film').onclick=()=>{if(currentFilm)playScene(currentFilm.scene,{reducedMotion:!playing},()=>{});};
$('#motion').onclick=()=>{playing=!playing;last=0;$('#motion').setAttribute('aria-pressed',String(playing));$('#motion').textContent=playing?'Pause animation':'Play animation';if(playing&&!raf)raf=requestAnimationFrame(tick);else if(!playing){cancelAnimationFrame(raf);raf=0;}$('#status').textContent=`${jobs.length} live studies · ${playing?'animation playing':'paused'}`;};
for(const id of ['silhouette','light'])$('#'+id).onclick=()=>{const on=document.body.classList.toggle(id);$('#'+id).setAttribute('aria-pressed',String(on));};
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;last=0;}else if(playing&&!raf)raf=requestAnimationFrame(tick);});
window.addEventListener('pagehide',()=>{cancelAnimationFrame(raf);clear();});render();
