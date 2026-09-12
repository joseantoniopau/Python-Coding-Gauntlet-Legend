/* The seam between gauntlet/pets.py and web/js/petart.js, measured.
 *
 * This is the check that was missing, and its absence is exactly why the
 * companion shipped with half its tier ladder invisible. companion.mjs proves
 * the FOLLOW — that an animal walks behind you, keeps station and arrives with
 * you through a load. It cannot prove that the animal it is drawing is the
 * animal the roster asked for, because it drives the overworld with its own
 * two-row fixture and never reads pets.py at all.
 *
 * So this reads the live roster out of Python and puts one number on each half
 * of the contract:
 *
 *   SPRITE   every `sprite` string pets.py ships resolves to an authored animal
 *            in petart.js, and the ones that fall back do so on purpose, by an
 *            entry in PET_ALIAS rather than by dropping off the end of it
 *   TIER     every `tier` string pets.py ships resolves to its own art tier and
 *            renders a frame no other tier renders. A ladder whose middle three
 *            rungs are byte-identical is not a ladder, and the roster is the
 *            only place the real rung names exist
 *
 * pets.py is rewritten often. When it grows an animal or a rank, this fails
 * with the name of the thing nobody has drawn yet, which is the whole point.
 */
import { installRaster, frameHash, colourCount, silhouetteDiff } from './raster.mjs';
installRaster();
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const PA = await import('../../web/js/petart.js');

/* The roster, from the source of truth rather than from a copy of it that can
 * go stale the moment somebody edits Python. */
let roster = null, rosterError = null;
try {
  roster = JSON.parse(execFileSync('python3', ['-c',
    'import json,sys;sys.path.insert(0,".");from gauntlet import pets;'
    + 'print(json.dumps([{k:r[k] for k in ("id","species","sprite","colour","tier")}'
    + ' for r in pets.catalogue()]))'], { cwd: ROOT, encoding: 'utf8' }));
} catch (e) { rosterError = String(e.message).split('\n')[0]; }

const fail = [];
const note = (m) => fail.push(m);
const out = { rosterRows: roster ? roster.length : null, rosterError };
if (!roster) {
  note('could not read gauntlet/pets.py — the contract is unverifiable, not passing');
  console.log(JSON.stringify(out, null, 1));
  process.exit(1);
}

/* ---------------- SPRITE: every animal the roster names ---------------- */
{
  const rows = [], unaliased = [];
  for (const r of roster) {
    const key = String(r.sprite || '').toLowerCase().trim();
    const drawn = PA.petKeyFor(r.sprite);
    // Landing on the fallback is fine; landing on it by ACCIDENT is not. An
    // explicit alias is somebody's decision that this animal reads as that one;
    // falling off the end of the table is nobody's.
    const deliberate = PA.PET_ANIMALS.indexOf(key) >= 0 || key in PA.PET_ALIAS;
    if (!deliberate) unaliased.push(`${r.id} (sprite "${r.sprite}")`);
    const img = PA.petFrame(r.sprite, 'right', 0, { colour: r.colour, tier: r.tier });
    rows.push({ id: r.id, sprite: r.sprite, drawnAs: drawn,
                aliased: deliberate ? (PA.PET_ANIMALS.indexOf(key) >= 0 ? 'authored' : 'alias')
                                    : 'FELL THROUGH',
                colours: colourCount(img) });
  }
  out.sprites = rows;
  out.spritesWithNoEntryInTheTable = unaliased;
  const over = rows.filter(r => r.colours > 15);
  out.coloursOverBudget = over;
  if (unaliased.length) {
    note(`pets.py ships ${unaliased.length} sprite(s) petart.js has never heard of, `
       + `so they render as the fallback by accident: ${unaliased.join(', ')}`);
  }
  if (over.length) note(`over the fifteen-colour budget: ${JSON.stringify(over)}`);
}

/* ---------------- TIER: every rank, and no two the same ---------------- */
{
  const tiers = [...new Set(roster.map(r => r.tier))];
  const rows = [], byHash = {};
  for (const t of tiers) {
    const art = PA.petTierKey(t);
    // A rank nobody mapped resolves to COMMON, silently and identically to the
    // rank below it. Named, so the failure says which rung vanished.
    const known = art !== 'COMMON' || String(t).toUpperCase().trim() === 'COMMON'
                  || (String(t).toUpperCase().trim() in PA.PET_TIER_ALIAS);
    const img = PA.petFrame('jaguar', 'right', 0, { tier: t });
    const h = frameHash(img);
    (byHash[h] ??= []).push(t);
    rows.push({ pyTier: t, artTier: art, mapped: known, frameHash: h.slice(0, 8) });
  }
  out.tiers = rows;
  const unmapped = rows.filter(r => !r.mapped).map(r => r.pyTier);
  const collided = Object.values(byHash).filter(v => v.length > 1);
  out.tiersWithNoEntryInTheTable = unmapped;
  out.tiersRenderingIdentically = collided;
  out.distinctTierFrames = `${Object.keys(byHash).length} of ${tiers.length}`;
  if (unmapped.length) {
    note(`pets.py ranks with no entry in PET_TIER_ALIAS, silently drawn as COMMON: `
       + unmapped.join(', '));
  }
  if (collided.length) {
    note(`ranks that render byte-identically, so the ladder is invisible: `
       + JSON.stringify(collided));
  }
}

/* ---------------- and the shapes, at the size they are seen ------------ */
{
  const keys = PA.PET_ANIMALS;
  const imgs = keys.map(k => PA.petFrame(k, 'right', 0, { tier: 'COMMON' }));
  const downs = keys.map(k => PA.petFrame(k, 'down', 0, { tier: 'COMMON' }));
  let worst = Infinity, worstPair = null, worstDown = Infinity, worstDownPair = null;
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const d = silhouetteDiff(imgs[i], imgs[j]);
      if (d < worst) { worst = d; worstPair = [keys[i], keys[j]]; }
      const dd = silhouetteDiff(downs[i], downs[j]);
      if (dd < worstDown) { worstDown = dd; worstDownPair = [keys[i], keys[j]]; }
    }
  }
  out.silhouettes = {
    authoredAnimals: keys.length,
    closestPairSide: { pixelsOfOutlineThatDiffer: worst, pair: worstPair },
    closestPairDown: { pixelsOfOutlineThatDiffer: worstDown, pair: worstDownPair },
  };
  // Two animals whose outline is IDENTICAL at 16px are one animal with two
  // names, and `down` is the facing a follower is seen in most.
  if (worstDown === 0) {
    note(`${worstDownPair.join(' and ')} have the same 16px outline facing down — `
       + 'they are one animal with two names');
  }
}

out.failures = fail.length;
out.detail = fail;
console.log(JSON.stringify(out, null, 1));
process.exit(fail.length ? 1 : 0);
