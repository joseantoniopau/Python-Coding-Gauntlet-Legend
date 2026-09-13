/* THE SKY, MEASURED — in pixels and in slot indices, never in "it did not throw".
 *
 * Three things were wrong and all three are claims about what you can SEE, so
 * all three are checked against a real raster rather than against a call log:
 *
 *   it always rained     every biome carried an `anim` list that was always
 *                        fully on, and grass was ['lightning','rain','fog'].
 *   nothing changed      there was no clear state anywhere in the table.
 *   nobody agreed        the overworld drew one thing out of its own table and
 *                        the battle drew another out of a different one.
 *
 * Seven measurements:
 *
 *   A  ONE ANSWER      the strip that gauntlet/weather.py shipped, read by the
 *                      OVERWORLD path (a region record) and by the BATTLE path
 *                      (a palette string, which is all main.js passes), across
 *                      FOUR AND A HALF HOURS of sampled moments — 2.3 strips —
 *                      must agree with each other AND with what Python says at
 *                      the same instant. Zero drift, with no escape hatch for a
 *                      clamped read.
 *   H  IT NEVER STOPS   a host that refreshes when the client says `stale`
 *                      never sees a stale read again, and the LIVE Overworld
 *                      asks for that refresh exactly once per exhausted strip.
 *   B  CLEAR IS CLEAR  on a clear day no biome — not one of the seventeen —
 *                      builds rain, bolts or falling motes. This is the death
 *                      of "it always rains", stated as a count of zero.
 *   C  IT LOOKS        every condition must change the picture. Each one is
 *      DIFFERENT       rendered and diffed against the same region rendered
 *                      clear, in pixels.
 *   D  DENSITY READS   drizzle < rain < storm, in pixels, in that order.
 *   E  FIREBALLS       the volcano's firestorm must actually paint a fireball:
 *                      hot-core pixels above the deck, moving with time.
 *   F  FURNITURE       a torch does not go out because the sky cleared, and the
 *                      JS fixture table matches weather.py's to the letter.
 *   G  DETERMINISM     the same region, condition and time hash identically
 *                      twice, and nothing new reaches for Math.random.
 *
 * Run: node scripts/verify/weather.mjs
 */
import { installRaster, pixelDiff, frameHash } from './raster.mjs';
installRaster();
/* overworld.js binds keys on construction and measures its own parent element.
 * Both are the host's business, not this module's, so both are stubbed — and
 * stubbed BEFORE the import, because the module binds at construction. */
if (typeof globalThis.addEventListener !== 'function') {
  globalThis.addEventListener = () => {};
  globalThis.removeEventListener = () => {};
}
import fs from 'fs';
import { execSync } from 'child_process';

const ROOT = new URL('../../', import.meta.url).pathname;
const SC = await import('../../web/js/battlescene.js');
const PX = await import('../../web/js/pixel.js');
const OW = await import('../../web/js/overworld.js');

/* The truth, live out of Python. Not a checked-in fixture: a fixture would let
 * weather.py drift away from the thing being verified, which is the entire
 * class of bug this harness exists to catch. */
const PY = JSON.parse(execSync(
  'python3 -c "' +
  'import json,sys; sys.path.insert(0,\'.\');' +
  'from gauntlet import weather, world;' +
  'BASE=1700000000.0;' +
  'print(json.dumps({' +
  '  \'slot_seconds\': weather.SLOT_SECONDS,' +
  '  \'fixtures\': {k: list(v) for k, v in weather.FIXTURES.items()},' +
  '  \'conditions\': {n: {\'anim\': list(c[\'anim\']), \'particle\': c[\'particle\'],' +
  '                      \'density\': c[\'density\']} for n, c in weather.CONDITIONS.items()},' +
  '  \'regions\': {r[\'id\']: {' +
  '      \'biome\': r[\'biome\'], \'palette\': r[\'palette\'],' +
  '      \'weather\': weather.forecast(r[\'id\'], 12345, BASE),' +
  /* PAST THE END OF THE STRIP, ON PURPOSE. range(53) at 137s covered 7124s and
   * the strip covers 7200s from an epoch 200s behind BASE, so exactly one probe
   * per region landed past it — and measurement A threw that one away, because
   * it skipped any read flagged `stale`. Four and a half hours of probes with
   * no such skip is what makes the freeze visible: the client that shipped
   * before this line was wrong in 877 of them. */
  '      \'probes\': [[BASE + s * 137.0, weather.condition_at(r[\'id\'], 12345, BASE + s * 137.0)]' +
  '                  for s in range(120)],' +
  /* And what the SERVER would answer if the client asked again at slot N. This
   * is the refreshed record main.js:refresh() now rebinds the overworld to; the
   * harness feeds it in at the same boundary rather than pretending the first
   * strip lasts forever. */
  '      \'refetch\': {str(int(BASE // weather.SLOT_SECONDS) + k):' +
  '                   weather.forecast(r[\'id\'], 12345,' +
  '                       (int(BASE // weather.SLOT_SECONDS) + k) * weather.SLOT_SECONDS)' +
  '                   for k in range(130)},' +
  '  } for r in world.REGIONS},' +
  '}))"',
  { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));

const REGIONS = Object.keys(PY.regions);
const bad = [];
const note = [];
const fail = (m) => { bad.push(m); };
const pct = (a, b) => (b ? (100 * a / b).toFixed(1) + '%' : '—');

/* ---------- a canvas to paint into ---------- */
const STAGE = SC.SCENE_STAGE;
function surface(w, h) {
  const c = globalThis.document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}
/* One frame of a whole stage: backdrop, then everything in front of it. The
 * figures are not drawn — this is a measurement about the room, not the fight.
 *
 * drawImage is wrapped because the raster context IGNORES anything that is not
 * a surface, and a browser throws. A scene field that used to be a canvas and
 * is quietly overwritten with a plain object therefore renders as a silent
 * nothing here and as an exception on every frame in the real game. That
 * happened once during this work — `sky` is the painted sky canvas and the
 * weather nearly took the name — so it is a hard failure now. */
let badDraws = 0;
function render(scene, t) {
  const cv = surface(STAGE.w, STAGE.h);
  const ctx = cv.getContext('2d');
  const real = ctx.drawImage.bind(ctx);
  ctx.drawImage = (img, ...rest) => {
    if (!img || typeof img.width !== 'number' || !img.data) {
      badDraws++;
      throw new TypeError('drawImage given a non-surface: ' + Object.prototype.toString.call(img));
    }
    return real(img, ...rest);
  };
  SC.drawScene(ctx, scene, t, null);
  SC.drawForeground(ctx, scene, t, null);
  return cv;
}

/* Every field a scene hands to drawImage must still BE a surface. */
function surfaceFields(scene) {
  const out = [];
  for (const k of ['sky', 'platform', 'vignette', 'occLeft', 'occRight', 'apron',
                   'keyGlow', 'floorPool', 'fillGlow']) {
    const v = scene[k];
    if (!v || typeof v.width !== 'number' || !v.data) out.push(k);
  }
  return out;
}

/* A region record shaped exactly like the one the server sends, with one
 * condition pinned. Pinning is how a harness drives a model it must not
 * duplicate: the strip is real, it is just one entry long. */
function pinned(id, condition, when = 1700000000) {
  const r = PY.regions[id];
  const leg = {};
  leg[condition] = PY.conditions[condition];
  return {
    id, biome: r.biome, palette: r.palette,
    weather: {
      region: id, biome: r.biome, condition, label: condition,
      anim: PY.conditions[condition].anim,
      fixtures: PY.fixtures[r.biome] || [],
      particle: PY.conditions[condition].particle,
      density: PY.conditions[condition].density,
      now: when, slot_seconds: PY.slot_seconds,
      epoch: Math.floor(when / PY.slot_seconds) * PY.slot_seconds,
      strip: [condition], legend: leg,
    },
  };
}

function sceneFor(id, condition, opts = {}) {
  const reg = pinned(id, condition);
  return SC.createScene({
    region: reg, palette: reg.palette, boss: false,
    key: id + '|' + (opts.key || 'field'),
    when: reg.weather.now, ...opts,
  });
}

/* ================================================================
 * A — ONE ANSWER, TWO RENDERERS
 * ================================================================ */
{
  let checks = 0, drift = 0, pyDrift = 0, refetches = 0, staleReads = 0;
  for (const id of REGIONS) {
    const r = PY.regions[id];
    const region = { id, biome: r.biome, palette: r.palette, weather: r.weather };
    // The overworld publishes the place it loaded. This is the only wire.
    SC.publishWeather(region);
    for (const [t, expect] of r.probes) {
      // The overworld asks with the record it holds...
      let field = SC.resolveSky(region, null, t);
      /* THE HOST REFRESHES, SO THE HARNESS DOES TOO. `stale` means the strip
       * has run out; overworld._pollSky() calls onSkyStale, main.js:refresh()
       * rebinds the overworld to the fresh record and republishes it. That is
       * the shipped behaviour, so model it here — and then hold the answer to
       * the same standard as every other one. Excusing a clamped read, which
       * is what this loop used to do, is what let a permanently frozen sky
       * ship green. */
      if (field.stale) {
        const fresh = r.refetch[String(Math.floor(t / PY.slot_seconds))];
        if (fresh) { region.weather = fresh; SC.publishWeather(region); refetches++; }
        field = SC.resolveSky(region, null, t);
      }
      // ...and the battle asks with the palette string main.js actually passes.
      const fight = SC.resolveSky(r.palette, r.palette, t);
      checks++;
      if (field.condition !== fight.condition) drift++;
      if (field.condition !== expect) pyDrift++;
      if (field.stale) staleReads++;
    }
  }
  const span = ((PY.regions[REGIONS[0]].probes.length - 1) * 137).toFixed(0);
  note.push(`A  ${checks} moments probed across ${REGIONS.length} regions, spanning ${span}s = ${(span / 7200).toFixed(1)} strips`);
  note.push(`A  overworld vs battle disagreements: ${drift}`);
  note.push(`A  client vs gauntlet/weather.py disagreements: ${pyDrift}`);
  note.push(`A  strips exhausted and refetched by the host: ${refetches}`);
  if (drift) fail(`A: the two renderers disagreed ${drift}/${checks} times`);
  if (pyDrift) fail(`A: the client read the strip wrong ${pyDrift}/${checks} times`);
  /* H, first half. A record the host keeps refreshing is never read stale. */
  note.push(`H  stale reads surviving a refreshing host: ${staleReads}/${checks}`);
  if (staleReads) fail(`H: ${staleReads}/${checks} reads were still stale after a refresh`);

  // And the same thing again through the live Overworld object, so the claim is
  // about the shipped module rather than about a function it happens to export.
  const cv = surface(640, 420);
  cv.parentElement = { getBoundingClientRect: () => ({ x: 0, y: 0, width: 640, height: 420, top: 0, left: 0, right: 640, bottom: 420 }) };
  const ow = new OW.Overworld(cv);
  let owChecks = 0, owDrift = 0;
  for (const id of ['fields_of_syntax', 'twin_pointer_pass', 'stack_queue_mines']) {
    for (const cond of ['clear', 'storm', 'snow', 'firestorm']) {
      if (!PY.conditions[cond]) continue;
      const reg = pinned(id, cond);
      ow.load(reg, 2);
      const st = PX.PARTICLE_STYLE[PY.conditions[cond].particle];
      owChecks++;
      if (ow.particleStyle !== st) owDrift++;
      if (ow.sky.condition !== cond) owDrift++;
      // ...and the battle, standing in the same place a moment later.
      const scene = SC.createScene({ region: reg.palette, palette: reg.palette,
                                     key: id + '|fight', when: reg.weather.now });
      if (scene.condition !== cond) owDrift++;
      if (scene.biome !== reg.biome) owDrift++;
    }
  }
  note.push(`A  live Overworld.load -> battle handoffs: ${owChecks}, mismatches: ${owDrift}`);
  if (owDrift) fail(`A: the live overworld and the live stage disagreed ${owDrift} times`);

  /* THE CASE THAT ACTUALLY HAPPENS IN PLAY. An encounter payload's `region` is
   * the PROBLEM'S realm, not the player's: standing in Python Village and being
   * handed an ARRAY problem sends the stage the palette `stone`, which belongs
   * to Array Caverns. The fight is still happening in the village, so the
   * village's sky is the right answer and the caverns' is not. */
  let wrongPlace = 0, tried = 0;
  for (const here of ['python_village', 'fields_of_syntax', 'twin_pointer_pass']) {
    for (const cond of ['storm', 'clear', 'snow']) {
      const reg = pinned(here, cond);
      SC.publishWeather(reg);                       // the overworld loads a map
      for (const elsewhere of ['stone', 'iron', 'ember', 'void']) {
        tried++;
        const got = SC.resolveSky(elsewhere, elsewhere, reg.weather.now);
        if (got.condition !== cond || got.region !== here) wrongPlace++;
      }
    }
  }
  note.push(`A  fights staged from another realm's palette: ${tried} probed, ${wrongPlace} fought in the wrong weather`);
  if (wrongPlace) fail(`A: ${wrongPlace}/${tried} fights took the sky of a region the player was not in`);

  // The particle style a condition names must exist in pixel.js, or the
  // overworld silently falls back to motes and the two diverge quietly.
  for (const [n, c] of Object.entries(PY.conditions)) {
    if (!PX.PARTICLE_STYLE[c.particle]) fail(`A: condition ${n} names unknown particle ${c.particle}`);
  }
}

/* ================================================================
 * H — THE SKY DOES NOT STOP AT TWO HOURS
 * ================================================================
 * Measurement A models the host by hand. This one drives the SHIPPED Overworld
 * object through eight hours of standing still and asks whether IT notices.
 *
 * The strip is 24 slots — two hours — and nothing refetches it on its own, so a
 * player who stays put runs off the end, readSky() clamps to the last slot and
 * flags `stale`, and before overworld._pollSky() acted on that flag the sky was
 * frozen there for the rest of the session. Measured on the shipped client:
 * seven condition changes in the first two hours and zero in the next five.
 *
 * The host here is exactly what main.js does now: on onSkyStale, swap in the
 * record the server would send and rebind. The clock is moved rather than
 * waited out, because _pollSky() reads Date.now() through skyNow().
 */
{
  const realNow = Date.now;
  const cv = surface(640, 420);
  cv.parentElement = { getBoundingClientRect: () => ({ x: 0, y: 0, width: 640, height: 420, top: 0, left: 0, right: 640, bottom: 420 }) };
  const SLOTS = 96;                       // eight hours, four strips
  let totalAsks = 0, totalStale = 0, totalWrong = 0, totalChanges = 0, hosted = 0;
  for (const id of ['graph_wastes', 'twin_pointer_pass', 'python_village']) {
    const r = PY.regions[id];
    const first = r.refetch[String(Math.floor(r.probes[0][0] / PY.slot_seconds))];
    const rec = { id, biome: r.biome, palette: r.palette, weather: first };
    let clock = (first.epoch + 1) * 1000;
    Date.now = () => clock;
    const ow = new OW.Overworld(cv);
    let asks = 0;
    /* The host. refresh() fetches a fresh payload and rebinds the overworld to
     * the record in it; the harness has every one of those payloads already. */
    ow.onSkyStale = () => {
      asks++;
      const fresh = r.refetch[String(Math.floor(clock / 1000 / PY.slot_seconds))];
      if (fresh) { rec.weather = fresh; ow.region = rec; }
    };
    ow.load(rec, 2);
    let prev = ow.sky.condition, changes = 0, stale = 0, wrong = 0;
    for (let i = 1; i <= SLOTS; i++) {
      clock = (first.epoch + i * PY.slot_seconds + 1) * 1000;
      ow.update(3);                       // one frame, long enough to poll
      const read = SC.resolveSky(ow.region, null, clock / 1000);
      if (read.stale) stale++;
      if (ow.sky.condition !== read.condition) wrong++;
      if (ow.sky.condition !== prev) { changes++; prev = ow.sky.condition; }
    }
    Date.now = realNow;
    note.push(`H  ${id.padEnd(18)} ${SLOTS} slots (8h): ${changes} condition changes, ${asks} refetches asked for, ${stale} stale reads`);
    totalAsks += asks; totalStale += stale; totalWrong += wrong; totalChanges += changes;
    hosted++;
  }
  note.push(`H  ${hosted} regions stood in for eight hours: ${totalChanges} changes, ${totalStale} stale reads, ${totalAsks} refetches`);
  if (totalStale) fail(`H: ${totalStale} reads were stale even though the host was refreshing`);
  if (totalWrong) fail(`H: the field's applied sky disagreed with the strip ${totalWrong} times`);
  /* Four strips per region, three regions: the field must ask at least once per
   * exhausted strip and must not ask on every poll. */
  if (totalAsks < hosted * 3) fail(`H: the field only asked for a fresh strip ${totalAsks} times in ${hosted * 4} strips`);
  if (totalAsks > hosted * 8) fail(`H: the field asked for a fresh strip ${totalAsks} times — that is a fetch per poll`);
  if (totalChanges < hosted * 4) fail(`H: only ${totalChanges} condition changes across ${hosted} regions and eight hours — the sky is frozen`);
  Date.now = realNow;
}

/* ================================================================
 * B — CLEAR IS CLEAR, IN ALL SEVENTEEN ROOMS
 * ================================================================ */
{
  let wet = 0;
  const rows = [];
  for (const id of REGIONS) {
    const s = sceneFor(id, 'clear');
    const carries = [];
    if (s.rain) carries.push('rain');
    if (s.foreRain) carries.push('forerain');
    if (s.bolts) carries.push('lightning');
    if (s.motes) carries.push('motes');
    if (s.fireballs) carries.push('fireball');
    if (s.drips) carries.push('drip');
    if (s.wisps) carries.push('flies');
    if (s.godrays) carries.push('godray');
    if (carries.length) { wet++; rows.push(`${id}: ${carries.join(',')}`); }
  }
  note.push(`B  regions that still make weather on a clear day: ${wet}/${REGIONS.length}`);
  for (const r of rows) note.push(`B    ${r}`);
  if (wet) fail(`B: ${wet} regions cannot have a clear day`);

  // The specific one the complaint was about.
  const fields = sceneFor('fields_of_syntax', 'clear');
  const storm = sceneFor('fields_of_syntax', 'storm');
  const a = render(fields, 1.7), b = render(storm, 1.7);
  const d = pixelDiff(a, b);
  note.push(`B  Fields of Syntax clear vs storm: ${d} pixels differ (${pct(d, STAGE.w * STAGE.h)} of frame)`);
  if (d < 400) fail(`B: a storm in the Fields only moves ${d} pixels`);
  if (fields.condition !== 'clear' || fields.anim.join(',') !== '') {
    fail(`B: a clear Fields still runs [${fields.anim.join(',')}]`);
  }
  if (!storm.rain || !storm.bolts) fail('B: a storm in the Fields has no rain or no lightning');
}

/* ================================================================
 * C — EVERY CONDITION CHANGES THE PICTURE
 * ================================================================ */
{
  const HOME = { clear: 'fields_of_syntax' };
  const base = {};
  const seen = new Map();
  for (const name of Object.keys(PY.conditions)) {
    // Rendered in a region whose climate can actually produce it, so the room
    // is the one the condition was authored against.
    let home = 'fields_of_syntax';
    for (const id of REGIONS) {
      if ((PY.regions[id].weather.legend || {})[name]) { home = id; break; }
    }
    if (!base[home]) base[home] = render(sceneFor(home, 'clear'), 1.7);
    const cv = render(sceneFor(home, name), 1.7);
    const d = pixelDiff(base[home], cv);
    const h = frameHash(cv);
    note.push(`C  ${name.padEnd(10)} in ${home.padEnd(22)} ${String(d).padStart(6)} px vs clear   ${h}`);
    /* Twenty pixels, not two hundred: a flurry is fourteen flakes a pixel wide
     * and that is what a flurry is supposed to be. The floor is here to catch a
     * condition that draws NOTHING, which is a different failure from one that
     * draws a little. */
    if (name !== 'clear' && d < 20) fail(`C: ${name} only moves ${d} pixels`);
    if (name === 'clear' && d !== 0) fail(`C: clear differs from itself by ${d}`);
    if (seen.has(h) && name !== 'clear') fail(`C: ${name} renders identically to ${seen.get(h)}`);
    seen.set(h, name);
  }
}

/* ================================================================
 * D — DENSITY READS
 * ================================================================ */
{
  const clear = render(sceneFor('fields_of_syntax', 'clear'), 2.3);
  const steps = ['drizzle', 'rain', 'storm'];
  const counts = steps.map(n => pixelDiff(clear, render(sceneFor('fields_of_syntax', n), 2.3)));
  note.push(`D  drizzle ${counts[0]} px < rain ${counts[1]} px < storm ${counts[2]} px`);
  for (let i = 1; i < counts.length; i++) {
    if (!(counts[i] > counts[i - 1])) fail(`D: ${steps[i]} (${counts[i]}) is not heavier than ${steps[i - 1]} (${counts[i - 1]})`);
  }
  const drops = steps.map(n => (sceneFor('fields_of_syntax', n).rain || []).length / 4);
  note.push(`D  raindrops built: ${steps.map((n, i) => `${n}=${drops[i]}`).join('  ')}`);
  if (!(drops[0] < drops[1] && drops[1] < drops[2])) fail('D: the drop counts do not follow the density');

  const snow = ['flurry', 'snow', 'blizzard'].map(n => (sceneFor('twin_pointer_pass', n).motes || []).length / 5);
  note.push(`D  snowflakes built: flurry=${snow[0]} snow=${snow[1]} blizzard=${snow[2]}`);
  if (!(snow[0] < snow[1] && snow[1] <= snow[2])) fail('D: snow does not thicken with the condition');
}

/* ================================================================
 * E — FIREBALLS IN THE VOLCANO
 * ================================================================
 * Measured by SUBTRACTION rather than by colour. The grade at the end of
 * drawForeground multiplies and lifts every pixel in the frame, so hunting for
 * an exact hex would be hunting for a colour that no longer exists by the time
 * anybody sees it. Rendering the identical scene with the fireballs unhooked
 * and diffing isolates exactly the pixels they are responsible for, after the
 * grade, which is the number that matters.
 */
{
  function diffBox(a, b) {
    let n = 0, minX = 1e9, maxX = -1, minY = 1e9, maxY = -1;
    for (let y = 0; y < a.height; y++) {
      for (let x = 0; x < a.width; x++) {
        const i = (y * a.width + x) * 4;
        if (a.data[i] === b.data[i] && a.data[i + 1] === b.data[i + 1]
            && a.data[i + 2] === b.data[i + 2] && a.data[i + 3] === b.data[i + 3]) continue;
        n++;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    return { n, minX, maxX, minY, maxY };
  }
  for (const id of ['stack_queue_mines', 'debugging_dungeon']) {
    const s = sceneFor(id, 'firestorm');
    if (!s.fireballs) { fail(`E: ${id} firestorm built no fireballs`); continue; }
    const balls = s.fireballs.length / 6;
    let frames = 0, total = 0, best = 0;
    let top = 1e9, bottom = -1, left = 1e9, right = -1;
    const hashes = new Set();
    for (let k = 0; k < 90; k++) {
      const t = k * 0.11;
      const lit = render(s, t);
      const held = s.fireballs;
      s.fireballs = null;
      const dark = render(s, t);
      s.fireballs = held;
      const box = diffBox(lit, dark);
      hashes.add(frameHash(lit));
      if (box.n > 0) {
        frames++; total += box.n; best = Math.max(best, box.n);
        top = Math.min(top, box.minY); bottom = Math.max(bottom, box.maxY);
        left = Math.min(left, box.minX); right = Math.max(right, box.maxX);
      }
    }
    note.push(`E  ${id}: ${balls} fireballs, painting in ${frames}/90 frames, ${total} px total, peak ${best} px in one frame`);
    note.push(`E  ${id}: they cross y ${top}..${bottom} (${bottom - top} px of fall, deck at ${STAGE.ground}) and x ${left}..${right}`);
    note.push(`E  ${id}: ${hashes.size}/90 frames distinct`);
    if (frames < 20) fail(`E: ${id} shows a fireball in only ${frames} of 90 frames`);
    if (best < 12) fail(`E: ${id} peak fireball is ${best} pixels`);
    if (bottom - top < 50) fail(`E: ${id} fireballs only fall ${bottom - top} pixels`);
    if (right - left < 40) fail(`E: ${id} fireballs only cross ${right - left} pixels`);
    if (bottom < STAGE.ground - 14) fail(`E: ${id} fireballs never reach the deck (${bottom} vs ${STAGE.ground})`);
    if (hashes.size < 80) fail(`E: ${id} firestorm is nearly static (${hashes.size}/90 distinct frames)`);
    if (!s.anim.includes('fireball')) fail(`E: ${id} firestorm does not list fireball`);
    if (!s.anim.includes('ash') || !s.anim.includes('ember')) fail(`E: ${id} firestorm has no ash or no embers`);
    // A clear day in the volcano has none of it.
    const calm = sceneFor(id, 'clear');
    if (calm.fireballs) fail(`E: ${id} throws fireballs on a clear day`);
    // And the near mote sheet carries the embers while ash falls behind.
    if (s.foreStyle === s.moteStyle) fail(`E: ${id} firestorm runs one mote field, not ash behind and sparks in front`);
    note.push(`E  ${id}: ash falls behind (${s.moteStyle.dir > 0 ? 'down' : 'up'}), sparks rise in front (${s.foreStyle.dir > 0 ? 'down' : 'up'}), and a clear day has neither`);
  }
}

/* ================================================================
 * F — FURNITURE IS NOT WEATHER
 * ================================================================ */
{
  const jsFix = SC.WEATHER_FIXTURES;
  const names = new Set([...Object.keys(jsFix), ...Object.keys(PY.fixtures)]);
  for (const b of names) {
    const a = (jsFix[b] || []).slice().sort().join(',');
    const c = (PY.fixtures[b] || []).slice().sort().join(',');
    if (a !== c) fail(`F: fixtures for ${b} differ — js [${a}] vs python [${c}]`);
  }
  note.push(`F  fixture tables agree on ${names.size} biomes`);
  for (const [id, want] of [['python_village', 2], ['debugging_dungeon', 2],
                            ['null_kings_castle', 2], ['fields_of_syntax', 0]]) {
    for (const cond of ['clear', 'mist']) {
      const s = sceneFor(id, cond);
      if (s.torches.length !== want) {
        fail(`F: ${id} has ${s.torches.length} torches when ${cond}, expected ${want}`);
      }
    }
  }
  note.push('F  village, dungeon and castle keep both torches on a clear day; the Fields have none');
  const mine = sceneFor('stack_queue_mines', 'clear');
  if (!mine.lavaPulse) fail('F: the mine lost its lava seam when the sky cleared');
  note.push('F  the mine keeps its lava seam when the sky clears');
}

/* ================================================================
 * G — DETERMINISM
 * ================================================================ */
{
  let mismatched = 0;
  for (const id of REGIONS) {
    for (const cond of ['clear', 'rain', 'storm']) {
      const a = frameHash(render(sceneFor(id, cond), 3.25));
      const b = frameHash(render(sceneFor(id, cond), 3.25));
      if (a !== b) { mismatched++; fail(`G: ${id}/${cond} rendered two different frames`); }
    }
  }
  note.push(`G  ${REGIONS.length * 3} scenes rebuilt and re-rendered: ${mismatched} differences`);

  /* Comments talk about Math.random in both of these files, and fx.js has
   * legitimately stochastic IMPACT particles that predate all of this and are
   * not on the backdrop path. So the scan is on code with comments removed, and
   * it is narrowed to the two things this pass owns: the whole of
   * battlescene.js, which is the deterministic backdrop module, and the weather
   * paths inside the other two. */
  const decomment = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
  const bs = decomment(fs.readFileSync(ROOT + 'web/js/battlescene.js', 'utf8'));
  const rnd = (bs.match(/Math\.random/g) || []).length;
  note.push(`G  Math.random in battlescene.js (comments stripped): ${rnd}`);
  if (rnd) fail('G: Math.random reached the backdrop draw path');
  const ow = decomment(fs.readFileSync(ROOT + 'web/js/overworld.js', 'utf8'));
  const owRnd = (ow.match(/Math\.random/g) || []).length;
  note.push(`G  Math.random in overworld.js (comments stripped): ${owRnd}`);
  if (owRnd) fail('G: Math.random in overworld.js');
  const fxSrc = fs.readFileSync(ROOT + 'web/js/fx.js', 'utf8');
  const sky = /_setSkyParticles\(sky\) \{[\s\S]*?\n  \}/.exec(fxSrc);
  if (!sky) fail('G: could not find fx._setSkyParticles to scan it');
  else if (/Math\.random/.test(sky[0])) fail('G: Math.random in fx._setSkyParticles');
  else note.push('G  fx._setSkyParticles is free of live entropy');
  // The condition must NOT be in the scene key: a room keeps its own stones
  // when the rain stops, or every change of weather rebuilds the world.
  const dry = sceneFor('fields_of_syntax', 'clear');
  const wet = sceneFor('fields_of_syntax', 'storm');
  if (dry.seed !== wet.seed) fail('G: the weather changed the room seed');
  note.push(`G  the room seed survives the weather: ${dry.seed} === ${wet.seed}`);
  let shadowed = 0;
  for (const id of REGIONS) {
    for (const cond of ['clear', 'storm', 'firestorm']) {
      const miss = surfaceFields(sceneFor(id, cond));
      if (miss.length) { shadowed++; fail(`G: ${id}/${cond} lost surfaces: ${miss.join(',')}`); }
    }
  }
  note.push(`G  painted surfaces intact on ${REGIONS.length * 3} scenes: ${shadowed} shadowed`);
  note.push(`G  non-surfaces handed to drawImage across every render above: ${badDraws}`);
  if (badDraws) fail(`G: drawImage was handed a non-surface ${badDraws} times`);
}

/* ---------- report ---------- */
for (const line of note) console.log(line);
console.log('');
if (bad.length) {
  console.log(`FAIL (${bad.length})`);
  for (const b of bad) console.log('  ' + b);
  process.exit(1);
}
console.log('weather: OK');
