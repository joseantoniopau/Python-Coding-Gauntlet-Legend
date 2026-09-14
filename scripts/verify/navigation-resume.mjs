/* Execute the actual main.js interaction bodies against isolated host nodes.
 * The browser pass checks layout; this checks delayed-response ownership.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const main = fs.readFileSync(new URL('../../web/js/main.js', import.meta.url), 'utf8');
function between(start, end) {
  const from = main.indexOf(start);
  assert(from >= 0, `Missing main.js boundary: ${start}`);
  const to = main.indexOf(end, from + start.length);
  assert(to > from, `Missing main.js boundary: ${end}`);
  return main.slice(from, to);
}
const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
};
const nextTurn = () => new Promise(setImmediate);

// Keep the production eligibility predicate, click handler and insertion call
// together: a button created while detached must still reach the action list.
const resumeBody = between('  const active=G.state?.active_encounter;', '  const btnBoss =');
const renderResume = new Function('G', 'el', 'api', 'actions', 'enterBattle', 'toast', resumeBody);
function resumeFixture(overrides = {}) {
  const request = deferred(), requested = [], entered = [], notices = [], nodes = [];
  const state = {active_encounter: {problem_id:'practice-example', mode:'adventure', dungeon_room:-1},
    run_open:false, dungeon:null, incantation:null, boss_fight:null, ...overrides};
  const actions = {appendChild(node) { nodes.push(node); node.isConnected = true; }};
  renderResume({state}, (tag, cls, label) => ({tag, className:cls, label, isConnected:false, disabled:false}),
    {resumeEncounter: id => {requested.push(id); return request.promise;}}, actions,
    payload => entered.push(payload), (...args) => notices.push(args));
  return {button:nodes[0], nodes, request, requested, entered, notices};
}

for (const overrides of [
  {active_encounter:null},
  {active_encounter:{mode:'adventure', dungeon_room:0}},
  {active_encounter:{mode:'adventure', dungeon_room:2}},
  {active_encounter:{mode:'interview', dungeon_room:-1}},
  {active_encounter:{mode:'adventure', dungeon_room:-1, repo_id:'repo'}},
  {active_encounter:{mode:'adventure', dungeon_room:-1, boss_id:'boss'}},
  {active_encounter:{mode:'adventure', dungeon_room:-1, practice_id:'plan'}},
  {run_open:true}, {dungeon:{id:'run'}}, {incantation:{id:'run'}}, {boss_fight:{id:'run'}},
]) assert.equal(resumeFixture(overrides).nodes.length, 0, JSON.stringify(overrides));

const ordinary = resumeFixture();
assert.equal(ordinary.nodes.length, 1, 'ordinary dungeon_room=-1 gets a connected Resume button');
assert(ordinary.button.isConnected);
const payload = {problem:{id:'practice-example'}, encounter:{started_at:123}, reason:'ENCOUNTER_RESUME'};
const pending = ordinary.button.onclick();
assert(ordinary.button.disabled, 'Resume disables while the request is pending');
assert.deepEqual(ordinary.requested, ['practice-example']);
ordinary.request.resolve(payload); await pending;
assert.deepEqual(ordinary.entered, [payload]);

const away = resumeFixture();
const late = away.button.onclick();
away.button.isConnected = false; away.request.resolve(payload); await late;
assert.equal(away.entered.length, 0, 'a detached world button cannot reopen battle');
assert.equal(away.notices.length, 0);

const refused = resumeFixture();
const refusal = refused.button.onclick();
refused.request.resolve({error:'encounter changed', message:'That link is no longer current.'}); await refusal;
assert.equal(refused.entered.length, 0);
assert.equal(refused.button.disabled, false);
assert.match(refused.notices[0][1], /no longer current/);

const appearanceBody = between('async function paintAppearance(){', '\nfunction paintCharacter()');
const makeAppearance = new Function('$', 'api', 'uikit', 'refresh', 'paintCharacter', `${appearanceBody}\nreturn paintAppearance;`);
async function appearanceFixture() {
  const select = deferred(), refresh = deferred();
  const choice = {value:'copper', disabled:false}, status = {};
  const host = {isConnected:true, querySelector:selector => selector === 'select' ? choice : status};
  let refreshes = 0, paints = 0;
  const paint = makeAppearance(() => host, {
    appearance:async () => ({selected:'equipment', options:[]}),
    appearanceSelect:() => select.promise,
  }, {esc:value => value}, () => {refreshes++; return refresh.promise;}, () => {paints++;});
  await paint();
  return {host, choice, select, refresh, counts:() => ({refreshes, paints})};
}
const colors = await appearanceFixture();
const chosen = colors.choice.onchange();
assert(colors.choice.disabled);
colors.select.resolve({selected:'copper'}); await nextTurn();
colors.refresh.resolve(); await chosen;
assert.deepEqual(colors.counts(), {refreshes:1, paints:1}, 'connected appearance selection refreshes its preview');

const leftEarly = await appearanceFixture();
const early = leftEarly.choice.onchange();
leftEarly.host.isConnected = false; leftEarly.select.resolve({selected:'copper'}); await early;
assert.deepEqual(leftEarly.counts(), {refreshes:0, paints:0}, 'leaving while saving cannot reopen Gear');

const leftDuringRefresh = await appearanceFixture();
const during = leftDuringRefresh.choice.onchange();
leftDuringRefresh.select.resolve({selected:'copper'}); await nextTurn();
leftDuringRefresh.host.isConnected = false; leftDuringRefresh.refresh.resolve(); await during;
assert.deepEqual(leftDuringRefresh.counts(), {refreshes:1, paints:0}, 'leaving during refresh cannot reopen Gear');

console.log('PASS — actual Resume eligibility/insertion, identity, pending/refusal handling, late navigation, and keepsake save/refresh ownership');
