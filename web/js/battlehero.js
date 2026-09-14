/* Original combat cels. The field rig stays small for navigation; this rig
 * has room for a face, a bent knee and equipment attached to the moving hand.
 * Coordinates are source pixels. Feet land at y=47 in every standing pose. */
import { gridSprite, heroPalette, heroArmor, weaponArt } from './sprites.js';
import { heroEquipOpts } from './lootart.js';

export const BATTLE_HERO = Object.freeze({ width: 40, height: 48, footX: 18, footY: 47, scale: 2 });
export const COMBAT_POSES = Object.freeze(['ready', 'cast', 'strike', 'guard', 'hurt', 'victory']);
const cache = new Map();
const LIMIT = 256;

// A small integer painter keeps outlines and material planes on the same grid.
function cel() {
  const g = Array.from({ length: 48 }, () => Array(40).fill('.'));
  const dot = (x, y, c) => { if (g[y] && x >= 0 && x < 40) g[y][x] = c; };
  const rect = (x, y, w, h, c) => { for (let j=y;j<y+h;j++) for(let i=x;i<x+w;i++) dot(i,j,c); };
  const line = (x0, y0, x1, y1, c) => {
    let dx=Math.abs(x1-x0), sx=x0<x1?1:-1, dy=-Math.abs(y1-y0), sy=y0<y1?1:-1, e=dx+dy;
    for (;;) { dot(x0,y0,c); if(x0===x1&&y0===y1)break; const e2=2*e; if(e2>=dy){e+=dy;x0+=sx;} if(e2<=dx){e+=dx;y0+=sy;} }
  };
  const poly = (points, c, edge='o') => {
    for(let y=0;y<48;y++) {
      const cuts=[];
      for(let i=0,j=points.length-1;i<points.length;j=i++) {
        const [a,b]=points[i], [d,e]=points[j];
        if((b>y)!==(e>y)) cuts.push(a+(y-b)*(d-a)/(e-b));
      }
      cuts.sort((a,b)=>a-b);
      for(let i=0;i<cuts.length;i+=2) for(let x=Math.ceil(cuts[i]);x<=Math.floor(cuts[i+1]);x++)dot(x,y,c);
    }
    if(edge) for(let i=0;i<points.length;i++)line(...points[i],...points[(i+1)%points.length],edge);
  };
  return { g, dot, rect, line, poly };
}

export function combatGrid(pose='ready', frame=0, look={}) {
  if(!COMBAT_POSES.includes(pose))pose='ready';
  const {g,dot,rect,line,poly}=cel(), armor=heroArmor(look);
  const beat=((frame%2)+2)%2;
  const lean=pose==='strike'?3:pose==='hurt'?-2:0;
  const lift=pose==='guard'?2:pose==='hurt'?1:0;
  const x=18+lean, y=7+lift;
  const cls=look.class_id || look.sprite || 'analyst';
  const back=pose==='strike'?1:4+beat;
  // Cape: long asymmetrical folds; the near arm never merges into its hem.
  poly([[x-4,y+10],[x-9,y+14],[back,38],[7,43],[x-2,39],[x+3,23]],'c');
  poly([[x-7,y+15],[back+2,37],[8,40],[x-2,28]],'v',null);
  line(x-8,y+17,back+2,36,'C'); line(8,39,x-4,29,'R');
  if(armor.legendary>=0) { line(back+1,38,7,42,'g'); line(7,42,x-2,38,'g'); }
  // Far leg then the weight-bearing near leg, each with a boot planted.
  poly([[x-4,29],[x+1,30],[x-1,38],[10,44],[7,44],[12,36]],'K');
  poly([[x,29],[x+6,29],[x+5,37],[x+8,44],[x+4,45],[x,37]],'v');
  line(x+2,32,x+3,37,'t');
  poly([[8,42],[12,42],[12,45],[15,46],[15,47],[5,47],[5,45]],'b');
  poly([[x+4,42],[x+8,42],[x+9,45],[x+12,46],[x+12,47],[x+2,47]],'b');
  line(6,46,12,46,'R'); line(x+3,46,x+10,46,'R');
  if(armor.boots>=1) { line(x+4,42,x+7,42,'m'); line(9,42,11,42,'m'); }
  // Cuirass and belt: chest lit from the upper left, ribs turn into shadow.
  poly([[x-5,y+11],[x+3,y+10],[x+8,y+16],[x+4,28],[x+6,31],[x-4,32],[x-7,24]],'t');
  poly([[x-4,y+13],[x+1,y+12],[x+4,y+17],[x+1,26],[x-4,26]],armor.chestplate>=0?'m':'T',null);
  poly([[x+4,y+16],[x+7,y+17],[x+3,28],[x,27]],armor.chestplate>=0?'A':'K',null);
  line(x-5,y+12,x-3,y+19,'R'); line(x-3,24,x+3,25,'g');
  if(look.body==='b') { poly([[x-4,25],[x+2,25],[x+6,32],[x+2,33],[x-5,31]],'t'); line(x-4,26,x-4,30,'R'); }
  rect(x-4,29,9,2,'K');rect(x,29,2,2,'g');
  // Neck and a three-quarter profile. The jaw is separate from the collar.
  poly([[x-1,y+6],[x+4,y+6],[x+3,y+12],[x,y+13],[x-2,y+10]],'S');
  poly([[x-4,y],[x+3,y-1],[x+6,y+2],[x+6,y+4],[x+8,y+5],[x+6,y+6],[x+5,y+9],[x+1,y+10],[x-3,y+7]],'s');
  rect(x+2,y+2,3,2,'N'); line(x+3,y+7,x+5,y+7,pose==='victory'?'N':'S');
  line(x+2,y+4,x+5,y+4,'o'); dot(x+5,y+4,'w');
  if(pose==='hurt') { line(x+2,y+3,x+5,y+5,'o'); }
  // Swept hair and crown silhouette; no enlarged field-sprite head.
  poly([[x-6,y+3],[x-5,y-2],[x-2,y-5],[x+4,y-4],[x+7,y],[x+2,y],[x,y+3],[x-2,y+2],[x-3,y+7],[x-5,y+6]],'h');
  line(x-3,y-3,x+2,y-3,'H'); line(x-5,y,x-4,y+3,'H');
  if(armor.helmet>=0) {
    poly([[x-6,y],[x-4,y-4],[x+3,y-5],[x+7,y],[x+1,y+1],[x-2,y+5],[x-5,y+5]],'m');
    line(x-4,y-3,x+2,y-4,'w'); line(x+1,y-3,x+4,y,'g');
    if(armor.helmet>=3) { line(x-4,y-4,x-6,y-7,'g'); line(x+3,y-5,x+5,y-7,'g'); }
  }
  // Class silhouette details stay behind the working hand.
  if(cls==='archivist') poly([[x-6,y+10],[x-8,y-1],[x-3,y-6],[x+4,y-5],[x+6,y-1],[x-1,y-2],[x-4,y+5]],'c');
  if(cls==='seer') { poly([[x-7,y+5],[x-7,y-3],[x-4,y-7],[x+1,y-7],[x-2,y-3],[x-4,y+3]],'g');line(x-6,y+5,x-6,y+13,'c'); }
  if(cls==='analyst') { poly([[x-8,29],[x-4,28],[x-3,35],[x-7,36]],'g');line(x-7,30,x-6,34,'w'); }
  if(cls==='warden') { poly([[x-8,y+11],[x-7,y+7],[x-3,y+7],[x+1,y+13],[x-3,y+17]],'m');line(x-7,y+8,x-4,y+8,'w'); }
  if(cls==='berserker') { line(x-6,y+12,x-10,y+8,'g');line(x-7,y+13,x-12,y+12,'w'); }
  if(cls==='artificer') { rect(x+1,y+2,6,3,'g');rect(x+2,y+3,2,1,'w'); }
  // Near arm is reposed from shoulder to elbow to wrist, not body translation.
  const hand=pose==='cast'?[32,17-beat]:pose==='strike'?[31,27]:pose==='victory'?[29,9]:pose==='guard'?[28,24]:pose==='hurt'?[24,29]:[28,31];
  const elbow=pose==='cast'?[26,24]:pose==='strike'?[28,25]:pose==='victory'?[27,17]:pose==='guard'?[25,28]:[24,28];
  poly([[x+4,y+12],[x+8,y+14],[elbow[0]+2,elbow[1]],[hand[0]+1,hand[1]-2],[hand[0]+3,hand[1]+1],[elbow[0],elbow[1]+3],[x+2,y+17]],armor.gauntlets>=0?'m':'t');
  poly([[hand[0]-1,hand[1]-2],[hand[0]+2,hand[1]-2],[hand[0]+3,hand[1]],[hand[0]+1,hand[1]+2],[hand[0]-1,hand[1]+1]],'s');
  line(x+4,y+12,x+7,y+14,'w'); dot(hand[0],hand[1]-1,'N');
  // Shield is strapped to the far forearm and rises in a guard pose.
  if(armor.shield>=0 || cls==='warden') {
    const sy=pose==='guard'?19:26, sx=pose==='guard'?27:x-6;
    poly([[sx-4,sy],[sx+3,sy-1],[sx+5,sy+3],[sx+3,sy+10],[sx,sy+13],[sx-4,sy+8]],'m');
    line(sx-3,sy+1,sx-3,sy+7,'w');line(sx,sy+1,sx,sy+10,'g');line(sx-2,sy+4,sx+3,sy+4,'g');
  }
  if(pose==='cast') {
    // Open fingers and two rune sparks. No spell effect is baked into the body.
    line(hand[0]+1,hand[1]-2,hand[0]+3,hand[1]-4,'N');dot(hand[0]+4,hand[1]-6,'g');
  } else {
    const w=look._weapon||{}, rung=Number.isFinite(w.rung)?w.rung:Math.max(0,['Rusted','Honed','Tempered','Runed','Legendary','Mythic'].indexOf(w.name||'Honed'));
    const blade=weaponArt(look.weapon||'sword',rung,{line:w.line,band:w.silhouette||w.band,half:w.half});
    // Blade grid is authored around grip (2,8). Quarter-turns preserve pixels.
    for(let j=0;j<blade.length;j++)for(let i=0;i<blade[j].length;i++) {
      const c=blade[j][i]; if(c==='.'||c===' ')continue;
      const u=i-2,v=j-8;
      if(pose==='strike')dot(hand[0]-v,hand[1]+u,c);
      else dot(hand[0]+u,hand[1]+v,c);
    }
    dot(hand[0],hand[1],'s');dot(hand[0]+1,hand[1],'N');
  }
  return g.map(row=>row.join(''));
}

export function combatFrame(pose='ready', frame=0, look={}, gear=null) {
  const opts=gear?heroEquipOpts(gear,look):look;
  const key=JSON.stringify([pose,frame&1,opts]);
  if(cache.has(key))return cache.get(key);
  const image=gridSprite(combatGrid(pose,frame,opts),heroPalette(opts),40,48);
  cache.set(key,image);
  while(cache.size>LIMIT)cache.delete(cache.keys().next().value);
  return image;
}

export function combatSet(look={},gear=null) {
  return Object.fromEntries(COMBAT_POSES.map(p=>[p,[0,1].map(f=>combatFrame(p,f,look,gear))]));
}
