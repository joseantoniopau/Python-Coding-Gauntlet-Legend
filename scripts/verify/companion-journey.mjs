/* Existing catalogue facts, UI escaping and asynchronous navigation ownership.
 * No browser, HTTP endpoint or save database is used. */
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {installStub} from './stub.mjs';
installStub();
const actual = JSON.parse(execFileSync('python3',['-c',`
import json
from gauntlet import pets, world
pet = next(p for p in pets.PETS if p.id != pets.STARTER_ID and any(r['skill'] == p.skill for r in world.REGIONS))
region = next(r for r in world.REGIONS if r['skill'] == pet.skill)
s = pets.new_state()
s.update(found=[pet.id, pets.STARTER_ID], active=[pet.id], bond={pet.id:45, pets.STARTER_ID:12}, fallen=[pets.STARTER_ID])
print(json.dumps({'payload':{'pets':pets.catalogue(s),'active':pet.id,'fallen':[pets.STARTER_ID],'keepsake':pets.KEEPSAKE},
 'state':{'run_open':False,'active_encounter':None,'player':{'region':region['id']},'regions':[dict(r,unlocked=True) for r in world.REGIONS]},'active':pet.id}))
`],{cwd:new URL('../../',import.meta.url),encoding:'utf8'}));
const {companionJourney,companionJourneyHTML,paintCompanions,configure,leave} = await import('../../web/js/partyui.js');
const {api}=await import('../../web/js/api.js');
let v=companionJourney(actual.payload,actual.state);
assert.equal(v.pet.id,actual.active); assert.equal(v.activity.kind,'practice');
assert(v.facts.some(f=>f.label==='Bond kept' && f.value.endsWith('45 bond')));
assert.equal(v.quote,v.pet.line);assert(v.keepsake);
assert.equal(v.activity.region,actual.state.player.region);
assert(companionJourneyHTML(v).includes('Shared journey'));
assert.equal(companionJourney(actual.payload,{...actual.state,run_open:true}).activity.kind,'none');
assert.equal(companionJourney(actual.payload,{...actual.state,run_open:undefined}).activity.kind,'none','Unknown measurement state stays closed');
assert.equal(companionJourney(actual.payload,{...actual.state,active_encounter:{problem_id:'open'}}).activity.kind,'resume');
const away={...actual.state,player:{region:'not_this_skill'}};
assert.equal(companionJourney(actual.payload,away).activity.kind,'map');
assert(companionJourney(actual.payload,away).activity.text.includes(actual.state.regions.find(r=>r.id===v.activity.region).name));
const fainted=structuredClone(actual.payload);fainted.pets.find(p=>p.id===actual.active).fainted=true;
assert.equal(companionJourney(fainted,actual.state).activity.kind,'town');
const resting=structuredClone(actual.payload);resting.pets.forEach(p=>p.active=false);
assert.equal(companionJourney(resting,actual.state,{},actual.active).activity.kind,'roster');
const remembered=companionJourney(actual.payload,actual.state,{},actual.payload.fallen[0]);
assert.equal(remembered.activity.kind,'journal');assert(remembered.facts.some(f=>f.value==='Remembered in the codex'));
const empty=companionJourney({pets:[],keepsake:'not owned'},actual.state);
assert.equal(empty.pet,null);assert.equal(empty.keepsake,'');assert(!companionJourneyHTML(empty).includes('not owned'));
assert(companionJourneyHTML(empty).includes('when you meet a companion'));
const roads={here:{id:'here'},escorts:[
 {id:'here',name:'Fixture here',state:'WALKING',state_label:'Walking with you',zone:{name:'Example zone'},held:false,drop:{name:'Not held'}},
 {id:'elsewhere',state:'WALKING'},
 {id:'taken',name:'Fixture captive',state:'TAKEN',state_label:'Taken',held:false,drop:{name:'Not held'}},
 {id:'freed',name:'Fixture rescued',state:'FREED',state_label:'Home',home:'Example home',held:true,drop:{name:'Recorded gift'}},
 {id:'unknown',state:'invented'}]};
v=companionJourney(actual.payload,actual.state,roads);
assert.deepEqual(v.roads.map(r=>r.id),['here','taken','freed']);
assert.equal(v.roads[0].keepsake,'');assert.equal(v.roads[2].keepsake,'Recorded gift');
assert(!companionJourneyHTML(v).includes('Not held'));
const unsafe=structuredClone(v);unsafe.pet.name='<img src=x onerror=alert(1)>';unsafe.quote='<script>bad()</script>';
const html=companionJourneyHTML(unsafe);assert(!html.includes('<img'));assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;'));

// Navigation while these reads are pending cannot reopen the old roster.
let complete;const pending=new Promise(resolve=>complete=resolve);let paints=0;
api.pets=()=>pending;api.petDiscovery=async()=>({progress:[]});api.worldMap=async()=>({escorts:roads});
document.getElementById=()=>({});document.querySelectorAll=()=>[];
configure({panel:()=>paints++,state:()=>actual.state,toast:()=>{}});
const painting=paintCompanions();leave();complete(actual.payload);await painting;
assert.equal(paints,0,'A departed roster does not overwrite a newer screen');
console.log('companion journey: actual bond/skill, measured and encounter gates, faint/rest/loss, truthful escort possession, escaping, async teardown verified');
