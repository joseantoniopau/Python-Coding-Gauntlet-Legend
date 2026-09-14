/* Original cinematic plates: painted colour planes and inked architecture on a
 * 480 × 270 grid. Playback is a pure function of the supplied script and clock.
 * No saves, timers, random draws or network requests belong in this module. */
import { heroFrame, portrait, gridSprite } from './sprites.js';
import { BATTLE_HERO, combatFrame } from './battlehero.js';
import { kingSprite, indexSphere } from './kingui.js';
import { bossSprite } from './bosses.js';
import { petFrame } from './petart.js';

export const CINEMA_SIZE = Object.freeze({ width: 480, height: 270 });
export const CAMERA_MOVES = Object.freeze(['HOLD','PUSH_IN','PULL_BACK','TRACK_LEFT','CRANE_UP','WHIP_PAN','LOCK_OFF','FREEZE','AERIAL','CUT']);
const W=480, H=270;
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number.isFinite(v)?v:a));
const smooth=t=>t*t*(3-2*t);
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const frac=v=>v-Math.floor(v);
const hash=(s)=>{let n=2166136261;for(const c of String(s))n=Math.imul(n^c.charCodeAt(0),16777619);return n>>>0;};
function canvas(){const c=document.createElement('canvas');c.width=W;c.height=H;c.getContext('2d').imageSmoothingEnabled=false;return c;}
function rect(c,x,y,w,h,color){c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.ceil(w),Math.ceil(h));}
// Scanline polygons keep the plate pixel grid exact and make the raster harness
// exercise real painted geometry, including the mountain and vault silhouettes.
function poly(c,points,color){
  c.fillStyle=color;
  const low=Math.max(0,Math.floor(Math.min(...points.map(p=>p[1]))));
  const high=Math.min(H,Math.ceil(Math.max(...points.map(p=>p[1]))));
  for(let y=low;y<high;y++){
    const cuts=[];
    for(let i=0,j=points.length-1;i<points.length;j=i++){
      const [x1,y1]=points[i],[x2,y2]=points[j];
      if((y1>y)!==(y2>y))cuts.push(x1+(y-y1)*(x2-x1)/(y2-y1));
    }
    cuts.sort((a,b)=>a-b);
    for(let i=0;i+1<cuts.length;i+=2)c.fillRect(Math.ceil(cuts[i]),y,Math.floor(cuts[i+1])-Math.ceil(cuts[i])+1,1);
  }
}
function oval(c,x,y,rx,ry,color){
  c.fillStyle=color;
  for(let j=-Math.ceil(ry);j<=ry;j++){
    const half=rx*Math.sqrt(Math.max(0,1-j*j/(ry*ry)));
    c.fillRect(Math.round(x-half),Math.round(y+j),Math.ceil(half*2),1);
  }
}
function line(c,x1,y1,x2,y2,color){
  const count=Math.max(Math.abs(x2-x1),Math.abs(y2-y1));
  for(let n=0;n<=count;n++)rect(c,x1+(x2-x1)*n/Math.max(1,count),y1+(y2-y1)*n/Math.max(1,count),1,1,color);
}
function bandSky(c,dawn=false){
  const colors=dawn?['#252939','#34384a','#534553','#855c60','#bd806d','#e9af82','#f2ca98']:['#080e1b','#11162a','#1c213b','#31304d','#50425c','#705364','#966468'];
  colors.forEach((p,i)=>rect(c,0,i*26,W,27,p));
  // Dry-brush cloud edges are broad clusters, never per-pixel noise.
  for(let i=0;i<18;i++){
    const x=(i*83)%510-24,y=28+(i*19)%89,len=25+(i*11)%68;
    rect(c,x,y,len,2,colors[Math.min(6,1+Math.floor(y/26))]);
    rect(c,x+9,y+3,len-18,1,colors[Math.min(6,2+Math.floor(y/26))]);
  }
  oval(c,354,71,25,25,dawn?'#f3cb99':'#bfabb0');
  if(!dawn)oval(c,344,64,23,23,'#31304d');
}
const RIDGES=[
  [[-40,179],[10,145],[40,161],[87,88],[121,137],[151,119],[185,157],[233,104],[263,145],[295,112],[332,160],[383,99],[420,151],[472,121],[520,165]],
  [[-30,206],[18,162],[53,179],[99,149],[132,170],[166,142],[212,191],[258,151],[303,177],[339,139],[383,172],[430,157],[511,201]],
];
function mountains(c,dawn=false){
  RIDGES.forEach((r,i)=>poly(c,[...r,[520,H],[-40,H]],dawn?(i?'#5d6267':'#777582'):(i?'#242940':'#46425b')));
  for(const [x,y] of RIDGES[0].slice(1,-1)){
    if(y>140)continue;
    poly(c,[[x,y],[x-13,y+23],[x-2,y+16],[x+8,y+27],[x+19,y+31]],dawn?'#c5b6af':'#797084');
    poly(c,[[x,y+7],[x+2,y+38],[x+19,y+31]],dawn?'#87838e':'#53516d');
  }
  poly(c,[[0,217],[67,194],[147,214],[232,198],[312,209],[389,188],[480,200],[480,270],[0,270]],dawn?'#686965':'#252431');
  // A pale river leads to the distant gate; the eye follows quiet value masses.
  poly(c,[[362,164],[342,184],[322,196],[294,208],[232,219],[178,250],[107,270],[162,270],[217,250],[256,230],[314,216],[338,196],[356,185]],dawn?'#baae9b':'#64556d');
  line(c,331,201,303,214,dawn?'#d7bfa3':'#927487');
}
function spire(c,x,y,height,width,lit=false){
  const ink='#121824',mid=lit?'#817878':'#303146',rim=lit?'#c1a18d':'#6c5b69';
  rect(c,x-width/2,y-height,width,height,ink);
  rect(c,x-width/2+2,y-height+4,width/2-1,height-4,mid);
  line(c,x-width/2,y-height+2,x-width/2,y,rim);
  poly(c,[[x-width/2-3,y-height],[x,y-height-18],[x+width/2+3,y-height]],ink);
  line(c,x-1,y-height-16,x-width/2-2,y-height-1,rim);
  for(let q=y-height+9;q<y-6;q+=12){rect(c,x-1,q,3,5,ink);if(lit)rect(c,x,q+1,1,3,'#e9b77f');}
  rect(c,x-width/2-3,y-3,width+6,3,ink);
}
function citadel(c,dawn=false){
  // Asymmetric buttresses and a needle keep this separate from a generic castle.
  poly(c,[[282,196],[291,173],[309,167],[314,153],[344,155],[350,172],[378,184],[387,199]],'#141b2b');
  rect(c,297,158,53,31,dawn?'#777274':'#353247');
  for(let x=300;x<349;x+=10){rect(c,x,152,5,12,'#171a2b');line(c,x,164,x-4,190,dawn?'#aaa08d':'#655369');}
  spire(c,326,174,75,15,dawn);spire(c,302,183,34,10,dawn);spire(c,351,187,48,11,dawn);
  poly(c,[[322,173],[326,165],[330,173],[330,185],[322,187]],'#101626');
  line(c,329,99,334,122,dawn?'#b5a28f':'#8f7181');
  // Suspended aqueduct, including visible air between its piers.
  rect(c,195,186,107,4,dawn?'#969084':'#4b4258');
  for(let x=197;x<297;x+=15){rect(c,x,190,4,14,'#202336');poly(c,[[x+4,190],[x+11,190],[x+7,193]],'#202336');}
}
function foreground(c,dawn=false){
  poly(c,[[0,218],[29,207],[57,220],[78,218],[113,239],[139,244],[156,270],[0,270]],'#0b1220');
  poly(c,[[374,270],[405,235],[428,235],[458,214],[480,216],[480,270]],'#0b1220');
  line(c,5,218,29,209,dawn?'#a4826b':'#706179');line(c,30,211,54,221,dawn?'#a4826b':'#706179');
  // Broken fluted columns frame the vista, a hand-painted cel-background motif.
  poly(c,[[4,0],[23,0],[22,136],[13,142],[6,176]],'#111827');
  rect(c,9,0,3,128,'#354052');rect(c,19,0,2,120,'#222c40');
  poly(c,[[449,0],[480,0],[480,193],[463,164],[464,74],[452,63]],'#0d1523');
  line(c,453,1,457,57,'#514353');line(c,468,82,467,156,'#392d3d');
}
function vista(dawn=false){const c=canvas(),g=c.getContext('2d');bandSky(g,dawn);mountains(g,dawn);citadel(g,dawn);return c;}
function vault(){
  const c=canvas(),g=c.getContext('2d');
  rect(g,0,0,W,H,'#10131e');
  poly(g,[[0,0],[480,0],[347,93],[131,93]],'#1d2330');
  poly(g,[[0,0],[131,93],[131,191],[0,259]],'#29303b');
  poly(g,[[480,0],[347,93],[347,191],[480,259]],'#242a36');
  rect(g,131,91,216,103,'#181e29');
  for(let x=138;x<345;x+=26){
    rect(g,x,103,18,67,'#101621');poly(g,[[x,103],[x+9,92],[x+18,103]],'#101621');
    line(g,x-1,103,x-1,170,'#50505a');line(g,x-1,103,x+8,92,'#65606a');
    rect(g,x-3,168,24,4,'#343c49');rect(g,x+2,155,14,2,'#716266');
  }
  // Repeated vault ribs converge on a shared vanishing point.
  for(let i=0;i<5;i++){
    const left=6+i*24,top=i*17,span=480-left*2;
    line(g,left,187,left,top+33,'#5b555f');line(g,left,top+33,240,14+i*16,'#514c57');
    line(g,240,14+i*16,left+span,top+33,'#383d49');line(g,left+span,top+33,left+span,187,'#383d49');
    rect(g,left-4,184,11,6,'#675a5c');rect(g,left+span-5,184,11,6,'#45414b');
  }
  for(let side=0;side<2;side++)for(let i=0;i<4;i++){
    const x=side?372+i*26:81-i*26,y=83-i*13;
    rect(g,x,y,20,87+i*9,'#111722');
    poly(g,[[x,y],[x+10,y-12],[x+20,y]],'#111722');
    line(g,x-2,y,x+9,y-13,'#797078');line(g,x-2,y,x-2,y+89+i*9,'#545160');
    rect(g,x-4,y+84+i*9,28,4,'#77656a');
  }
  poly(g,[[0,225],[130,187],[348,187],[480,225],[480,270],[0,270]],'#252b36');
  for(let y=193;y<271;y+=Math.max(5,Math.floor((y-170)/7)))line(g,0,y,480,y,'#393b43');
  for(let x=-300;x<900;x+=74)line(g,240,181,x,270,'#48424b');
  // The upper stair stays spatially separate from the rescued formation.
  for(let i=0;i<8;i++){rect(g,379-i*4,155+i*9,111+i*4,9,'#343741');rect(g,379-i*4,155+i*9,111+i*4,2,'#786766');}
  poly(g,[[390,12],[449,12],[449,143],[390,174]],'#0a101c');
  line(g,388,15,388,171,'#62565b');
  return c;
}
function town(){
  const c=vista(true),g=c.getContext('2d');
  poly(g,[[0,174],[480,176],[480,270],[0,270]],'#87766b');
  for(let y=186;y<H;y+=13)for(let x=10+(y%2)*11;x<W;x+=29){rect(g,x,y,22,2,'#a79580');rect(g,x+4,y+3,16,1,'#75695f');}
  for(const [x,y,w,h] of [[21,146,100,64],[326,138,132,81]]){
    rect(g,x,y,w,h,'#b09678');rect(g,x+w*.62,y,w*.38,h,'#817063');
    poly(g,[[x-10,y],[x+w/2,y-43],[x+w+8,y]],'#384858');
    poly(g,[[x-8,y],[x+w/2,y-41],[x+w*.53,y-27],[x+6,y]],'#596271');
    for(let q=0;q<3;q++)line(g,x+9+q*12,y-3-q*9,x+w-8-q*12,y-3-q*9,'#748087');
    rect(g,x+18,y+10,21,32,'#2f3d45');rect(g,x+21,y+13,15,21,'#dab180');rect(g,x+27,y+12,3,24,'#62584f');
    rect(g,x+60,y+21,24,h-21,'#3b3d3e');line(g,x+61,y+24,x+61,y+h-2,'#c4a489');
    rect(g,x-3,y-1,w+7,4,'#353c48');rect(g,x+w-26,y-43,12,22,'#857b73');rect(g,x+w-28,y-45,16,3,'#b39a83');
    line(g,x+1,y+3,x+1,y+h,'#d4b38c');
  }
  rect(g,127,150,3,75,'#45454b');rect(g,129,150,35,3,'#45454b');
  poly(g,[[132,153],[160,153],[158,177],[147,182],[134,176]],'#9c6b54');
  line(g,137,158,153,173,'#d4af80');line(g,151,158,139,172,'#d4af80');
  // An open lesson box and six loose rune slats, not a victorious trophy.
  poly(g,[[230,231],[257,229],[263,239],[235,243]],'#534e48');
  poly(g,[[230,231],[228,219],[252,215],[257,229]],'#aa8860');
  for(let n=0;n<6;n++){rect(g,228+(n*13)%40,245+Math.floor(n/3)*5,11,3,'#d3b58a');rect(g,230+(n*13)%40,246+Math.floor(n/3)*5,5,1,'#655650');}
  return c;
}

function beatAt(scene,ms){let i=-1;for(let n=0;n<(scene.beats||[]).length;n++){if(ms>=num(scene.beats[n].at_ms))i=n;else break;}return i;}
function cameraFor(beat,p,scene){
  const c=beat.camera||{},e=smooth(p),pull=clamp(num(c.pullback,scene.roll_call?.pullback||1),1,2.6);
  // Cast rows already fit inside the painted plate. The script's distance
  // multiplier opens a close shot to native scale; it must never shrink the
  // entire room below the viewport. The separate stair roster needs full width.
  const released=scene.released||scene.roll_call?.released||[];
  const wideZoom=released.length?1:clamp(1.25/pull,1,1.25);
  let x=240,y=135,zoom=1;
  if(c.subject==='king'){x=314;y=138;zoom=1.25;}
  if(c.subject==='interpreter'){x=306;y=172;zoom=c.framing==='head'?1.65:1.1;}
  if(c.to==='one_sphere'){x=232;y=138;zoom=1+e*9;}
  else if(c.move==='PUSH_IN')zoom*=1+e*.45;
  else if(c.move==='PULL_BACK')zoom*=1.3-e*.3;
  else if(c.move==='TRACK_LEFT'){x=275-e*70;zoom=Math.max(zoom,1.25);}
  else if(c.move==='CRANE_UP'){zoom=1.25+(wideZoom-1.25)*e;y=154-e*19;}
  else if(c.move==='WHIP_PAN'){x=210+60*smooth(clamp(p/.22));zoom=Math.max(zoom,1.25);}
  else if(c.move==='AERIAL'){x=231+18*e;y=125+9*e;zoom=1.08;}
  else if(c.move==='LOCK_OFF')zoom=wideZoom;
  if(c.subject==='pel'){x=246;y=174;zoom=1.17;}
  // Keep a finite painted background behind every shot. Pans use a cropped
  // view with room to travel, rather than revealing the canvas beyond the art.
  zoom=Math.max(1,zoom);
  x=clamp(x,W/(2*zoom),W-W/(2*zoom));
  y=clamp(y,H/(2*zoom),H-H/(2*zoom));
  return {x,y,zoom};
}

/** Pure script sampler, also the integration seam for art-gallery scrubbing. */
export function cinematicFrame(scene,elapsedMs=0,{reducedMotion=false}={}){
  const ms=Math.max(0,num(elapsedMs)),index=beatAt(scene,ms),beat=scene.beats?.[index]||{};
  const local=Math.max(0,ms-num(beat.at_ms)),progress=clamp(local/Math.max(1,num(beat.duration_ms,1)));
  let artBeat=beat,artMs=ms,artProgress=progress;
  const frozen=beat.camera?.move==='FREEZE';
  if(frozen){
    let first=index;while(first>0&&scene.beats[first-1].camera?.move==='FREEZE')first--;
    artBeat=scene.beats[Math.max(0,first-1)]||beat;artMs=num(scene.beats[first]?.at_ms);artProgress=1;
  }
  const camera=cameraFor(artBeat,reducedMotion?1:artProgress,scene);
  const fx=beat.fx||[],staged=artBeat.stage||[];
  const world=staged.includes('world'),dawn=fx.includes('dawn');
  const mode=staged.includes('black')?'black':world?'world':staged.includes('pel')?'town':'vault';
  const freed=staged.includes('freed')?(scene.roll_call?.rows||[]):[];
  const released=staged.includes('released')?(scene.released||scene.roll_call?.released||[]):[];
  const rows=beat.rows||[];
  // Speaking slots follow the server's own timing, including a capped last slot.
  let slot=rows.length?Math.min(rows.length-1,Math.floor(progress*rows.length)):-1;
  if(rows.length&&['roll_call','the_ones_nobody_came_for'].includes(beat.id)){
    // finale.py's spoken/read speeds: the producer sends the speaking count in
    // camera.rows. Keep long rosters within its actual capped beat duration.
    const spoken=Math.min(rows.length,num(beat.camera?.rows,rows.length));
    const nominal=spoken*900+(rows.length-spoken)*260;
    const available=Math.max(1,num(beat.duration_ms)- (beat.id==='the_ones_nobody_came_for'?3200:0));
    const clock=local*Math.max(1,nominal/available);
    slot=Math.min(rows.length-1,clock<spoken*900?Math.floor(clock/900):spoken+Math.floor((clock-spoken*900)/260));
  }
  return { index,beat,local,progress,frozen,artMs:reducedMotion?0:artMs,camera,mode,dawn,fx,staged,freed,released,
    castRow:slot>=0?rows[slot]:null,castIndex:slot,
    sunglasses:fx.includes('sunglasses')?smooth(clamp(local/500)):(frozen&&index>0&&scene.beats.slice(0,index).some(b=>b.fx?.includes('sunglasses'))?1:0),
    paletteMix:frozen?1:beat.id==='unfreeze'?1-clamp(local/1200):0,
    indexLight:fx.includes('green_index_lit')?1:fx.includes('index_fails')?1-clamp(local/700):0,
    kingOpacity:staged.includes('king')?(fx.includes('king_unresolves')?1-progress:1):0,
  };
}

function tintFour(image, target=null){
  const out=target||document.createElement('canvas');out.width=image.width;out.height=image.height;
  const c=out.getContext('2d');c.drawImage(image,0,0);const d=c.getImageData(0,0,out.width,out.height);
  const ramp=[[10,10,12],[74,82,96],[255,138,43],[242,234,216]];
  for(let i=0;i<d.data.length;i+=4){if(!d.data[i+3])continue;const l=(d.data[i]*.25+d.data[i+1]*.6+d.data[i+2]*.15)/255;const p=ramp[l<.19?0:l<.42?1:l<.67?2:3];d.data[i]=p[0];d.data[i+1]=p[1];d.data[i+2]=p[2];}
  c.putImageData(d,0,0);return out;
}
function makeCast(row){
  const identity=hash(row.id||row.name||'unnamed');
  const key=row.sprite||'architect';
  const colors=['#9c705f','#687884','#9a825f','#6d718f','#89758a'];
  const look={class_id:['analyst','archivist','warden','artificer','seer'][identity%5],cloak:colors[identity%5]};
  return {row,body:heroFrame('down',0,look,'idle'),portrait:portrait(key)};
}

/** All image allocation happens here, outside the playback loop. */
export function createCinema(scene={},opts={}){
  const stage=canvas(),ctx=stage.getContext('2d');
  const plates={vault:vault(),world:vista(false),dawn:vista(true),town:town()};
  const held=canvas();
  let heldReady=false;
  const hero=[0,1].map(f=>combatFrame('ready',f,opts.look||{},opts.gear||null));
  const king=kingSprite('UNQUIET',0,1),sphere=indexSphere(1);
  const interpreter=bossSprite('interviewer','#7d8b96',0);
  const llama=petFrame('llama','left',0,{}),pel=heroFrame('down',0,{class_id:'analyst'},'idle');
  const casts=new Map();
  for(const row of [...(scene.roll_call?.rows||[]),...(scene.released||scene.roll_call?.released||[]),...(scene.beats||[]).flatMap(b=>b.rows||[])]){
    if(row&&typeof row==='object'&&(row.id||row.sprite))casts.set(row.id||row.name,makeCast(row));
  }
  // Named supplemental cast is optional. Never synthesize a crowd from a count.
  const mentors=(opts.mentors||[]).map(makeCast),companions=(opts.companions||[]).map(makeCast);
  let disposed=false;
  function draw(out,width,height,elapsedMs=0){
    if(disposed)return null;
    const f=cinematicFrame(scene,elapsedMs,opts),t=f.artMs/1000;
    const plate=f.mode==='world'?(f.dawn?plates.dawn:plates.world):plates[f.mode];
    rect(ctx,0,0,W,H,'#080d16');
    const cam=f.camera;
    const project=(image,x=0,y=0,w=image.width,h=image.height,alpha=1)=>{
      ctx.globalAlpha=alpha;
      ctx.drawImage(image,Math.round(W/2+(x-cam.x)*cam.zoom),Math.round(H/2+(y-cam.y)*cam.zoom),Math.round(w*cam.zoom),Math.round(h*cam.zoom));ctx.globalAlpha=1;
    };
    if(plate)project(plate);
    // A pan reveals separate depth planes, without blurring pixel edges.
    if(f.mode==='world'){
      for(let i=0;i<6;i++){const x=(i*103+17)-((opts.reducedMotion?0:t)*2)%103;rect(ctx,x,98+i*9,44+i*2,1,f.dawn?'#d2b8a3':'#746477');}
      if(f.fx.includes('name_rail')){ctx.font='7px monospace';ctx.fillStyle='#c5c0c1';for(let i=0;i<(scene.name_rail||[]).length;i++)ctx.fillText(scene.name_rail[i],(i*79-t*35)%570-30,55+i%3*18);}
    }
    if(f.mode==='vault'){
      for(let i=0;i<8;i++){const x=149+i*26;if(f.indexLight>0)project(sphere,x,133,10,10,f.indexLight);else{oval(ctx,W/2+(x+5-cam.x)*cam.zoom,H/2+(138-cam.y)*cam.zoom,3*cam.zoom,3*cam.zoom,'#222d34');}}
      if(f.fx.includes('stair_light'))poly(ctx,[[396,0],[460,0],[480,245],[329,216]],'#d1ab7424');
    }
    const drawPerson=(image,x,y,s=1,alpha=1)=>{project(image,x-image.width*s/2,y-image.height*s,image.width*s,image.height*s,alpha);};
    if(f.staged.includes('interpreter')){
      // The real final-boss art supplies the coils and hat; no surrogate monster.
      drawPerson(interpreter,318,237,.9);
    }
    if(f.staged.includes('mentors'))mentors.forEach((a,i)=>drawPerson(a.body,132+i*22,162,1,.45));
    if(f.staged.includes('companions'))companions.forEach((a,i)=>drawPerson(a.body,284+i*20,162,1,.45));
    const ranks=Math.max(1,num(scene.roll_call?.ranks,1));
    // Back rows paint first. The roster remains in rescue order left to right.
    for(let i=f.freed.length-1;i>=0;i--){
      const row=f.freed[i],a=casts.get(row.id||row.name);
      if(a){const per=Math.ceil(f.freed.length/ranks),rank=Math.floor(i/per);drawPerson(a.body,156+(i%per)*Math.min(24,170/Math.max(1,per-1)),201-rank*17,1);}
    }
    for(let i=f.released.length-1;i>=0;i--){
      const row=f.released[i],a=casts.get(row.id||row.name);
      if(a)drawPerson(a.body,370+(i%5)*17,197-Math.floor(i/5)*11,1,.8);
    }
    const heroX=f.mode==='town'?215:218,heroY=f.mode==='town'?238:232;
    // A source pixel remains one stage pixel before the camera transform. The
    // combat rig's planted boot, not its transparent canvas edge, owns the mark.
    const heroLeft=heroX-BATTLE_HERO.footX,heroTop=heroY-BATTLE_HERO.footY;
    if(f.staged.includes('architect')){
      const frame=opts.reducedMotion?0:Math.floor(t*(f.fx.includes('wind_from_below')?6:2))%2;
      project(hero[frame],heroLeft,heroTop,BATTLE_HERO.width,BATTLE_HERO.height);

    }
    if(f.kingOpacity>0){
      // Delete edge strips in a fixed order. He doesn't fall, burst or jitter.
      const gone=1-f.kingOpacity;
      for(let x=0;x<king.width;x++)if(frac(x*.61803398875)>=gone){
        const xx=308+(x-king.width/2)*2;
        ctx.drawImage(king,x,0,1,king.height,Math.round(W/2+(xx-cam.x)*cam.zoom),Math.round(H/2+(224-king.height*2-cam.y)*cam.zoom),Math.max(1,Math.round(2*cam.zoom)),Math.round(king.height*2*cam.zoom));
      }
    }
    if(f.staged.includes('pel'))drawPerson(pel,279,239,1.1);
    if(f.staged.includes('llama'))drawPerson(llama,321,f.mode==='town'?239:209,1.65);
    if(f.castRow&&['roll_call','the_speakers','the_ones_nobody_came_for'].includes(f.beat.id)){
      const actor=casts.get(f.castRow.id||f.castRow.name);
      if(actor){rect(ctx,14,16,68,71,'#0d1522');rect(ctx,15,17,66,1,'#be9470');ctx.drawImage(actor.portrait,24,24,48,48);ctx.font='7px monospace';ctx.fillStyle='#e1c7a8';ctx.fillText(String(f.castRow.name||'').slice(0,24),90,42);}
    }
    if(!opts.reducedMotion&&!f.frozen&&(f.fx.includes('dust')||f.fx.includes('wind_from_below')))for(let i=0;i<22;i++){
      const wind=f.fx.includes('wind_from_below')?15:2;
      const x=frac(i*.618+t*.004)*W,y=frac(i*.381-t*wind/270)*H;
      rect(ctx,x,y,i%6===0?2:1,1,i%3?'#8e7663':'#c6a37c');
    }
    if(f.mode==='black')rect(ctx,0,0,W,H,'#080d16');
    if(f.frozen){
      // Cache the complete held composition once, including the real cast. The
      // sunglasses are the sole moving cel over it. No frame-by-frame readback.
      if(!heldReady){tintFour(stage,held);heldReady=true;}
      ctx.drawImage(held,0,0);
      if(f.sunglasses){
        const drop=opts.reducedMotion?0:(1-f.sunglasses)*24;
        project(sunglasses,heroLeft+15,heroTop+9-drop,12,4);
        if(f.staged.includes('llama'))project(sunglasses,306,187,12,4);
      }
    } else {
      if(f.paletteMix&&heldReady){ctx.globalAlpha=f.paletteMix;ctx.drawImage(held,0,0);ctx.globalAlpha=1;}
      // Gallery scrubbing backwards must rebuild the next freeze, not reuse an
      // unrelated previously sampled tableau.
      if(elapsedMs<num(scene.freeze_at_ms))heldReady=false;
    }
    // Preserve composition: artwork is contained, never stretched or cropped by
    // a tall browser. The surrounding mattes belong to this cinematic surface.
    rect(out,0,0,width,height,'#080d16');
    const fit=Math.min(width/W,height/H),dw=Math.max(1,Math.floor(W*fit)),dh=Math.max(1,Math.floor(H*fit));
    out.imageSmoothingEnabled=false;out.drawImage(stage,Math.floor((width-dw)/2),Math.floor((height-dh)/2),dw,dh);
    return f;
  }
  const sunglasses=gridSprite(['.ooooo..ooooo.','ooooooo.oooooo','.ooooo..ooooo.','..ooo....ooo..'],{o:'#0a0a0c'},14,4);
  return {draw,dispose(){disposed=true;casts.clear();},size:CINEMA_SIZE};
}

/** Title plate uses the same landscape and lighting, with a quiet central field
 * for the logo and menu. Its own clock has no relation to finale bookkeeping. */
export function createTitleArt(){
  const back=vista(false),front=canvas();foreground(front.getContext('2d'));
  const hero=combatFrame('ready',0,{class_id:'analyst'});
  return {draw(ctx,w,h,time=0,reducedMotion=false){
    const t=reducedMotion?0:time,scale=Math.max(w/W,h/H),dw=W*scale,dh=H*scale,ox=(w-dw)/2,oy=(h-dh)/2;
    ctx.imageSmoothingEnabled=false;ctx.drawImage(back,ox,oy,dw,dh);
    // Very slow clouds, each a translucent painted band instead of particle fog.
    for(let i=0;i<5;i++){const x=ox+((i*111-t*1.2+W)%W)*scale;rect(ctx,x,oy+(61+i*20)*scale,48*scale,scale,'#81707b30');}
    ctx.drawImage(front,ox,oy,dw,dh);
    ctx.drawImage(hero,ox+53*scale,oy+186*scale,40*scale,48*scale);
    // Keep the center dark enough for a real title treatment and choices.
    const veil=ctx.createLinearGradient(0,h*.38,0,h);veil.addColorStop(0,'#080d1600');veil.addColorStop(.45,'#080d168c');veil.addColorStop(1,'#080d16e8');ctx.fillStyle=veil;ctx.fillRect(0,h*.38,w,h*.62);
  }};
}
