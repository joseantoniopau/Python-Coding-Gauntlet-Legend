/* Real CPU Canvas timings. This is not browser FPS or a full game-loop test.
 * GAUNTLET_CANVAS_MODULE=/path/to/@napi-rs/canvas node scripts/verify/render-budget.mjs
 * Each case gets a fresh process so its first-use cost is separate from warming.
 */
import fs from 'node:fs';
import os from 'node:os';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const self = fileURLToPath(import.meta.url);
const root = new URL('../../', import.meta.url);
const option = (key, fallback) => {
  const at = process.argv.indexOf(key);
  return at < 0 ? fallback : process.argv[at + 1];
};
const bounded = (key, fallback, low, high) => {
  const value = Number(option(key, fallback));
  if (!Number.isInteger(value) || value < low || value > high) throw Error(`${key} must be ${low}..${high}`);
  return value;
};
const samples = bounded('--samples', 480, 120, 2400);
const warmups = bounded('--warmups', 240, 120, 1200);
const cases = [
  'scene:all_regions',
  'battle:python_village:slime',
  'battle:array_caverns:behemoth',
  'battle:sliding_window_marsh:hydra',
  'battle:binary_tree_canopy:dragon',
  'battle:debugging_dungeon:demon',
  'battle:null_kings_castle:interviewer',
  'hero:all_classes_and_poses',
  'boss:all_archetypes',
  'cinema:forming_up',
  'cinema:the_world_is_not_restored',
  'cinema:the_one_you_teach',
  'cinema:freeze',
];
const round = value => Math.round(value * 10000) / 10000;
const delta = (a, b) => Object.fromEntries(Object.keys(a).map(key => [key, a[key] - b[key]]));
const worker = option('--worker', null);

if (!worker) {
  const rows = [];
  for (const id of cases) {
    const result = spawnSync(process.execPath, [self, '--worker', id, '--samples', String(samples), '--warmups', String(warmups)],
      {encoding:'utf8', env:process.env, timeout:60000, maxBuffer:4 * 1024 * 1024});
    if (result.status !== 0) throw Error(`${id}: ${result.stderr || result.error || result.stdout}`);
    const row = JSON.parse(result.stdout);
    rows.push(row);
    console.log(`${id.padEnd(44)} p50 ${row.warm.p50_ms.toFixed(3)} ms  p95 ${row.warm.p95_ms.toFixed(3)} ms  canvases +${row.warm.allocations.canvas_instances}  first use ${row.first_use.setup_ms.toFixed(1)} + ${row.first_use.draw_ms.toFixed(1)} ms`);
  }
  const hashFiles = ['web/js/battlescene.js', 'web/js/battlehero.js', 'web/js/bosses.js',
    'web/js/bossart.js', 'web/js/monsterart.js', 'web/js/sprites.js', 'web/js/cinema.js', 'web/art/cinematic-scenes.json'];
  const report = {
    generated_at:new Date().toISOString(),
    method:{
      renderer:'@napi-rs/canvas synchronous CPU raster; production module calls',
      samples_per_case:samples, warmup_draws_per_case:warmups,
      isolation:'Fresh Node process per case; module import, fixture setup and first draw excluded from warm samples.',
      clocks:'Per-draw elapsed time from performance.now; process CPU user+system time over the measured loop is reported separately.',
      sequence:'Deterministic 120-frame loop; cinematic samples remain inside the named authored beat.',
      allocations:'Counts Canvas instances created through document/OffscreenCanvas and getImageData calls/pixels. Does not measure all JavaScript/native heap allocation or resizing.',
      exclusions:['DOM layout', 'browser compositing', 'requestAnimationFrame scheduling', 'full BattleFX spell/particle/HUD layer', 'audio', 'grading', 'Python server work'],
      interpretation:'Frame-budget references are comparisons only. These timings do not establish browser FPS, responsiveness on other hardware, learning outcomes, or production readiness.',
    },
    machine:{node:process.version, platform:process.platform, arch:process.arch, os_release:os.release(), cpu:os.cpus()[0]?.model, logical_cpus:os.cpus().length},
    canvas_module:process.env.GAUNTLET_CANVAS_MODULE || '@napi-rs/canvas',
    source_sha256:Object.fromEntries(hashFiles.map(path => [path, createHash('sha256').update(fs.readFileSync(new URL(path, root))).digest('hex')])),
    rows,
  };
  const output = option('--output', '/private/tmp/gauntlet-render-budget.json');
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(`Evidence: ${output}`);
} else {
  if (!cases.includes(worker)) throw Error(`Unknown case ${worker}`);
  const importsAt = performance.now();
  const {createCanvas} = require(process.env.GAUNTLET_CANVAS_MODULE || '@napi-rs/canvas');
  const counts = {canvas_instances:0, image_data_reads:0, image_data_pixels:0};
  function canvas(width = 1, height = 1) {
    counts.canvas_instances++;
    const image = createCanvas(width, height), ctx = image.getContext('2d');
    const read = ctx.getImageData.bind(ctx);
    ctx.getImageData = (...args) => {
      counts.image_data_reads++;
      counts.image_data_pixels += Math.abs(Number(args[2]) * Number(args[3]));
      return read(...args);
    };
    ctx.imageSmoothingEnabled = false;
    return image;
  }
  globalThis.document = {createElement:tag => {
    if (tag !== 'canvas') throw Error(`Unexpected DOM allocation: ${tag}`);
    return canvas();
  }, body:{appendChild(){}}, documentElement:{style:{}}};
  globalThis.window = globalThis;
  globalThis.OffscreenCanvas = function(width, height) { return canvas(width, height); };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};
  globalThis.devicePixelRatio = 1;
  globalThis.matchMedia = () => ({matches:false, addEventListener(){}});
  const Stage = await import('../../web/js/battlescene.js');
  const Hero = await import('../../web/js/battlehero.js');
  const Boss = await import('../../web/js/bosses.js');
  const Monster = await import('../../web/js/monsterart.js');
  const Sprites = await import('../../web/js/sprites.js');
  const Cinema = await import('../../web/js/cinema.js');
  const module_import_ms = performance.now() - importsAt;
  const look = {class_id:'warden', body:'b', armor:{helmet:75, chestplate:75, boots:75, gauntlets:75, shield:75}};
  const [kind, id, enemy] = worker.split(':');
  const width = kind === 'cinema' ? 480 : 256, height = kind === 'cinema' ? 270 : 224;
  const target = canvas(width, height), ctx = target.getContext('2d');
  let draw, prepare = () => {}, dispose = () => {}, coverage;
  const setupCounts = {...counts}, setupAt = performance.now();
  const stageFor = region => Stage.createScene({region, biome:Monster.REGION_BIOME[region], key:`benchmark:${region}`, seed:7319, when:0});
  if (kind === 'scene') {
    const regions = Object.keys(Monster.REGION_BIOME), scenes = regions.map(stageFor);
    coverage = regions;
    draw = i => { const scene = scenes[i % scenes.length]; Stage.drawScene(ctx, scene, (i % 120) / 60); Stage.drawForeground(ctx, scene, (i % 120) / 60); };
    dispose = () => scenes.forEach(Stage.destroyScene);
  } else if (kind === 'battle') {
    const scene = stageFor(id), isBoss = enemy !== 'slime';
    coverage = {region:id, enemy, phase:isBoss ? 2 : null, hero_poses:Hero.COMBAT_POSES};
    prepare = () => { Hero.combatSet(look); if (isBoss) Boss.warmBoss(enemy, undefined, 2); };
    draw = i => {
      const t = (i % 120) / 60;
      Stage.drawScene(ctx, scene, t);
      Stage.drawFigureShadow(ctx, scene, 64, 42);
      ctx.drawImage(Hero.combatFrame(Hero.COMBAT_POSES[i % Hero.COMBAT_POSES.length], i % 2, look), 28, 79, 80, 96);
      if (isBoss) Boss.drawBoss(ctx, enemy, 184, 175, {time:t * 1000, phase:2});
      else { const image = Monster.monsterFrame(enemy, i % 2); ctx.drawImage(image, 172, 175 - image.height * 2, image.width * 2, image.height * 2); }
      Stage.drawForeground(ctx, scene, t);
    };
    dispose = () => Stage.destroyScene(scene);
  } else if (kind === 'hero') {
    const looks = Sprites.HERO_CLASSES.map(class_id => ({...look, class_id}));
    const frames = looks.flatMap(item => Hero.COMBAT_POSES.flatMap(pose => [0, 1].map(frame => ({item, pose, frame}))));
    coverage = {classes:Sprites.HERO_CLASSES, poses:Hero.COMBAT_POSES, frame_variants:frames.length};
    prepare = () => looks.forEach(item => Hero.combatSet(item));
    draw = i => { const f = frames[i % frames.length]; ctx.clearRect(0, 0, width, height); ctx.drawImage(Hero.combatFrame(f.pose, f.frame, f.item), 28, 79, 80, 96); };
  } else if (kind === 'boss') {
    const names = Boss.BOSS_ARCHETYPES;
    coverage = {archetypes:names, phase:2, frames:Boss.BOSS_FRAME_NAMES};
    prepare = () => names.forEach(name => Boss.warmBoss(name, undefined, 2));
    draw = i => { ctx.clearRect(0, 0, width, height); Boss.drawBoss(ctx, names[i % names.length], 184, 175,
      {time:(i % 120) / 60 * 1000, phase:2, frame:Math.floor(i / names.length) % Boss.BOSS_FRAME_COUNT}); };
  } else {
    const fixtures = JSON.parse(fs.readFileSync(new URL('../../web/art/cinematic-scenes.json', import.meta.url), 'utf8'));
    const scene = fixtures.scenes.find(row => row.id === 'pass_full').scene;
    const beat = scene.beats.find(row => row.id === id);
    if (!beat) throw Error(`No cinematic beat ${id}`);
    const film = Cinema.createCinema(scene, {look});
    coverage = {fixture:'pass_full', beat:id, duration_ms:beat.duration_ms, fixture_is_player_evidence:false};
    draw = i => film.draw(ctx, width, height, beat.at_ms + beat.duration_ms * (.1 + .8 * (i % 120) / 120));
    dispose = () => film.dispose();
  }
  const setup_ms = performance.now() - setupAt;
  const firstAt = performance.now(); draw(0); const first_draw_ms = performance.now() - firstAt;
  const firstAllocations = delta(counts, setupCounts);
  const warmupAt = performance.now(); prepare();
  for (let i = 0; i < warmups; i++) draw(i);
  const warmup_ms = performance.now() - warmupAt;
  const before = {...counts}, times = [], cpu = process.cpuUsage();
  for (let i = 0; i < samples; i++) { const at = performance.now(); draw(i); times.push(performance.now() - at); }
  const usage = process.cpuUsage(cpu), allocations = delta(counts, before);
  times.sort((a, b) => a - b);
  const quantile = fraction => round(times[Math.ceil(fraction * times.length) - 1]);
  const pixels = ctx.getImageData(0, 0, width, height).data;
  const output_sha256 = createHash('sha256').update(pixels).digest('hex');
  dispose();
  console.log(JSON.stringify({id:worker, width, height, coverage,
    first_use:{module_import_ms:round(module_import_ms), setup_ms:round(setup_ms), draw_ms:round(first_draw_ms), allocations:firstAllocations},
    warmup_ms:round(warmup_ms),
    warm:{samples, p50_ms:quantile(.5), p95_ms:quantile(.95), p99_ms:quantile(.99), max_ms:round(times.at(-1)),
      mean_ms:round(times.reduce((a, b) => a + b, 0) / times.length),
      process_cpu_ms:round((usage.user + usage.system) / 1000), allocations,
      over_16_67_ms:times.filter(value => value > 1000 / 60).length,
      over_33_33_ms:times.filter(value => value > 1000 / 30).length}, output_sha256}));
}
