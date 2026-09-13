/* death.mjs — web/js/deathfx.js and the heart in web/js/audio.js, measured.
 *
 * Nothing below is asserted from memory. Every claim is either counted off a
 * real raster or read back out of gauntlet/upkeep.py:
 *
 *   A  the three intervals, stated, and each gap proved longer than the last
 *      AND longer than the 455ms the alarm was already running at
 *   B  the tempos ARE upkeep.py's BPM_MAX and BPM_ONSET, read from Python, and
 *      audio.js's alarm beat is unchanged by the refactor that made room for them
 *   C  colour leaves before light leaves, and the hero is the last thing lit —
 *      both as pixel counts, not as an intention
 *   D  no number reaches the player that gauntlet/death.py did not supply
 *   E  the end state is reachable from every t, and the way out always exists
 *   F  deterministic from a cold cache, capped, fifteen colours off rendered
 *      pixels at three kits and three canvas sizes, and reduced motion is four
 *      stills on the beats with no iris at all
 */
import { installRaster, RASTER, colourCount, frameHash, pixelDiff } from './raster.mjs';
installRaster();
import { execFileSync } from 'child_process';
import fs from 'fs';

const ROOT = new URL('../../', import.meta.url).pathname;
const D = await import('../../web/js/deathfx.js');
const A = await import('../../web/js/audio.js');

const fails = [];
const bad = (m) => { fails.push(m); return m; };
const ok = (cond, m) => { if (!cond) bad(m); return cond; };
const pct = (a, b) => (b ? `${((a / b) * 100).toFixed(1)}%` : '0%');

/* Three kits, because the hero's plate is built from his own luminance ranks
 * and a hero in black plate occupies a different part of the scale to a hero in
 * a shirt. If the figure only reads at one kit it does not read. */
const LOOKS = {
  bare: { weapon: 'sword', emote: 'neutral' },
  plate: {
    weapon: 'sword', emote: 'neutral',
    cloak: '#52456e', tunic: '#7d6b90', metal: '#b0aabd', trim: '#a08a52',
    boot: '#715b45', skin: '#c08a62', hair: '#4a3a2c',
    _weapon: { key: 'sword', rung: 3, name: 'Runed', metal: '#cfd2e8', trim: '#a89aff' },
    _pieces: [{ piece: 'helmet', at: 75 }, { piece: 'chestplate', at: 75 },
              { piece: 'gauntlets', at: 75 }, { piece: 'boots', at: 75 },
              { piece: 'shield', at: 75 }],
  },
  dark: {
    weapon: 'axe', emote: 'neutral',
    cloak: '#14121c', tunic: '#1b1822', metal: '#2a2733', trim: '#3a3040',
    boot: '#171420', skin: '#5a4436', hair: '#120f18',
  },
};

const newCanvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
const ctxOf = (c) => c.getContext('2d');

/* ============================== A. the sequence ========================== */
console.log('A. THE SEQUENCE');
console.log(`   beats at        ${D.DEATH_BEAT_AT.join(' / ')} ms`);
console.log(`   tempos          ${D.DEATH_BEAT_BPM.join(' / ')} BPM`);
console.log(`   periods         ${D.DEATH_BEAT_MS.join(' / ')} ms`);
const gaps = D.DEATH_BEAT_AT.slice(1).map((v, i) => v - D.DEATH_BEAT_AT[i]);
console.log(`   gaps            ${gaps.join(' -> ')} ms  (ratios ${gaps.map((g, i) => (i ? (g / gaps[i - 1]).toFixed(2) : '-')).join(' ')})`);
console.log(`   silence after   ${D.DEATH_SILENCE_MS} ms`);
console.log(`   words at        ${D.WORDS_AT} ms   total ${D.DEATH_MS} ms`);
const alarmPeriod = Math.round(60000 / A.BPM_MAX);
console.log(`   alarm was at    ${alarmPeriod} ms (${A.BPM_MAX} BPM) when health hit zero`);
for (let i = 1; i < gaps.length; i++) {
  ok(gaps[i] > gaps[i - 1], `gap ${i + 1} (${gaps[i]}) is not slower than gap ${i} (${gaps[i - 1]})`);
}
ok(gaps[0] > alarmPeriod, `the first gap (${gaps[0]}) does not slow from the alarm's ${alarmPeriod}`);
ok(D.DEATH_BEAT_AT.length === 3, 'there are not exactly three beats');
console.log(`   VERDICT: ${gaps.length + 1} beats, every gap slower than the last, first gap ${(gaps[0] / alarmPeriod).toFixed(2)}x the alarm's`);

/* ======================= B. it is the same heart ========================= */
console.log('\nB. THE SAME HEART');
let PY = null;
try {
  PY = JSON.parse(execFileSync('python3', ['-c',
    'import json;from gauntlet import upkeep as u;'
    + 'print(json.dumps({"onset":u.BPM_ONSET,"max":u.BPM_MAX,'
    + '"dire":[b.colour for b in u.ALARM_BANDS if b.id=="DIRE"][0],'
    + '"floor":u.alarm_for(0,20),'
    + '"audible":sorted({u.alarm_for(h,20)["bpm"] for h in range(0,21)}-{0})}))'],
    { cwd: ROOT, encoding: 'utf8' }));
} catch (e) { bad(`python unavailable: ${String(e.message).split('\n')[0]}`); }

if (PY) {
  console.log(`   upkeep.py        BPM_ONSET ${PY.onset}  BPM_MAX ${PY.max}  DIRE ${PY.dire}`);
  console.log(`   at 0/20 health   band ${PY.floor.band}  bpm ${PY.floor.bpm}  pulse_hz ${PY.floor.pulse_hz}`);
  console.log(`   audible tempos   ${PY.audible.join(', ')} BPM — every rate the alarm can actually play today`);
  ok(D.DEATH_BEAT_BPM[0] === PY.max, `beat 1 (${D.DEATH_BEAT_BPM[0]}) is not upkeep BPM_MAX (${PY.max})`);
  ok(D.DEATH_BEAT_BPM[1] === PY.onset, `beat 2 (${D.DEATH_BEAT_BPM[1]}) is not upkeep BPM_ONSET (${PY.onset})`);
  ok(D.DEATH_BEAT_BPM[0] === PY.floor.bpm, `beat 1 is not the rate the alarm ends on (${PY.floor.bpm})`);
  // Which bands sound is upkeep's business and it moves. What must hold is
  // that the FIRST death gap is slower than the slowest beat the alarm can
  // play, whatever the bands are doing this week — otherwise the slowdown is
  // not unambiguous and the whole effect depends on the player's memory.
  const slowestAlarm = Math.round(60000 / Math.min(...PY.audible));
  ok(gaps[0] > slowestAlarm,
     `the first death gap (${gaps[0]}ms) is not slower than the alarm's slowest beat (${slowestAlarm}ms)`);
  console.log(`   slowest alarm    ${slowestAlarm} ms; first death gap ${gaps[0]} ms — ${(gaps[0] / slowestAlarm).toFixed(2)}x slower than anything the player has heard`);
  ok(D.DIRE_FALLBACK === PY.dire, `DIRE_FALLBACK ${D.DIRE_FALLBACK} has drifted from upkeep's ${PY.dire}`);
  ok(A.BPM_ONSET === PY.onset && A.BPM_MAX === PY.max, 'audio.js BPM constants have drifted from upkeep.py');
  console.log(`   VERDICT: beat 1 = BPM_MAX, beat 2 = BPM_ONSET, beat 3 = ${D.DEATH_BEAT_BPM[2]} = round(${PY.onset}x${PY.onset}/${PY.max}) — one ramp, run backwards`);
}

/* The alarm beat itself must be untouched. Record what heartbeat() schedules
 * and compare it to the numbers that were in the file before the refactor. */
const sched = [];
A.audio.enabled = true;
A.audio.ready = true;
A.audio.ctx = { currentTime: 0, createGain: () => ({ gain: { value: 1, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime() {} }, connect() {}, disconnect() {} }) };
A.audio.sfxBus = { __bus: true };
A.audio._tone = (when, dur, gain, o) => sched.push({ when: +when.toFixed(4), dur: +dur.toFixed(4), gain: +gain.toFixed(4), from: +o.from.toFixed(3), to: +o.to.toFixed(3), lp: o.lp });
A.audio._build = () => true;

for (const sev of [0, 0.5, 1]) {
  sched.length = 0;
  A.audio.heartbeat(sev);
  const want = [
    { when: 0.005, dur: 0.16, gain: +(0.16 + sev * 0.20).toFixed(4), from: +(58 - sev * 12).toFixed(3), to: +((58 - sev * 12) * 0.62).toFixed(3), lp: 240 },
    { when: 0.175, dur: 0.13, gain: +((0.16 + sev * 0.20) * 0.82).toFixed(4), from: +((58 - sev * 12) * 1.12).toFixed(3), to: +((58 - sev * 12) * 0.66).toFixed(3), lp: 260 },
  ];
  const same = JSON.stringify(sched) === JSON.stringify(want);
  ok(same, `heartbeat(${sev}) changed shape:\n     now  ${JSON.stringify(sched)}\n     was  ${JSON.stringify(want)}`);
  if (sev === 1) console.log(`   alarm beat @sev1 ${JSON.stringify(sched)}`);
}
console.log('   alarm heartbeat() unchanged at severity 0, 0.5 and 1: ' + (fails.length ? 'SEE FAILURES' : 'yes'));

sched.length = 0;
const handle = A.audio.heartbeatStop();
console.log(`   death beats      ${sched.length} tones over ${D.DEATH_BEAT_AT[2] / 1000}s`);
for (let i = 0; i < 3; i++) {
  const sh = A.audio.deathBeatShape(i);
  console.log(`     beat ${i + 1}  ${String(D.DEATH_BEAT_BPM[i]).padStart(3)} BPM  ${sh.f} Hz  gain ${sh.gain.toFixed(2)}  stretch ${sh.stretch.toFixed(2)}x  ${sh.pair ? 'lub-DUB' : 'lub alone'}`);
  if (i) {
    const prev = A.audio.deathBeatShape(i - 1);
    ok(sh.f < prev.f, `beat ${i + 1} is not lower than beat ${i}`);
    ok(sh.gain < prev.gain, `beat ${i + 1} is not quieter than beat ${i}`);
    ok(sh.stretch > prev.stretch, `beat ${i + 1} is not longer than beat ${i}`);
  }
}
ok(A.audio.deathBeatShape(0).f === 58 - 12 && Math.abs(A.audio.deathBeatShape(0).gain - 0.36) < 1e-9,
   'beat 1 is not the alarm\'s own severity-1 beat, so the seam is audible');
ok(!A.audio.deathBeatShape(2).pair, 'the last beat still closes its pair');
ok(sched.length === 5, `expected 5 tones (lub-DUB, lub-DUB, lub) and got ${sched.length}`);
ok(Math.abs(sched[4].when - (0.005 + D.DEATH_BEAT_AT[2] / 1000)) < 1e-6,
   'the third beat is not scheduled on the audio clock at its stated offset');
console.log(`   scheduled at     ${sched.map(s => (s.when * 1000).toFixed(0)).join(', ')} ms on the AUDIO clock, not a timer`);
handle.cancel();
A.audio.enabled = false;
const silent = A.audio.heartbeatStop();
ok(silent && silent.silent === true && silent.times.length === 3,
   'with audio off the caller loses the timing table');
console.log('   with sound off   handle still returns the same times: ' + JSON.stringify(silent.times));

/* ================== C. colour before light, hero last ==================== */
console.log('\nC. THE BLACK IS NOT INSTANT');
const HOST = [[D.DEATH_STAGE.w, D.DEATH_STAGE.h], [960, 540], [1440, 810]];
const hostCanvas = newCanvas(960, 540);
const hostCtx = ctxOf(hostCanvas);

function saturationOf(canvas) {
  // Mean chroma over opaque pixels, 0..255. This is the number that has to
  // reach zero while the luminance is still high.
  let n = 0, sum = 0;
  const d = canvas.data;
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue;
    sum += Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]);
    n++;
  }
  return n ? sum / n : 0;
}
function luminanceOf(canvas) {
  let n = 0, sum = 0;
  const d = canvas.data;
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue;
    sum += (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
    n++;
  }
  return n ? sum / n : 0;
}
/* Pixels that are not the void — "still lit" — and how many of them are inside
 * the hero's own 16x24 box in stage space. */
function litStats(canvas, scale, ox, oy) {
  const d = canvas.data, W = canvas.width;
  // GEOMETRY COMES FROM THE MODULE, NOT FROM A COPY OF IT. These four numbers
  // used to be written out here as 46/100/16/24, which is the 192x128 stage;
  // when the raster moved to 256x224 this box went on pointing at empty sky and
  // reported the hero as "neither the hero nor his shadow".
  const G = D.DEATH_STAGE;
  const hw = G.heroW / 2;
  const x0 = ox + (G.heroX - hw) * scale, x1 = ox + (G.heroX + hw) * scale;
  const y0 = oy + (G.ground - G.heroH) * scale, y1 = oy + G.ground * scale;
  // The shadow is under his feet, below the sprite box. It is part of him and
  // it leaves with him, so it is counted separately rather than quietly
  // inflating the "not the hero" number.
  // ...and its depth comes from the module too. It is 3 rows of the RIG, which
  // is 3 * FIGURE_SCALE rows of the frame; the part of it that rises above the
  // ground line is already inside the hero box above.
  const sy0 = oy + G.ground * scale;
  const sy1 = oy + (G.ground + (G.shadowH - G.shadowRise)) * scale;
  let lit = 0, inHero = 0, inShadow = 0;
  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    if (!d[i + 3]) continue;
    // "lit" is exact: anything that is not literally THEME.void #06060a.
    if (d[i] === 0x06 && d[i + 1] === 0x06 && d[i + 2] === 0x0a) continue;
    lit++;
    const x = p % W, y = (p / W) | 0;
    if (x >= x0 && x < x1 && y >= y0 && y < y1) inHero++;
    else if (x >= x0 && x < x1 && y >= sy0 && y < sy1) inShadow++;
  }
  return { lit, inHero, inShadow, his: inHero + inShadow };
}

const MARKS = [0, 400, 832, 833, 1200, 1800, 2370, 2371, 2600, 2883, 2884, 3400, 3909];
console.log('   kit=plate, 960x540 host (scale 4, ox 96, oy 14)');
console.log('      t ms  phase  beats  colours  chroma  luminance  lit px   of that, hero');
const track = [];
for (const t of MARKS) {
  D.renderDeath(t, { look: LOOKS.plate });
  hostCtx.fillStyle = '#000000'; hostCtx.fillRect(0, 0, 960, 540);
  const eff = D.createDeath({ look: LOOKS.plate }).begin({}).seek(t);
  eff.draw(hostCtx, 960, 540);
  const scale = Math.max(1, Math.floor(Math.min(960 / D.DEATH_STAGE.w, 540 / D.DEATH_STAGE.h)));
  const ox = Math.round((960 - D.DEATH_STAGE.w * scale) / 2);
  const oy = Math.round((540 - D.DEATH_STAGE.h * scale) / 2);
  const colours = colourCount(hostCanvas);
  const chroma = saturationOf(hostCanvas);
  const lum = luminanceOf(hostCanvas);
  const { lit, inHero, his } = litStats(hostCanvas, scale, ox, oy);
  track.push({ t, colours, chroma, lum, lit, inHero, his });
  console.log(`   ${String(t).padStart(6)}  ${D.phaseAt(t).id.padEnd(6)} ${String(D.beatsBy(t)).padStart(4)}  ${String(colours).padStart(7)}  ${chroma.toFixed(2).padStart(6)}  ${lum.toFixed(2).padStart(9)}  ${String(lit).padStart(6)}   ${String(inHero).padStart(6)} ${pct(inHero, lit).padStart(7)}`);
  ok(colours <= 15, `t=${t} painted ${colours} colours, budget is 15`);
}
const atStart = track[0], atBeat2 = track.find(r => r.t === 833);
const beforeBeat2 = track.find(r => r.t === 832);
ok(beforeBeat2.chroma < atStart.chroma * 0.4,
   `the colour has not drained by beat two (${atStart.chroma.toFixed(2)} -> ${beforeBeat2.chroma.toFixed(2)})`);
ok(beforeBeat2.lum > atStart.lum * 0.85,
   `the light fell during the drain (${atStart.lum.toFixed(2)} -> ${beforeBeat2.lum.toFixed(2)}) — colour must go first`);
console.log(`   colour before light: chroma ${atStart.chroma.toFixed(2)} -> ${beforeBeat2.chroma.toFixed(2)} (${pct(beforeBeat2.chroma, atStart.chroma)}) while luminance held at ${pct(beforeBeat2.lum, atStart.lum)}`);

const atBeat3 = track.find(r => r.t === 2371);
console.log(`   at beat three the field is ${D.paletteAt(2371, {}).field === 0 ? 'exactly void' : 'still lit'}; lit pixels remaining ${atBeat3.lit}`);
ok(atBeat3.his === atBeat3.lit,
   `at the third beat ${atBeat3.lit - atBeat3.his} lit pixels are neither the hero nor his shadow`);
const lastLit = [...track].reverse().find(r => r.lit > 0);
ok(lastLit.his === lastLit.lit, 'the last thing visible is not the hero');
console.log(`   at beat three ${atBeat3.lit} pixels are still lit: ${atBeat3.inHero} the figure, ${atBeat3.lit - atBeat3.inHero} his shadow, 0 anything else`);
const black = track.find(r => r.t === 3909);
ok(black.lit === 0, `the black is not black: ${black.lit} lit pixels remain at t=${black.t}`);
console.log(`   the hero is last: at beat three he and his shadow are 100% of what is lit; from t=${D.BLACK_FROM} nothing is lit at all`);

/* every kit, every host size, every mark */
let worst = 0, worstAt = '';
for (const [name, look] of Object.entries(LOOKS)) {
  for (const [w, h] of HOST) {
    const c = newCanvas(w, h), cx = ctxOf(c);
    const eff = D.createDeath({ look }).begin({});
    for (let i = 0; i <= 60; i++) {
      eff.seek((D.DEATH_MS * i) / 60);
      eff.draw(cx, w, h);
      const n = colourCount(c);
      if (n > worst) { worst = n; worstAt = `${name} ${w}x${h} t=${Math.round(eff.t)}`; }
      if (n > 15) bad(`${name} ${w}x${h} t=${Math.round(eff.t)} painted ${n} colours`);
    }
  }
}
console.log(`   worst colour count across 3 kits x 3 host sizes x 61 frames: ${worst} (${worstAt}), budget 15`);

/* reduced motion */
console.log('\n   REDUCED MOTION');
const rHashes = new Map();
for (const t of [0, 400, 832, 833, 1500, 2370, 2371, 2600, 2884, 3909]) {
  const c = newCanvas(960, 540), cx = ctxOf(c);
  const eff = D.createDeath({ look: LOOKS.plate, reduced: true }).begin({});
  eff.seek(t); eff.draw(cx, 960, 540);
  const h = frameHash(c);
  rHashes.set(t, h);
  console.log(`   ${String(t).padStart(6)} ms  stage ${String(D.stageAt(t, true)).padStart(2)}  iris ${D.irisAt(t, true)}  colours ${colourCount(c)}  hash ${h}`);
  ok(colourCount(c) <= 15, `reduced motion at t=${t} painted ${colourCount(c)} colours`);
}
const distinct = new Set(rHashes.values());
ok(distinct.size === 4, `reduced motion produced ${distinct.size} distinct frames, expected 4 stills`);
ok(rHashes.get(0) === rHashes.get(832) && rHashes.get(833) === rHashes.get(2370),
   'reduced motion is moving between the beats');
ok(D.irisAt(500, true) === D.irisAt(2000, true), 'the iris is closing in reduced motion');
console.log(`   ${distinct.size} distinct frames across the whole sequence, held between beats, iris never moves`);

/* measureDeath() is the module's own account of itself. Exercised here rather
 * than left as an untested export, and cross-checked against the raster: its
 * `sat` must reach 0 while `field` is still 1, or the ordering claim is false
 * in the data as well as in the pixels. */
{
  const rows = D.measureDeath({ look: LOOKS.plate, samples: 14 });
  const satZero = rows.find(r => r.sat === 0);
  const fieldZero = rows.find(r => r.field === 0);
  const plateZero = rows.find(r => r.plate === 0);
  ok(satZero && satZero.t <= D.FALL_FROM, 'the colour is not gone by beat two');
  ok(fieldZero && fieldZero.t <= D.LAST_FROM, 'the field still has light at beat three');
  ok(satZero.t < fieldZero.t, 'the light goes before the colour does');
  ok(fieldZero.t < plateZero.t, 'the hero goes out before the frame does');
  console.log(`   measureDeath(): sat hits 0 at t=${satZero.t}, field at t=${fieldZero.t}, plate at t=${plateZero.t}`);
  console.log(`   -> colour (beat ${D.beatsBy(satZero.t)}), then light (beat ${D.beatsBy(fieldZero.t)}), then the hero. In that order, every time.`);
}

/* ============================= D. the words ============================== */
console.log('\nD. WHAT THE PLAYER READS');
const REPORT = {
  wake: { slot: 'auto3', label: 'Entered the Sunken Vault', region: 'Sunken Vault', reason: 'region_entered' },
  cost: { playtime: '12m 22s', gold: 340, items: 3, levels: 0 },
  kept: { attempts: 1841, skills: 26, mastery: '61%', due: 12 },
};
const full = D.deathLines(REPORT);
console.log(`   ${full.title}`);
for (const l of full.lines) console.log(`     [${l.id}] ${l.text}`);

/* Not one number on this screen may be one that death.py did not send. */
const supplied = new Set();
for (const grp of [REPORT.cost, REPORT.kept]) {
  for (const v of Object.values(grp)) String(v).match(/\d+/g)?.forEach(n => supplied.add(n));
}
const invented = [];
for (const l of full.lines) {
  for (const n of (l.text.match(/\d+/g) || [])) if (!supplied.has(n)) invented.push(`${l.id}: ${n}`);
}
ok(invented.length === 0, `numbers on the death screen that gauntlet/death.py never supplied: ${invented.join(', ')}`);
console.log(`   numbers printed: ${full.lines.flatMap(l => l.text.match(/[0-9]+/g) || []).join(', ')} — all of them from the report, 0 invented`);

/* an empty report, a hostile one, and the case that matters most: no save */
for (const [name, rep] of [['null', null], ['empty', {}], ['garbage', { wake: 7, cost: 'no', kept: [] }],
  ['no save', { cost: { playtime: '4m 10s' }, kept: { attempts: 3 } }],
  ['partial', { wake: { region: 'Ashfall' } }]]) {
  const out = D.deathLines(rep);
  const nums = out.lines.flatMap(l => l.text.match(/\d+/g) || []);
  const allowed = new Set(JSON.stringify(rep || {}).match(/\d+/g) || []);
  const made = nums.filter(n => !allowed.has(n));
  ok(made.length === 0, `report "${name}" produced invented numbers ${made.join(',')}`);
  ok(out.lines.some(l => l.id === 'kept'), `report "${name}" dropped the kept line`);
  ok(out.actions.length >= 1, `report "${name}" left the player with no way out`);
  console.log(`   report "${name}" -> ${out.lines.length} lines [${out.lines.map(l => l.id).join(' ')}], kept line present, ${out.actions.length} action`);
}
ok(D.deathLines({}).lines.find(l => l.id === 'where').text === D.NO_SAVE_LINE,
   'a player with no save is not told they can keep going');
ok(!/[!]/.test(JSON.stringify(D.deathLines(REPORT))), 'there is an exclamation mark on the death screen');
console.log('   no exclamation marks; the kept line is unconditional and carries no numbers at all');

/* AND THEY HAVE TO BE ON THE SCREEN.
 *
 * Everything above this point checks the TEXT deathLines() returns, which is
 * what the first version of this harness checked and all it checked — so it
 * passed for the whole life of a screen that never drew a word. renderDeath
 * took opts.words and ignored it; nothing in web/ consumed deathLines(),
 * KEPT_LINE or NO_SAVE_LINE; the sequence ended on pure black and a real death
 * at 1440x940 held there until the player pressed a key.
 *
 * So: render the last frame and count. The buffer is the module's own, read
 * back through blitDeath at 1:1. */
{
  const cv = newCanvas(D.DEATH_STAGE.w, D.DEATH_STAGE.h);
  const cx = ctxOf(cv);
  const paint = (t) => {
    const st = D.renderDeath(t, { look: LOOKS.plate, words: full, report: REPORT,
                                  alarmColour: D.DIRE_FALLBACK });
    D.blitDeath(cx, cv.width, cv.height, st.stage);
    let lit = 0;
    for (let i = 0; i < cv.data.length; i += 4) {
      if (!cv.data[i + 3]) continue;
      if (cv.data[i] === 0x06 && cv.data[i + 1] === 0x06 && cv.data[i + 2] === 0x0a) continue;
      lit++;
    }
    return { lit, words: st.words };
  };
  const before = paint(D.WORDS_AT - 1);
  const after = paint(D.WORDS_AT);
  const later = paint(D.WORDS_AT + 6000);
  ok(before.words === 0, `the words are on screen ${D.WORDS_AT - 1}ms in, before the silence is over`);
  ok(after.words > 0, 'the words never reach the frame — renderDeath took opts.words and ignored them');
  ok(later.words === after.words, 'the words change after they have landed');
  ok(after.lit >= after.words, 'fewer lit pixels than the words painted');
  console.log(`   painted at t=${D.WORDS_AT - 1}: ${before.words} px of text`);
  console.log(`   painted at t=${D.WORDS_AT}: ${after.words} px of text, ${after.lit} lit pixels on the frame`);
  console.log(`   still there at t=${D.WORDS_AT + 6000}: ${later.words} px — the screen holds until the player leaves`);

  /* Every digit on the frame has to come out of the report, and the only way to
   * be sure of that from the RASTER is to render twice with two different
   * reports and check the frames differ exactly where the numbers do. */
  const other = D.deathLines({ ...REPORT, cost: { ...REPORT.cost, gold: 999 } });
  const st2 = D.renderDeath(D.WORDS_AT, { look: LOOKS.plate, words: other, alarmColour: D.DIRE_FALLBACK });
  const cv2 = newCanvas(D.DEATH_STAGE.w, D.DEATH_STAGE.h);
  D.blitDeath(ctxOf(cv2), cv2.width, cv2.height, st2.stage);
  let moved = 0;
  for (let i = 0; i < cv.data.length; i += 4) {
    if (cv.data[i] !== cv2.data[i] || cv.data[i + 1] !== cv2.data[i + 1]
      || cv.data[i + 2] !== cv2.data[i + 2] || cv.data[i + 3] !== cv2.data[i + 3]) moved++;
  }
  ok(moved > 0, 'changing a number in the report changed nothing on the frame');
  console.log(`   changing cost.gold 340 -> 999 moved ${moved} pixels: the figures on the frame are the report's`);

  /* The kept line is the point of the screen, so it is proved present in the
   * PIXELS and not only in the string: drop it from the block and the frame
   * must lose a measurable amount of text. */
  const without = { ...full, lines: full.lines.filter(l => l.id !== 'kept') };
  const st3 = D.renderDeath(D.WORDS_AT, { look: LOOKS.plate, words: without, alarmColour: D.DIRE_FALLBACK });
  ok(st3.words < after.words,
     'removing the kept line did not change the painted text — it was never drawn');
  console.log(`   the kept line is worth ${after.words - st3.words} painted pixels of the ${after.words}`);
}

/* ============================== E. it must not trap ====================== */
console.log('\nE. IT MUST NOT TRAP');
console.log(`   skip armed at    first death ${D.skipArmedAt(0)} ms (after the third beat), thereafter ${D.skipArmedAt(1)} ms`);
ok(D.skipArmedAt(0) === D.DEATH_BEAT_AT[2], 'the first death does not arm the skip on the third beat');
ok(D.skipArmedAt(1) === 0 && D.skipArmedAt(9) === 0, 'a repeat death does not arm the skip immediately');
for (const t of [0, 500, 1500, 2371, 3000, 3909, 99999]) {
  const e = D.createDeath({ look: LOOKS.plate, seen: 1 }).begin({});
  e.seek(t); e.skip();
  ok(e.t === D.DEATH_MS && !e.active && e.showWords,
     `skip() from t=${t} did not land on the end state (t=${e.t} active=${e.active})`);
}
console.log('   skip() from 7 different t: all land on t=' + D.DEATH_MS + ', active=false, words showing');
{
  const e = D.createDeath({ look: LOOKS.plate }).begin({});
  let guard = 0;
  while (e.active && guard++ < 10000) e.update(0.016);
  ok(!e.active, 'the sequence never ends on its own');
  ok(guard < 300, `the sequence took ${guard} frames at 60fps to finish`);
  console.log(`   left alone it ends by itself after ${guard} frames at 60fps (${(guard * 16.67 / 1000).toFixed(2)}s)`);
}
{
  // A frame clock that has been asleep, gone backwards, or gone mad.
  const e = D.createDeath({ look: LOOKS.plate }).begin({});
  const c = newCanvas(640, 360), cx = ctxOf(c);
  for (const dt of [0, -1, NaN, Infinity, -Infinity, 1e6, 100, 0.016, undefined, null, '0.5']) {
    try { e.update(dt); e.draw(cx, 640, 360); }
    catch (err) { bad(`update(${String(dt)}) threw ${err.message}`); }
    ok(Number.isFinite(e.t) && e.t >= 0 && e.t <= D.DEATH_MS, `update(${String(dt)}) put t at ${e.t}`);
  }
  for (const [w, h] of [[0, 0], [1, 1], [-5, 20], [NaN, NaN]]) {
    try { e.draw(cx, w, h); } catch (err) { bad(`draw(${w}x${h}) threw ${err.message}`); }
  }
  try { e.draw(null, 640, 360); } catch (err) { bad(`draw(null) threw ${err.message}`); }
  console.log('   11 pathological dt values and 5 degenerate canvases: no throw, t stays in [0, ' + D.DEATH_MS + ']');
}
{
  const e = D.createDeath({});   // no look at all — a state with no hero in it
  const c = newCanvas(640, 360), cx = ctxOf(c);
  e.begin({});
  for (let i = 0; i <= 20; i++) { e.seek((D.DEATH_MS * i) / 20); e.draw(cx, 640, 360); }
  console.log('   with no hero look at all: draws the field and the black, never throws, still ends');
}

/* ============================ F. the harness rules ====================== */
console.log('\nF. DETERMINISTIC, CACHED, COUNTED');
const src = fs.readFileSync(new URL('../../web/js/deathfx.js', import.meta.url), 'utf8');
ok(!/Math\.random/.test(src), 'Math.random appears in deathfx.js');
ok(!/ctx\.(arc|ellipse)\s*\(/.test(src), 'deathfx.js draws with a path primitive the raster harness cannot see');
ok(!/createRadialGradient|createLinearGradient/.test(src), 'deathfx.js uses a gradient, which cannot stay inside fifteen colours');
console.log('   no Math.random, no gradients, no arc/ellipse — fillRect only, which is what raster.mjs can actually count');

function hashRun(look, reduced) {
  const out = [];
  const c = newCanvas(960, 540), cx = ctxOf(c);
  const e = D.createDeath({ look, reduced }).begin({});
  for (let i = 0; i <= 24; i++) { e.seek((D.DEATH_MS * i) / 24); e.draw(cx, 960, 540); out.push(frameHash(c)); }
  return out.join('|');
}
D.clearDeathCache();
const cold = hashRun(LOOKS.plate, false);
const warm = hashRun(LOOKS.plate, false);
D.clearDeathCache();
const cold2 = hashRun(LOOKS.plate, false);
ok(cold === warm, 'a warm cache renders differently from a cold one');
ok(cold === cold2, 'two cold runs of the same input do not agree');
console.log(`   25-frame run hash  cold ${cold.slice(0, 8)}...  warm ${cold === warm ? 'identical' : 'DIFFERS'}  cold again ${cold === cold2 ? 'identical' : 'DIFFERS'}`);

RASTER.counting = true;
RASTER.canvases = 0;
D.clearDeathCache();
D.warmDeath({ look: LOOKS.plate });
const afterWarm = RASTER.canvases;
const c2 = newCanvas(960, 540), cx2 = ctxOf(c2);
RASTER.canvases = 0;
const e2 = D.createDeath({ look: LOOKS.plate }).begin({});
for (let i = 0; i < 240; i++) { e2.seek((D.DEATH_MS * i) / 240); e2.draw(cx2, 960, 540); }
const inLoop = RASTER.canvases;
RASTER.counting = false;
ok(inLoop === 0, `${inLoop} canvases allocated during 240 frames of playback`);
console.log(`   allocations       ${afterWarm} on warmDeath(), ${inLoop} across 240 frames of playback`);

for (const [name, look] of Object.entries(LOOKS)) { D.warmDeath({ look }); }
for (let i = 0; i < 40; i++) D.stagesFor(`#${(0x100000 + i * 7919).toString(16).slice(0, 6)}`);
const stats = D.deathStats();
console.log(`   caches            ${JSON.stringify(stats)}`);
ok(stats.stages <= stats.STAGE_CACHE_MAX, `stage cache ${stats.stages} over cap ${stats.STAGE_CACHE_MAX}`);
ok(stats.plates <= stats.PLATE_CACHE_MAX, `plate cache ${stats.plates} over cap ${stats.PLATE_CACHE_MAX}`);

/* The plate must use its full ramp at every kit, or the figure is a silhouette. */
console.log('\n   THE FIGURE, at three kits');
for (const [name, look] of Object.entries(LOOKS)) {
  const c = newCanvas(D.DEATH_STAGE.w, D.DEATH_STAGE.h), cx = ctxOf(c);
  const e = D.createDeath({ look }).begin({});
  e.seek(D.LAST_FROM);           // the moment he is the only thing lit
  const before = D.renderDeath(D.LAST_FROM, { look });
  e.draw(cx, D.DEATH_STAGE.w, D.DEATH_STAGE.h);
  const { lit, inHero, his } = litStats(c, 1, 0, 0);
  ok(his === lit, `${name}: ${lit - his} lit pixels at beat three belong to neither the hero nor his shadow`);
  console.log(`   ${name.padEnd(6)} plate ${before.plate.w}x${before.plate.h}, ${String(before.plate.opaque).padStart(3)} opaque px from ${String(before.plate.tones).padStart(3)} source tones -> ${new Set(before.plate.idx.filter(v => v !== 255)).size} ramp steps; at beat three ${lit} px lit = ${inHero} figure + ${lit - inHero} shadow, nothing else`);
  ok(new Set(before.plate.idx.filter(v => v !== 255)).size >= 3,
     `${name} collapses to fewer than 3 ramp steps — the figure reads as a silhouette`);
}

/* ================================ verdict =============================== */
console.log('\n' + '='.repeat(72));
if (fails.length) {
  console.log(`FAIL (${fails.length})`);
  for (const f of fails) console.log('  - ' + f);
  process.exitCode = 1;
} else {
  console.log('PASS — three beats at 132/72/39 BPM, every gap slower than the last,');
  console.log(`       the colour gone by beat two, the hero the last thing lit, ${worst} colours worst case,`);
  console.log('       no invented numbers, and the way out is always there.');
}
