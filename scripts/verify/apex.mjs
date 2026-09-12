/* The seam between gauntlet/hunters.py and web/js/bosses.js, measured.
 *
 * hunters.py authors seventeen apex hunters and gives each one TWO sprite keys:
 *
 *   sprite            a NEW key. Nobody has drawn it. It is a promise.
 *   sprite_fallback   an existing bosses.js archetype that resolves TODAY, so
 *                     the creature has a face the hour it is wired in
 *
 * That split is the only reason a gameplay pass can ship a monster before an
 * art pass has drawn it, and it is worth exactly nothing unless somebody checks
 * both halves. So:
 *
 *   RESOLVES    every fallback resolves to ITSELF through bosses.resolveBoss.
 *               resolveBoss defaults to 'titan' for anything it does not know,
 *               which means a typo does not throw — it silently ships the wrong
 *               monster. Comparing the answer to the question is the whole test
 *   DRAWS       every fallback renders a real image at every one of the five
 *               boss frames, in every phase, with no null canvas
 *   DISCIPLINE  no frame exceeds fifteen colours (docs/08-art-direction.md)
 *   DISTINCT    two apexes that share a fallback are DECLARED in
 *               hunters.SPRITE_FALLBACK_REPEATS. Seventeen creatures over
 *               fifteen archetypes means three pairs share until somebody draws
 *               the real ones; an UNDECLARED collision is the defect
 *   UNAUTHORED  every proposed new key is still absent from bosses.js. When one
 *               appears, this says so, and hunters.py should stop falling back
 *
 * Run: node scripts/verify/apex.mjs
 */
import { installRaster, colourCount, silhouetteDiff } from './raster.mjs';
installRaster();
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const B = await import('../../web/js/bosses.js');

/* The roster, from Python rather than from a copy of it that can go stale. */
let roster = null, rosterError = null, check = null;
try {
  const out = execFileSync('python3', ['-c',
    'import json,sys;sys.path.insert(0,".");from gauntlet import hunters;'
    + 'print(json.dumps({"apexes":[{k:a.to_dict()[k] for k in '
    + '("id","name","region","element","sprite","sprite_fallback","colour")} '
    + 'for a in hunters.APEXES],'
    + '"repeats":list(hunters.SPRITE_FALLBACK_REPEATS),'
    + '"check":hunters.self_check()["ok"]}))'],
    { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 26 });
  const parsed = JSON.parse(out);
  roster = parsed.apexes;
  check = { repeats: parsed.repeats, ok: parsed.check };
} catch (e) { rosterError = String(e.message || e).slice(0, 400); }

const fail = [];
const note = (m) => fail.push(m);

if (!roster) {
  console.log(JSON.stringify({ ok: false, rosterError }, null, 1));
  process.exit(1);
}

/* ---------------- 1. fallbacks resolve to themselves ---------------- */
let unresolved = 0;
for (const a of roster) {
  const got = B.resolveBoss(a.sprite_fallback);
  if (got !== a.sprite_fallback) {
    unresolved++;
    note(`${a.id}: fallback '${a.sprite_fallback}' resolved to '${got}'`);
  }
}

/* ---------------- 2. every fallback actually draws ---------------- */
let drawn = 0, overPalette = 0;
const maxColours = {};
for (const a of roster) {
  for (let f = 0; f < B.BOSS_FRAME_COUNT; f++) {
    for (let p = 0; p < B.BOSS_PHASE_COUNT; p++) {
      let img;
      try { img = B.bossSprite(a.sprite_fallback, a.colour, f, p); }
      catch (e) { note(`${a.id}: bossSprite THREW ${e.message}`); continue; }
      if (!img || !img.width || !img.height) {
        note(`${a.id}: frame ${f} phase ${p} -> bad image`);
        continue;
      }
      drawn++;
      const n = colourCount(img);
      maxColours[a.id] = Math.max(maxColours[a.id] || 0, n);
    }
  }
  if ((maxColours[a.id] || 0) > 15) {
    overPalette++;
    note(`${a.id}: ${maxColours[a.id]} colours in a frame, budget is 15`);
  }
}

/* ---------------- 3. shared fallbacks are declared ---------------- */
const byFallback = {};
for (const a of roster) (byFallback[a.sprite_fallback] ||= []).push(a.id);
const collisions = Object.entries(byFallback).filter(([, v]) => v.length > 1);
const declared = new Set(check.repeats);
const undeclared = collisions.filter(([k]) => !declared.has(k));
for (const [k, v] of undeclared) note(`undeclared shared fallback '${k}': ${v.join(', ')}`);

/* Distinct fallbacks must actually look distinct, or the split bought nothing. */
const silhouettes = {};
for (const key of new Set(roster.map(a => a.sprite_fallback))) {
  silhouettes[key] = B.bossSprite(key, '#c43f4f', 0, 0);
}
const keys = Object.keys(silhouettes);
let identicalPairs = 0;
for (let i = 0; i < keys.length; i++) {
  for (let j = i + 1; j < keys.length; j++) {
    if (silhouetteDiff(silhouettes[keys[i]], silhouettes[keys[j]]) === 0) {
      identicalPairs++;
      note(`'${keys[i]}' and '${keys[j]}' have identical silhouettes`);
    }
  }
}

/* ---------------- 4. the promised keys are still promises ---------------- */
const authored = roster.filter(a => B.BOSS_ARCHETYPES.includes(a.sprite));
const stillFallingBack = authored.map(a => a.id);
for (const id of stillFallingBack) {
  note(`${id}: its real sprite EXISTS in bosses.js now — stop using the fallback`);
}

const out = {
  ok: fail.length === 0 && check.ok,
  pythonSelfCheck: check.ok,
  apexes: roster.length,
  archetypesAvailable: B.BOSS_ARCHETYPES.length,
  framesDrawn: drawn,
  fallbacksUnresolved: unresolved,
  overPaletteBudget: overPalette,
  maxColoursSeen: Math.max(0, ...Object.values(maxColours)),
  sharedFallbacks: collisions.map(([k, v]) => `${k}: ${v.join(' + ')}`),
  undeclaredCollisions: undeclared.length,
  identicalSilhouettePairs: identicalPairs,
  newKeysNowAuthored: stillFallingBack,
  failures: fail,
};
console.log(JSON.stringify(out, null, 1));
process.exit(out.ok ? 0 : 1);
