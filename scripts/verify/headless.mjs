/* headless.mjs — drive the real client against the real server, with no browser.
 *
 *     GAUNTLET_DATA_DIR=$(mktemp -d) python3 run.py serve --port 8801 &
 *     node scripts/verify/headless.mjs 8801
 *
 * THE DATA DIR IS NOT OPTIONAL, and the env var above is the whole reason.
 * This harness DRIVES A REAL GAME: it walks the character, starts encounters,
 * and opens a 115-minute FINAL_EXAM which then seals the world layer behind
 * HTTP 409s. On a server started without GAUNTLET_DATA_DIR, the game it does
 * that to is the PLAYER'S OWN SAVE — which is exactly what happened once, from
 * the command this header used to recommend.
 *
 * So it asks /api/ping, which reports whether the server is on a throwaway
 * dir, and exits 2 if it is not. A verification harness must not be able to do
 * that to somebody's game, and "remember the env var" is not a mechanism.
 *
 * To run it against the real save anyway — there is no good reason, but it is
 * the operator's game — set GAUNTLET_ALLOW_LIVE_SAVE=1.
 *
 * Drive the real client headlessly against the real server.
 *
 * Not a mock: this loads web/js/api.js and the real art modules under the same
 * instrumented canvas stub the render harness uses, points `fetch` at the live
 * server, and walks the screens in the order main.js walks them — boot, town,
 * map, the boss list, a phase turn, the portal, the practical.
 *
 * What it reports is what RENDERED: pixels drawn, canvases allocated, and the
 * four failure classes a parse check cannot see (null draw sources, non-finite
 * coordinates, paints that resolve to undefined, allocation inside a loop).
 */
import fs from 'fs';
import { installStub, REC, newCtx, enterLoop, exitLoop, setWhere, snapshot } from './stub.mjs';
installStub();

const ROOT = new URL('../../web/js/', import.meta.url).href;
const PORT = process.argv[2] || '8801';
// The session token the server stamps into index.html. Fetched from the page
// rather than passed in, because that is where a browser gets it too.
const page = await (await fetch(`http://127.0.0.1:${PORT}/`)).text();
const TOKEN = (page.match(/__GAUNTLET_TOKEN__ *= *"([^"]*)"/) || [])[1] || '';
if (!TOKEN) {
  console.error(`no server on ${PORT}. run: `
    + `GAUNTLET_DATA_DIR=$(mktemp -d) python3 run.py serve --port ${PORT}`);
  process.exit(2);
}
const BASE = `http://127.0.0.1:${PORT}`;

// Refuse the player's save before touching it.
{
  let ping = null;
  try {
    ping = await (await fetch(`${BASE}/api/ping`,
      { headers: { 'X-Gauntlet-Token': TOKEN } })).json();
  } catch (e) { ping = null; }
  if (!ping || !ping.ok) {
    console.error(`the server on ${PORT} did not answer /api/ping; refusing to drive it`);
    process.exit(2);
  }
  if (!ping.scratch && process.env.GAUNTLET_ALLOW_LIVE_SAVE !== '1') {
    console.error(
`REFUSING TO RUN: the server on port ${PORT} is not on a throwaway data dir

    ${ping.data_dir || '(this server is too old to say — treat that as the real save)'}

This harness walks the character, starts encounters and can open a 115-minute
FINAL_EXAM that seals the world layer behind HTTP 409s. Start a throwaway one:

    GAUNTLET_DATA_DIR=$(mktemp -d) python3 run.py serve --port ${PORT} &

(or set GAUNTLET_ALLOW_LIVE_SAVE=1 if you really mean this save.)`);
    process.exit(2);
  }
}

globalThis.window.__GAUNTLET_TOKEN__ = TOKEN;
const realFetch = globalThis.fetch;
let calls = 0, failures = [];
globalThis.fetch = (path, opts) => { calls++; return realFetch(BASE + path, opts); };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };

const { api } = await import(`${ROOT}api.js`);
const B  = await import(`${ROOT}bosses.js`);
const FX = await import(`${ROOT}fx.js`);
const OW = await import(`${ROOT}overworld.js`);
const SC = await import(`${ROOT}battlescene.js`);

const ctx = newCtx(960, 540);
const rendered = [];
function paint(label, fn) {
  setWhere(label);
  const before = REC.drawCalls;
  try { fn(); } catch (e) { failures.push(`${label}: ${e.message}`); return; }
  rendered.push([label, REC.drawCalls - before]);
}
async function get(label, fn) {
  try { const v = await fn(); return v; }
  catch (e) { failures.push(`${label}: ${e.message}`); return null; }
}

// A previous drive may have left a measured run open on this save. Close it:
// this script is measuring the world, and the seal is measured on purpose lower
// down, from a run this script opens itself.
try { await api.finishInterview(); } catch (e) { /* none open */ }
try { await api.finishExam({}); } catch (e) { /* none open */ }

console.log('=== BOOT: the calls main.js makes before the title clears ===');
const ping   = await get('ping',   () => api.ping());
const state  = await get('state',  () => api.state());
const world  = await get('world',  () => api.world());
const map    = await get('map',    () => api.worldMap());
const todo   = await get('todo',   () => api.todo());
const curric = await get('curric', () => api.curriculum());
console.log(' ping    :', JSON.stringify(ping));
console.log(' state   :', 'level', state?.player?.level, '| region', state?.player?.region,
            '| skills', state?.skills?.length, '| bosses', state?.bosses?.length,
            '| keys', state?.keys_held + '/' + (state?.keys?.length ?? '?'));
console.log(' world   :', 'regions', world?.regions?.length, '| bosses', world?.bosses?.length,
            '| items', world?.items?.length);
console.log(' worldMap:', 'nodes', map?.nodes?.length, '| edges', map?.edges?.length,
            '| reachable', map?.reachable?.length, '| npcs', map?.npcs?.length,
            '| portal on the map:', !!map?.portal);
console.log(' todo    :', (todo?.todo ?? []).length, 'things to do:',
            (todo?.todo ?? []).map(t => t.id).join(', '));
console.log(' curric  :', curric?.next?.title ?? curric?.objective?.title ?? '(none)');

console.log('\n=== THE SCREENS ===');
for (const [label, fn] of [
  ['town',        () => api.town()],
  ['shop',        () => api.shop('python_village')],
  ['forge',       () => api.forge()],
  ['wheel',       () => api.wheel()],
  ['quests',      () => api.quests()],
  ['chains',      () => api.chains()],
  ['pets',        () => api.pets()],
  ['arts',        () => api.arts()],
  ['rollcall',    () => api.rollCall()],
  ['sanctuaries', () => api.sanctuaries()],
  ['keys',        () => api.keys()],
  ['portal',      () => api.portal()],
  ['hunt',        () => api.hunt('python_village')],
  ['classes',     () => api.classes()],
  ['dungeons',    () => api.dungeons()],
  ['legendaries', () => api.legendaries()],
  ['saves',       () => api.saves()],
  ['transfer',    () => api.transfer()],
  ['examLadder',  () => api.examLadder()],
  ['antagonist',  () => api.antagonist()],
  ['story',       () => api.story()],
]) {
  const v = await get(label, fn);
  const n = v && typeof v === 'object'
    ? Object.keys(v).length : 0;
  console.log(`  ${label.padEnd(12)} ${v ? 'OK' : 'FAIL'}  ${n} keys` +
              (v?.error ? `  error=${v.error}` : ''));
}

console.log('\n=== THE PORTAL PANEL, RENDERED ===');
const portal = await get('portal', () => api.portal());
console.log(' wards:', portal.wards?.length, '| lit:',
            (portal.wards ?? []).filter(w => w.lit).length,
            '| open:', portal.open, '| requirement:', portal.requirement,
            '| practical open:', portal.practical?.open,
            '| never gates:', (portal.never_gates ?? []).length);

console.log('\n=== A BOSS, FOUGHT: the client path ===');
// Walk home first if a previous drive left the player out in the world: this
// section is about what happens when you ask for a boss from the wrong place.
for (let i = 0; i < 8; i++) {
  const at = (await api.state()).player.region;
  if (at === 'python_village') break;
  const back = (await api.routes()).routes?.find(e => e.passable);
  if (!back) break;
  await api.travel(back.id ?? back.route);
}
console.log(' standing in:', (await api.state()).player.region);
let r = await get('startBoss(away)', () => api.startBoss('graph_necromancer'));
console.log(' from the village:', r?.error, '|', (r?.message || '').slice(0, 70));
console.log(' the refusal hands over a road:', r?.travel?.route, 'hops', r?.travel?.hops);
for (const route of (r?.travel?.path ?? [])) {
  const t = await get('travel', () => api.travel(route));
  if (t?.error) { failures.push(`travel ${route}: ${t.error}`); break; }
}
const here = (await api.state()).player.region;
console.log(' walked to:', here);
r = await get('startBoss(there)', () => api.startBoss('graph_necromancer'));
const fight = r?.boss?.fight;
console.log(' fight open: phase', fight?.phase, '/', fight?.phases,
            '| art_phase', fight?.art_phase, '| hp', fight?.hp + '/' + fight?.hp_max,
            '| ladder', (fight?.ladder ?? []).join(','));

console.log('\n=== THE SILHOUETTE, ACTUALLY DRAWN, ONE PER PHASE ===');
const arche = B.BOSS_ARCHETYPES.includes('necromancer') ? 'necromancer' : B.BOSS_ARCHETYPES[0];
// Warm the sprite cache first. A cold first render allocates by design; the
// claim being measured is that the LOOP does not, which is what run.mjs checks.
for (let p = 0; p < 6; p++) B.warmBoss(arche, '#6a4f8f', p);
for (let p = 0; p < 6; p++) B.drawBoss(ctx, arche, 480, 300, { time: 0, phase: p, seed: 5 });
const allocBeforeLoop = REC.allocTotal;
enterLoop('bossPhases');
for (let p = 0; p < (fight?.phases ?? 4); p++) {
  const stage = Math.ceil(p * 5 / ((fight?.phases ?? 4) - 1));
  const before = REC.drawCalls;
  paint(`drawBoss(phase ${p} -> stage ${stage})`,
        () => B.drawBoss(ctx, arche, 480, 300, { time: p * 400, phase: stage, seed: 5 }));
}
exitLoop();
for (const [label, n] of rendered) console.log(`  ${label.padEnd(40)} ${n} draw calls`);
console.log('  canvases allocated inside the loop:', REC.allocTotal - allocBeforeLoop,
            '| allocInLoop records:', REC.allocInLoop.length);

console.log('\n=== THE PRACTICAL, FROM THE MENU, WITH NO KEYS ===');
const keys = await api.keys();
console.log(' keys held:', keys.held.length, '/', keys.required);
const exam = await get('startExam', () => api.startExam());
console.log(' exam/start:', exam?.run ? `${exam.run.total} questions, ${exam.run.minutes} min` : exam?.error);
const cur = await get('interviewCurrent', () => api.interviewCurrent());
console.log(' question served:', cur?.problem?.id, '| pattern:', cur?.problem?.pattern);
console.log(' mid-run the town refuses to pay:', (await api.town()).visit?.error);
console.log(' mid-run heal:', await get('heal', () => api.heal()).then(v => v?.error ?? 'ALLOWED'));

console.log('\n=== WHAT THE STUB SAW ===');
console.log(' ', JSON.stringify(snapshot()));
console.log(' HTTP calls made:', calls);
console.log(' FAILURES:', failures.length ? failures : 'none');
process.exit(failures.length || REC.nullImage.length || REC.nonFinite.length
             || REC.badPaint.length ? 1 : 0);
