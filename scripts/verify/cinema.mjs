/* Cinematic contract checks use the real Python script and real raster pixels.
 * They do not start a game, write a save, or call an HTTP route. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { installRaster, frameHash, pixelDiff, colourCount } from './raster.mjs';
import { installStub, newCtx, enterLoop, exitLoop, REC } from './stub.mjs';
const root=fileURLToPath(new URL('../../',import.meta.url));
const fixture=spawnSync('python3',['-c',`
import json
from gauntlet import finale, ending
scenes=[finale.cutscene(freed=finale._fake_freed(n), released=finale._fake_released(r), total_captives=28, exam_report=finale._fake_report('READY'), names=['window','counter']) for n,r in [(0,0),(4,6),(28,0)]]
scenes.append(ending.rematch(exam_report=ending._fake_report('NOT_READY'), still_held=28, carried=0))
print(json.dumps(scenes))
`],{cwd:root,encoding:'utf8'});
assert.equal(fixture.status,0,fixture.stderr);
const scenes=JSON.parse(fixture.stdout);
installRaster();
const {createCinema,cinematicFrame,createTitleArt,CAMERA_MOVES}=await import('../../web/js/cinema.js');
function target(){const c=document.createElement('canvas');c.width=480;c.height=270;return c;}
const shot=(c)=>c.getContext('2d').getImageData(0,0,c.width,c.height);
const at=(scene,id,fraction=.5)=>{const b=scene.beats.find(b=>b.id===id);assert(b,id);return b.at_ms+b.duration_ms*fraction;};
const scene=scenes[1];
assert.deepEqual(CAMERA_MOVES,scene.camera_moves);
assert.equal(cinematicFrame(scene,at(scene,'the_prompt_stays')).mode,'black');
assert.equal(cinematicFrame(scene,at(scene,'the_one_you_teach')).mode,'town');
assert.equal(cinematicFrame(scene,at(scene,'the_world_is_not_restored')).mode,'world');
assert.equal(cinematicFrame(scenes[0],at(scenes[0],'forming_up')).freed.length,0,'No invented rescued crowd');
assert.equal(cinematicFrame(scenes[0],at(scenes[0],'forming_up')).released.length,0,'No invented released crowd');
const longRoll=scenes[2].beats.find(b=>b.id==='roll_call');
assert.equal(cinematicFrame(scenes[2],longRoll.at_ms+899).castIndex,0);
assert.equal(cinematicFrame(scenes[2],longRoll.at_ms+901).castIndex,1);
assert.equal(cinematicFrame(scenes[2],longRoll.at_ms+12*900+261).castIndex,13);
const formation=cinematicFrame(scene,at(scene,'forming_up'));
assert.equal(formation.freed.length,4);assert.equal(formation.released.length,6);
assert(!formation.freed.some(a=>formation.released.some(b=>a.id===b.id)),'The two casts remain separate');
const a=cinematicFrame(scene,at(scene,'the_green_shelf',.1)),b=cinematicFrame(scene,at(scene,'the_green_shelf',.9));
assert(b.camera.zoom>a.camera.zoom,'Push-in reaches its subject');
const left=cinematicFrame(scene,at(scene,'roll_call',.1)),right=cinematicFrame(scene,at(scene,'roll_call',.9));
assert(right.camera.x<left.camera.x,'Track-left moves left');
const crane0=cinematicFrame(scene,at(scene,'forming_up',0)),crane1=cinematicFrame(scene,at(scene,'forming_up',1-1e-6));
assert(crane1.camera.y<crane0.camera.y,'Crane rises');
assert(crane1.camera.zoom<crane0.camera.zoom,'Crane honors roster pullback');
const breaking0=cinematicFrame(scene,at(scene,'the_king_breaks',.1)),breaking1=cinematicFrame(scene,at(scene,'the_king_breaks',.9));
assert(breaking1.kingOpacity<breaking0.kingOpacity,'King dissolves without a collapse animation');
assert.equal(cinematicFrame(scene,at(scene,'what_he_could_not_do')).kingOpacity,0,'Hold shows the King’s absence');
assert.equal(cinematicFrame(scene,at(scene,'the_index_fails',.5)).indexLight,0,'All index spheres go dark within one second');
const frozen0=cinematicFrame(scene,at(scene,'freeze',.1)),frozen1=cinematicFrame(scene,at(scene,'the_readiness_line',.9));
assert.equal(frozen0.artMs,frozen1.artMs,'Every freeze beat shares one art clock');
assert.deepEqual(frozen0.camera,frozen1.camera,'The held camera cannot creep');
assert.deepEqual(frozen0.staged,frozen1.staged,'Cut-in speech cannot delete the held formation');
assert.equal(cinematicFrame(scene,at(scene,'unfreeze',.9)).paletteMix,0,'Full palette returns after 1200ms');
assert.deepEqual(cinematicFrame(scene,at(scene,'the_green_shelf',.1),{reducedMotion:true}).camera,cinematicFrame(scene,at(scene,'the_green_shelf',.9),{reducedMotion:true}).camera,'Reduced motion holds a settled camera');

// A full cast must open to a full painted frame, never become a small plate
// surrounded by black. This also covers the settled camera inherited by FREEZE.
for(const s of scenes)for(const beat of s.beats)for(const fraction of [0,.5,.999]){
  const frame=cinematicFrame(s,beat.at_ms+beat.duration_ms*fraction);
  if(frame.mode==='black')continue;
  const c=frame.camera;
  assert(c.zoom>=1,`${beat.id}: the painted plate cannot shrink below its viewport`);
  assert(240-c.x*c.zoom<=1e-7 && 240+(480-c.x)*c.zoom>=480-1e-7,`${beat.id}: plate covers full width`);
  assert(135-c.y*c.zoom<=1e-7 && 135+(270-c.y)*c.zoom>=270-1e-7,`${beat.id}: plate covers full height`);
}
const fullCast=scenes[2],fullFrozen=cinematicFrame(fullCast,at(fullCast,'freeze'));
assert.equal(fullFrozen.freed.length,28);
assert.equal(fullFrozen.camera.zoom,1,'The full roster retains native sprite scale');
assert.deepEqual(fullFrozen.camera,{x:240,y:135,zoom:1});
const fullFilm=createCinema(fullCast),fullCanvas=target();
fullFilm.draw(fullCanvas.getContext('2d'),480,270,at(fullCast,'freeze'));
const fullPixels=shot(fullCanvas).data;
let paintedEdges=0;
for(let y=0;y<270;y++)for(const x of [12,24,36,444,456,468]){
  const i=(y*480+x)*4;
  if(fullPixels[i]!==10||fullPixels[i+1]!==10||fullPixels[i+2]!==12)paintedEdges++;
}
assert(paintedEdges>200,'Painted architecture remains visible at both sides of the full-cast freeze');
fullFilm.dispose();

const film=createCinema(scene),cv=target();
film.draw(cv.getContext('2d'),480,270,at(scene,'index_floor'));
const frames=new Map();
for(const id of ['the_green_shelf','the_offer_again','the_king_breaks','forming_up','freeze','the_sunglasses','unfreeze','the_world_is_not_restored','the_one_you_teach','the_prompt_stays']){
  film.draw(cv.getContext('2d'),480,270,at(scene,id));frames.set(id,frameHash(cv));
}
assert(new Set(frames.values()).size>=9,'Different scenes change the rendered composition');
film.draw(cv.getContext('2d'),480,270,at(scene,'freeze',.1));
assert(colourCount(cv)<=4,'The complete freeze composition uses four colors');
const freezePixels=shot(cv);
film.draw(cv.getContext('2d'),480,270,at(scene,'freeze',.9));
assert.equal(pixelDiff(freezePixels,shot(cv)),0,'Frozen pixels cannot move');
film.draw(cv.getContext('2d'),480,270,at(scene,'the_sunglasses',.8));const held=shot(cv);
film.draw(cv.getContext('2d'),480,270,at(scene,'the_readiness_line',.9));
assert.equal(pixelDiff(held,shot(cv)),0,'After sunglasses settle, the whole held tableau stays fixed');
const replay=createCinema(scene);replay.draw(cv.getContext('2d'),480,270,at(scene,'the_one_you_teach'));const replayHash=frameHash(cv);
film.draw(cv.getContext('2d'),480,270,at(scene,'the_one_you_teach'));assert.equal(frameHash(cv),replayHash,'Same script and time are deterministic');
const reduced=createCinema(scene,{reducedMotion:true});reduced.draw(cv.getContext('2d'),480,270,at(scene,'index_floor',.1));const still=shot(cv);
reduced.draw(cv.getContext('2d'),480,270,at(scene,'index_floor',.9));assert.equal(pixelDiff(still,shot(cv)),0,'Reduced motion stops ambient animation');
film.dispose();const disposed=frameHash(cv);film.draw(cv.getContext('2d'),480,270,at(scene,'freeze'));assert.equal(frameHash(cv),disposed,'Disposed renderer cannot paint');

// Instrumented canvas catches nonfinite coordinates and late image allocation.
installStub();
const makeElement=document.createElement.bind(document);
const checkText=(text,x,y)=>{assert.equal(typeof text,'string');assert(Number.isFinite(x)&&Number.isFinite(y),'Text coordinates must be finite');REC.ctxCalls++;};
document.createElement=(tag)=>{const node=makeElement(tag);if(tag==='canvas')node.getContext('2d').fillText=checkText;return node;};
const draw=createCinema(scene),ctx=newCtx(960,540),title=createTitleArt();
// stub.mjs currently treats fillText's text argument as a numeric coordinate.
// Validate the actual coordinate positions here instead of suppressing errors.
ctx.fillText=checkText;
let count=0;
for(const s of scenes){
  const renderer=createCinema(s);
  for(const beat of s.beats){
    for(const fraction of [0,.1,.5,.999]){
      enterLoop(beat.id);renderer.draw(ctx,960,540,beat.at_ms+beat.duration_ms*fraction);exitLoop();count++;
    }
  }
  renderer.dispose();
}
for(const [w,h] of [[480,270],[960,540],[1280,800],[390,844]]){enterLoop('title');title.draw(ctx,w,h,4,true);exitLoop();}
assert.equal(REC.nonFinite.length,0,JSON.stringify(REC.nonFinite.slice(0,3)));
assert.equal(REC.nullImage.length,0,JSON.stringify(REC.nullImage.slice(0,3)));
assert.equal(REC.badPaint.length,0,JSON.stringify(REC.badPaint.slice(0,3)));
assert.equal(REC.allocInLoop.length,0,JSON.stringify(REC.allocInLoop.slice(0,3)));
draw.dispose();
console.log(JSON.stringify({ok:true,sampledFrames:count,scenes:scenes.length,cameraMoves:CAMERA_MOVES.length,freeze:'four colors; fixed pixels; sunglasses sole motion',cast:'0, 4+6, 28; no invented rows',fullCastFreeze:{zoom:fullFrozen.camera.zoom,paintedEdgeSamples:paintedEdges},perFrameCanvasAllocations:REC.allocInLoop.length},null,2));
