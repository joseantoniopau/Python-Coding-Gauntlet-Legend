/* Execute the shipped field and travel consumers with authored Python payloads.
 * No browser, shared server, save file or game renderer is started here. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const root = new URL('../../', import.meta.url);
const read = name => fs.readFileSync(new URL(name, root), 'utf8');
const main = read('web/js/main.js'), field = read('web/js/overworld.js');
const world = read('web/js/worldui.js');
function between(source, start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, `Production boundary missing: ${start}`);
  return source.slice(a, b);
}
const payload = JSON.parse(execFileSync('python3', ['-c', `
import json
from gauntlet import zonecompanions as z
s={'world':{'routes_walked':[z.SLATE_ROUTE]},'inventory':[]}
events=z.advance(s)['events']
print(json.dumps({'ok':True,'region':'fields_of_syntax',
                 'escort':z.escort_in(s,'fields_of_syntax'),'escort_events':events}))
`], {cwd:root, encoding:'utf8'}));
assert.equal(payload.escort_events[0].drop.id, 'the_slate');
const afterTurn = () => new Promise(setImmediate);
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; };

function fixture() {
  const gates = new Set(), said = [], snapshots = [], scheduled = [], moves = [], captions = [];
  let region = 'python_village', paints = 0;
  const G = {screen:'world', _fieldEpoch:1, state:{run_open:false, player:{created_at:123}},
    world:{mentors:{byte:{name:'BYTE'}}}, overworld:{region:{id:region},
      setEscort(row) { snapshots.push(row); }}};
  const node = id => ({classList:{contains: c => gates.has(`${id}:${c}`)}, remove() {gates.delete(id);}});
  const document = {body:node('body')};
  const api = {move:async (...args) => {moves.push(args); return payload;}};
  const source = between(main, 'const escortNotices = [];', '/* Every road leaving');
  const consumer = new Function('G','document','$','uikit','currentRegion','paintWorldSide',
    'roadsFromHere','say','api','clearTimeout','setTimeout', `${source}
    return {consumeEscortResponse, drainEscortNotices, showEscortCaption, saveFieldMove,
            escortPlayer, notices:escortNotices};`)(G, document, node, {faceFor:()=>'scholar'},
      () => ({id:region, mentor:'byte', physical:'Buildings rebuild as fluency returns.'}),
      () => {paints++; captions.push(G.escortCaption);}, () => [
        {name:'The Waking Road',to_name:'Fields of Syntax',passable:true,danger:1},
        {name:'The Locked Road',to_name:'The Caverns',passable:false,
          requirement:'Find the key',percent:25}], (...args) => {said.push(args); gates.add('#dialogue:show');},
      api, () => {}, callback => {scheduled.push(callback); return scheduled.length;});
  const setRegion = id => {region=id; G.overworld.region={id};};
  return {G, gates, said, snapshots, moves, scheduled, captions, api, consumer, setRegion};
}

// Exactly one speech from one original response, despite snapshot adoption
// after refresh; it waits behind dialogue, modals and the map screen.
{
  const f=fixture(), c=f.consumer;
  c.consumeEscortResponse(payload,payload.region,-1);
  assert.equal(c.notices.length,1);
  f.gates.add('#dialogue:show'); assert.equal(c.drainEscortNotices(),false);
  f.gates.clear();f.G.screen='panel'; assert.equal(c.drainEscortNotices(),false);
  f.G.screen='world';f.gates.add('#modal-bg:show');assert.equal(c.drainEscortNotices(),false);
  f.gates.clear();c.consumeEscortResponse(payload,payload.region);
  assert.equal(c.notices.length,1);
  assert.equal(c.drainEscortNotices(),true);
  assert.equal(f.said[0][0],payload.escort.name);
  assert(f.said[0][1].includes(payload.escort_events[0].note));
  assert(f.said[0][1].includes(payload.escort_events[0].drop.mechanic));
  f.gates.clear();assert.equal(c.drainEscortNotices(),false);
  assert.equal(f.said.length,1);
}
// Refusals/unknown measured state never enable guidance or queue a gift.
for (const run_open of [true,undefined]) {
  const f=fixture();f.G.state.run_open=run_open;
  f.consumer.consumeEscortResponse(payload,'python_village');
  assert.equal(f.consumer.notices.length,0);assert.equal(f.snapshots.length,0);
  assert.equal(f.consumer.showEscortCaption(payload.escort,{kind:'building'}),false);
}
{
  const f=fixture();f.consumer.consumeEscortResponse({...payload,error:'sealed'},'python_village');
  assert.equal(f.consumer.notices.length,0);
  f.consumer.consumeEscortResponse(payload,'python_village',0);
  assert.equal(f.snapshots.length,0,'Old region generation cannot install an escort');
  f.G.state.player.created_at=456;
  assert.equal(f.consumer.drainEscortNotices(),false,'New save cannot inherit pending speech');
}
// Actual field callback uses server place/route facts, with no assigned shop role.
{
  const f=fixture();
  assert(f.consumer.showEscortCaption(payload.escort,{kind:'building'}));
  assert.match(f.captions.at(-1).lines[0],/BYTE.*SPACE/);
  assert.doesNotMatch(f.captions.at(-1).lines.join(' '),/mender|smith/);
  assert(f.consumer.showEscortCaption(payload.escort,{kind:'exit'}));
  assert.match(f.captions.at(-1).lines.join(' '),/Fields of Syntax.*Danger 1/);
  assert.match(f.captions.at(-1).lines.join(' '),/Find the key.*25%/);
}
// Exercise actual Overworld methods. Standing at a solid facade's reachable
// doorstep invokes the caption; the callback can refuse without consuming it.
{
  const methods = between(field,'  setEscort(row) {','  /* ------------------------------------------------------------- companion');
  const C = new Function(`return class {${methods}}`)();
  const o=new C();let calls=0,allow=false;
  Object.assign(o,{player:{x:5,y:9},_escortCaptions:new Set(),
    markers:[{kind:'building',x:5,y:7,id:'home'},{kind:'exit',x:12,y:9,id:'road'}],
    stateSource:()=>({run_open:false}),onEscortCaption:()=>{calls++;return allow;}});
  o.setEscort(payload.escort);assert.equal(calls,1);assert.equal(o._escortCaptions.size,0);
  allow=true;o._offerEscortCaption();o._offerEscortCaption();assert.equal(calls,2);
  o.player.x=12;o._offerEscortCaption();assert.equal(calls,3);
  o.setEscort({});o._escortCaptions.clear();o._offerEscortCaption();assert.equal(calls,3);
  o.stateSource=()=>({run_open:true});o.setEscort(payload.escort);assert.equal(calls,3);
}
// Movement snapshots capture their region at scheduling time, not after travel.
{
  const f=fixture();f.consumer.saveFieldMove(3,4);
  f.G._fieldEpoch++;await f.scheduled.shift()();assert.equal(f.moves.length,0);
  f.consumer.saveFieldMove(5,6);await f.scheduled.shift()();
  assert.deepEqual(f.moves,[['python_village',5,6]]);assert.equal(f.said.length,1);
}
{
  const f=fixture(), reply=deferred();f.api.move=()=>reply.promise;
  f.consumer.saveFieldMove(5,6);const pending=f.scheduled.shift()();
  f.G._fieldEpoch++;f.setRegion('array_caverns');f.G.screen='battle';
  reply.resolve(payload);await pending;
  assert.equal(f.snapshots.length,0);assert.equal(f.said.length,0);
}
// Execute the side-panel road consumer, including refresh and stale navigation.
const roadSource=between(main,'async function takeRoad(road) {','/* Icons for state.todo');
for (const late of [false,true]) {
  const f=fixture(), reply=deferred(), loaded=[];
  const travel=new Function('G','api','toast','sealedTitle','audio','refresh','closeModal',
    'loadRegion','returnToWorld','offerLessons','escortPlayer','consumeEscortResponse','clearTimeout',
    `${roadSource};return takeRoad;`)(f.G,{travel:()=>reply.promise},()=>{},()=>'',{sfx:()=>{}},
      async()=>{},()=>{},id=>{loaded.push(id);f.setRegion(id);f.G._fieldEpoch++;},
      ()=>{f.G.screen='world';f.consumer.drainEscortNotices();},()=>{},f.consumer.escortPlayer,
      f.consumer.consumeEscortResponse,()=>{});
  const task=travel({id:'rt_waking_road'});
  if(late)f.G.screen='battle';reply.resolve(payload);await task;
  assert.equal(loaded.length,late?0:1);assert.equal(f.said.length,late?0:1);
}
// Map travel must forward the entire original response even if its host was
// destroyed while waiting. A retired map never installs its region afterward.
{
  const method=between(world,'  async travel(routeId) {','  /** Walk a whole chain');
  for(const late of [false,true]) {
    const reply=deferred(), notices=[], regions=[];
    const C=new Function('api',`return class {${method}}`)({travel:()=>reply.promise});
    const ui=new C();Object.assign(ui,{host:{isConnected:true},queue:[],hooks:{
      onTravelResponse:r=>notices.push(r),onRegion:(id,r)=>regions.push([id,r])},
      refused:()=>false,sfx:()=>{},steps:()=>{},toast:()=>{}});
    const task=ui.travel('rt_waking_road');if(late)ui.host=null;
    reply.resolve(payload);await task;
    assert.equal(notices[0],payload);assert.equal(regions.length,late?0:1);
    if(!late)assert.equal(regions[0][1],payload);
  }
}
// The real offer/queue code rejects battle guidance on the world, and passes a
// live validity predicate through the read-before-ack tutor API.
{
  const code=between(main,'const lessonQueue = [];','function configureTutor()');
  const calls=[], G={screen:'world',tab:'trials',state:{run_open:false}};
  const tutor={beat:async(id,opts)=>{calls.push({id,valid:opts.valid});}};
  const node={hidden:true,classList:{contains:()=>false}};
  const offers=new Function('G','$','tutor',`${code};return {offerLessons,nextLesson};`)(G,()=>node,tutor);
  offers.offerLessons('the_trials','the_tabs');await afterTurn();assert.equal(calls.length,0);
  G.screen='battle';offers.offerLessons('the_trials');await afterTurn();
  assert.equal(calls[0].valid(),true);G.screen='world';assert.equal(calls[0].valid(),false);
  G.screen='battle';G.tab='approach';assert.equal(calls[0].valid(),false);
  G.tab='trials';G.mcq={};assert.equal(calls[0].valid(),false);
}
assert(main.includes('G.overworld.onEscortCaption = showEscortCaption;'));
assert(main.includes('G.overworld.onMove = saveFieldMove;'));
assert(main.includes('consumeEscortResponse(view, regionId, epoch);'));
console.log('Escort handoffs: authored Slate payload, both travel paths, movement, field captions, measured/stale guards and tutorial context passed.');
