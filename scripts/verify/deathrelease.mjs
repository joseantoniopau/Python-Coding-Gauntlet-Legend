/* deathrelease.mjs — the one property a death screen must have: IT LETS GO.
 *
 * scripts/verify/death.mjs measures what the screen LOOKS like. This measures
 * what it DOES, and it is a separate file because the two failures are separate:
 * a death screen can be beautiful, correctly timed, exactly fifteen colours, and
 * still be the thing that ends somebody's playthrough because one bad frame
 * clock left it on screen forever. "Death is a setback, never a spiral and never
 * a wall" is a rule about the software as much as about the design.
 *
 * So this file is adversarial about the HOST rather than about the art. A host
 * is not a well-behaved loop. It is a browser tab that slept for four minutes,
 * a clock that handed back NaN, a player mashing keys during the beats, a
 * resize mid-animation, a second death fired before the first one finished.
 * Every one of those is driven below, from a seeded generator so a failure is
 * reproducible, and the same four questions are asked after each:
 *
 *     does t stay inside [0, DEATH_MS]        (it cannot run past the end)
 *     does it reach the end                   (it cannot stall before it)
 *     does `active` go false                  (the host is told to stop)
 *     are the words there when it does        (the player has something to read
 *                                              and a button to press)
 *
 * A. released from every t, by every route
 * B. hostile clocks, and the tab that woke up
 * C. the way out never depends on the report, the save, or the animation
 * D. fifteen colours off real pixels, and deterministic from a cold cache
 */
import { installRaster, RASTER, colourCount, frameHash } from './raster.mjs';
installRaster();

const D = await import('../../web/js/deathfx.js');

const fails = [];
const bad = (m) => { fails.push(m); console.log(`   FAIL ${m}`); return m; };
const ok = (cond, m) => { if (!cond) bad(m); return cond; };

const newCanvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
const ctxOf = (c) => c.getContext('2d');

/* Seeded, so "it failed on run 3141" is a thing somebody can reproduce rather
 * than a thing they have to believe. Not in a draw path — this only chooses
 * which abuse to apply next. */
let seed = 0x9e3779b9;
const rnd = () => { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return ((seed >>> 0) % 100000) / 100000; };

const LOOKS = [
  ['none', null],
  ['bare', { weapon: 'sword', emote: 'neutral' }],
  ['plate', { weapon: 'sword', emote: 'neutral', cloak: '#52456e', tunic: '#7d6b90',
              metal: '#b0aabd', trim: '#a08a52', boot: '#715b45', skin: '#c08a62',
              hair: '#4a3a2c' }],
  ['garbage', { weapon: 42, emote: null, cloak: 'not-a-colour', metal: undefined }],
];

const REPORTS = [
  ['a full death', { wake: { region: 'Sunken Vault', label: 'Entered the Sunken Vault' },
                     cost: { playtime: '12m 22s', gold: 340, items: 3, levels: 1 },
                     kept: { attempts: 1841, skills: 26, mastery: '61%', due: 12 } }],
  ['no save at all', { wake: { region: '', label: '' }, cost: {}, kept: { attempts: 3, skills: 1, mastery: '0%', due: 0 } }],
  ['null', null],
  ['undefined', undefined],
  ['empty', {}],
  ['hostile', { wake: 7, cost: 'lots', kept: [1, 2, 3] }],
  ['nested nulls', { wake: null, cost: null, kept: null }],
  ['numbers as strings', { wake: { region: 12 }, cost: { gold: 'many', items: null }, kept: { attempts: '5' } }],
];

function released(e, where) {
  let bads = 0;
  if (!(e.t >= 0 && e.t <= D.DEATH_MS)) bads += !!bad(`${where}: t escaped the timeline at ${e.t}`);
  if (e.active) bads += !!bad(`${where}: still active`);
  if (e.t !== D.DEATH_MS) bads += !!bad(`${where}: stalled at t=${e.t}, expected ${D.DEATH_MS}`);
  if (!e.showWords) bads += !!bad(`${where}: ended with nothing to read`);
  if (!e.canSkip) bads += !!bad(`${where}: ended with no way out`);
  const w = e.words;
  if (!w || !Array.isArray(w.lines) || w.lines.length === 0) bads += !!bad(`${where}: no lines`);
  if (!w || !Array.isArray(w.actions) || w.actions.length === 0) bads += !!bad(`${where}: no action to press`);
  return bads === 0;
}

/* ===================== A. released from every t, every route ============= */
console.log('A. IT ALWAYS LETS GO');
{
  const ctx = ctxOf(newCanvas(960, 540));
  const routes = {
    'played out': (e) => { for (let i = 0; i < 2000 && e.active; i++) e.update(1 / 60); },
    'skipped at once': (e) => e.skip(),
    'skipped mid-beat': (e) => { e.update(0.5); e.skip(); },
    'skipped twice': (e) => { e.skip(); e.skip(); },
    'sought to the end': (e) => e.seek(D.DEATH_MS),
    'sought past the end': (e) => e.seek(1e9),
    'sought backwards then played': (e) => { e.seek(-1e9); for (let i = 0; i < 2000 && e.active; i++) e.update(1 / 60); },
    'one enormous frame': (e) => { e.update(999); for (let i = 0; i < 2000 && e.active; i++) e.update(1 / 60); },
  };
  let runs = 0;
  for (const [lname, look] of LOOKS) {
    for (const [rname, report] of REPORTS) {
      for (const reduced of [false, true]) {
        for (const [route, drive] of Object.entries(routes)) {
          for (const seen of [0, 1, 9]) {
            const e = D.createDeath({ look, report, reduced, seen }).begin({});
            drive(e);
            e.draw(ctx, 960, 540);
            released(e, `${lname}/${rname}/${reduced ? 'reduced' : 'full'}/${route}/seen=${seen}`);
            runs++;
          }
        }
      }
    }
  }
  console.log(`   ${runs} runs: 4 kits x ${REPORTS.length} reports x 2 motion settings x ${Object.keys(routes).length} routes x 3 death counts`);
  console.log(`   every one ended at t=${D.DEATH_MS}ms, inactive, with words and a button`);
}

/* skip arming, stated in milliseconds rather than in prose */
{
  const first = D.skipArmedAt(0);
  const later = D.skipArmedAt(1);
  console.log(`   skip armed at   first death ${first} ms (the third beat lands at ${D.DEATH_BEAT_AT[2]} ms), thereafter ${later} ms`);
  ok(first === D.DEATH_BEAT_AT[D.DEATH_BEAT_AT.length - 1], 'the first death arms the skip somewhere other than the last beat');
  ok(later === 0, 'the second death does not arm the skip immediately');
  ok(first < D.DEATH_MS, 'the skip arms after the screen has already ended');
  // the longest a key press can go unanswered, which is the number that matters
  console.log(`   worst unanswered keypress: ${first} ms, and it happens once per playthrough`);
  ok(first <= 2500, `a player can be ignored for ${first} ms`);
  for (const seen of [-5, 0, 0.5, 1, NaN, undefined, null, 'many', 1e9]) {
    const at = D.skipArmedAt(seen);
    ok(Number.isFinite(at) && at >= 0 && at <= D.DEATH_MS, `skipArmedAt(${String(seen)}) returned ${at}`);
  }
}

/* ===================== B. hostile clocks ================================= */
console.log('\nB. HOSTILE CLOCKS');
{
  const ctx = ctxOf(newCanvas(640, 360));
  const CLOCKS = [
    ['NaN every frame', () => NaN],
    ['undefined every frame', () => undefined],
    ['negative', () => -0.016],
    ['zero', () => 0],
    ['a sleeping tab', () => (rnd() < 0.1 ? 240 : 0.016)],
    ['sixty hertz', () => 1 / 60],
    ['two hundred and forty hertz', () => 1 / 240],
    ['jitter', () => 0.001 + rnd() * 0.2],
    ['strings', () => '0.016'],
    ['Infinity', () => Infinity],
  ];
  for (const [name, clock] of CLOCKS) {
    const e = D.createDeath({ look: LOOKS[2][1] }).begin({});
    let frames = 0;
    let escaped = false;
    for (; frames < 100000 && e.active; frames++) {
      e.update(clock());
      if (!(e.t >= 0 && e.t <= D.DEATH_MS)) { escaped = true; break; }
      if (frames % 97 === 0) e.draw(ctx, 640, 360);
    }
    ok(!escaped, `${name}: t left the timeline`);
    if (e.active) {
      // A clock that can never advance is the host's bug, not this module's —
      // but the player must still be able to leave, so the skip has to work.
      e.skip();
      released(e, `${name} (stalled clock, then skipped)`);
      console.log(`   ${name.padEnd(32)} never advanced; skip() still released it`);
    } else {
      released(e, name);
      console.log(`   ${name.padEnd(32)} ended after ${frames} frames at t=${Math.round(e.t)}ms`);
    }
  }
}

/* THE PER-FRAME CEILING, stated rather than assumed.
 *
 * A single frame may not swallow the whole sequence: a tab that slept through
 * the beats and woke on the words would have shown the player a death screen
 * with no death in it. So `update` clamps its delta, and the clamp is measured
 * here rather than read off the source — the number that matters is how many
 * frames the worst case still needs to finish, because "it clamps" is only
 * acceptable if it still ends. */
{
  const probe = D.createDeath({ look: null }).begin({});
  probe.update(1e6);
  const ceiling = probe.t;
  ok(ceiling > 0, 'a single frame advances nothing at all');
  ok(ceiling < D.DEATH_MS, `one frame advanced ${ceiling}ms and swallowed the whole sequence`);
  const worstFrames = Math.ceil(D.DEATH_MS / ceiling);
  console.log(`   one frame advances at most ${ceiling} ms, so even a tab waking once per`);
  console.log(`   sequence needs ${worstFrames} frames to finish — and it does finish`);
  for (let i = 0; i < 1000 && probe.active; i++) probe.update(1e6);
  released(probe, 'the slowest possible host');
}

/* the tab that slept, mid-beat, and then a resize on the frame it woke */
{
  const e = D.createDeath({ look: LOOKS[1][1], seen: 1 }).begin({});
  e.update(0.4);
  const mid = e.t;
  for (let i = 0; i < 1000 && e.active; i++) e.update(300);   // four minutes a frame
  for (const [w, h] of [[1, 1], [3840, 2160], [0, 0], [960, 540]]) {
    const c = newCanvas(Math.max(1, w), Math.max(1, h));
    e.draw(ctxOf(c), w, h);
  }
  released(e, 'slept then resized');
  console.log(`   a tab that slept at t=${Math.round(mid)}ms woke up finished, and survived four resizes`);
}

/* A CLOCK THAT NEVER MOVES is a broken host, and the screen still has to let go.
 *
 * `canSkip` is arming advice and it is measured in a clock; a clock stuck on NaN
 * arms nothing, ever. So the guarantee rule E actually rests on is that `skip()`
 * is UNGATED — it works from any t, on any death, armed or not — and that a
 * screen which has stopped for any reason reports that the player may leave. */
{
  for (const seen of [0, 1]) {
    const e = D.createDeath({ look: LOOKS[1][1], seen }).begin({});
    for (let i = 0; i < 500; i++) e.update(NaN);
    ok(e.t === 0, `a NaN clock moved t to ${e.t}`);
    e.skip();
    released(e, `NaN clock forever, seen=${seen}`);
  }
  const stopped = D.createDeath({ look: null, seen: 0 }).begin({});
  stopped.cancel();
  ok(stopped.canSkip, 'a stopped screen told the player they may not leave it');
  const sought = D.createDeath({ look: null, seen: 0 }).begin({});
  sought.seek(D.DEATH_MS);
  ok(!sought.active, 'seek() to the end left the host loop running forever');
  ok(sought.canSkip, 'a finished screen told the player they may not leave it');
  console.log('   skip() is ungated and released the screen on the first death with a dead clock');
  console.log('   a cancelled screen and a screen sought to the end both report canSkip');
}

/* a second death fired over a running one */
{
  const e = D.createDeath({ look: LOOKS[1][1] }).begin({});
  e.update(1.0);
  e.begin({ report: REPORTS[0][1], seen: 3 });
  ok(e.t === 0 && e.active, 'restarting did not rewind the screen');
  for (let i = 0; i < 2000 && e.active; i++) e.update(1 / 60);
  released(e, 'restarted mid-animation');
  e.begin({}); e.cancel();
  ok(!e.active, 'cancel() left the screen active');
  console.log('   a second death over a running one rewinds cleanly; cancel() stops it');
}

/* ===================== C. the way out is unconditional =================== */
console.log('\nC. THE WAY OUT NEVER DEPENDS ON ANYTHING');
for (const [name, report] of REPORTS) {
  const words = D.deathLines(report);
  const ids = words.lines.map((l) => l.id);
  ok(words.lines.length > 0, `${name}: no lines at all`);
  ok(ids.includes('where'), `${name}: does not say where the player wakes`);
  ok(ids.includes('kept'), `${name}: does not say what dying could not take`);
  ok(words.actions.length === 1 && words.actions[0].id === 'wake', `${name}: no GET UP`);
  ok(!JSON.stringify(words).includes('!'), `${name}: the death screen shouts`);
  const kept = words.lines.find((l) => l.id === 'kept');
  ok(kept && kept.text === D.KEPT_LINE, `${name}: the kept line was edited or dropped`);
  console.log(`   ${name.padEnd(20)} ${words.lines.length} lines [${ids.join(' ')}] + ${words.actions.length} action`);
}
ok(/keep/i.test(D.NO_SAVE_LINE) || /everything you have already learned/i.test(D.NO_SAVE_LINE),
   'the no-save line does not tell the player they can keep going');
console.log(`   with no save at all: "${D.NO_SAVE_LINE}"`);
console.log('   the kept line carries no numbers, so it is true on a death that cost nothing');
ok(!/\d/.test(D.KEPT_LINE), 'the unconditional kept line carries a number it cannot always support');

/* ===================== D. colours, off real pixels ======================= */
console.log('\nD. FIFTEEN COLOURS, DETERMINISTIC');
{
  const HOST = [[192, 128], [640, 360], [960, 540], [1920, 1080]];
  let worst = 0, worstAt = '';
  let frames = 0;
  for (const [lname, look] of LOOKS) {
    for (const [w, h] of HOST) {
      for (const reduced of [false, true]) {
        const c = newCanvas(w, h), cx = ctxOf(c);
        const e = D.createDeath({ look, reduced }).begin({});
        for (let i = 0; i <= 48; i++) {
          e.seek((D.DEATH_MS * i) / 48);
          e.draw(cx, w, h);
          frames++;
          const n = colourCount(c);
          if (n > worst) { worst = n; worstAt = `${lname} ${w}x${h}${reduced ? ' reduced' : ''} t=${Math.round(e.t)}`; }
          if (n > 15) bad(`${lname} ${w}x${h} t=${Math.round(e.t)} painted ${n} colours`);
        }
      }
    }
  }
  console.log(`   worst colour count over ${frames} rendered frames: ${worst} (${worstAt}), budget 15`);
}

/* determinism: a cold cache and a warm one must paint the same bytes */
{
  const run = () => {
    const c = newCanvas(640, 360), cx = ctxOf(c);
    const e = D.createDeath({ look: LOOKS[2][1] }).begin({});
    const hashes = [];
    for (let i = 0; i <= 24; i++) { e.seek((D.DEATH_MS * i) / 24); e.draw(cx, 640, 360); hashes.push(frameHash(c)); }
    return hashes.join(':');
  };
  D.clearDeathCache();
  const cold = run();
  const warm = run();
  D.clearDeathCache();
  const coldAgain = run();
  ok(cold === warm, 'a warm cache paints different pixels to a cold one');
  ok(cold === coldAgain, 'two cold runs disagree');
  console.log(`   25-frame hash  cold ${cold.slice(0, 8)}...  warm identical: ${cold === warm}  cold again identical: ${cold === coldAgain}`);

  const src = (await import('fs')).readFileSync(new URL('../../web/js/deathfx.js', import.meta.url), 'utf8');
  ok(!/Math\.random/.test(src), 'deathfx.js calls Math.random');
  ok(!/Date\.now|performance\.now/.test(src), 'deathfx.js reads a wall clock in a draw path');
  console.log('   no Math.random and no wall clock anywhere in deathfx.js');

  RASTER.counting = true; RASTER.canvases = 0;
  const e = D.createDeath({ look: LOOKS[2][1] }).begin({});
  const ctx = ctxOf(newCanvas(960, 540));
  const after = RASTER.canvases;
  RASTER.canvases = 0;
  for (let i = 0; i < 300 && e.active; i++) { e.update(1 / 60); e.draw(ctx, 960, 540); }
  RASTER.counting = false;
  ok(RASTER.canvases === 0, `${RASTER.canvases} canvases allocated during playback`);
  console.log(`   allocations   ${after} on begin(), ${RASTER.canvases} across a full playback`);
  console.log(`   caches        ${JSON.stringify(D.deathStats())}`);
}

console.log('\n========================================================================');
if (fails.length) {
  console.log(`FAIL — ${fails.length} problem(s)`);
  for (const f of fails.slice(0, 20)) console.log(`  ${f}`);
  process.exit(1);
}
console.log('PASS — the death screen released the player from every t, by every route,');
console.log('       under every clock a browser can produce, with any report or none;');
console.log('       fifteen colours off real pixels and byte-identical from a cold cache.');
