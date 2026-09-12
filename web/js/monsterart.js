/* The bestiary, as shapes.
 *
 * The complaint this file exists to answer was the player's, and it was correct:
 * seventy-one enemies share twenty-eight sprite keys, the early ones are blobs,
 * and every area therefore looks like the first area. That is the cheapest thing
 * making a seventeen-region world feel like one room. A screenshot of the Marsh
 * and a screenshot of the Mines should not be distinguishable only by the tile
 * under the monster's feet.
 *
 * So: thirty-two authored creatures grouped into families by ELEMENT and BIOME,
 * the seventeen apexes gauntlet/hunters.py names — drawn to the silhouettes it
 * writes for them — seven more apex-class bodies it does not currently use, and
 * three unmarked fallback bodies for keys nobody has drawn yet.
 *
 * Nothing here is traced, sampled or derived from any existing game. Every grid
 * below was authored for this file, in this file.
 *
 * WHAT THIS MODULE OWES THE REST OF THE GAME
 *
 *   monsterFrame(key, frame, opts)   -> a cached canvas, 24x24, or 32x32 apex
 *   monsterSprite(key, pattern, f, c)-> the sprites.js enemySprite signature
 *   monsterSilhouette(key, frame)    -> the readability check, colour gone
 *   monsterMotion(key)               -> frames, period, bob, sway, phase
 *   rosterFor(region)                -> what lives there
 *   apexKeyFor(region)               -> the one that hunts you there
 *   monsterIsAuthored(key)           -> whether a key fell through
 *
 * It owns no state a caller has to manage and it never throws on a name it does
 * not know. gauntlet/hunters.py had not landed when this was written, so the
 * apex roster is keyed on REGION rather than on hunter ids: whatever names that
 * file ships, `apexKeyFor(regionId)` answers, and an unrecognised hunter name
 * with a known region still draws that region's apex.
 *
 * THE RULES THIS FILE IS HELD TO
 *
 *  1. Fifteen colours plus transparent, counted off the RENDERED RASTER by
 *     scripts/verify/monsters.mjs and never off the palette dict. A dict with
 *     fifteen entries that a shading pass turns into sixteen is over budget.
 *  2. One pixel grid. Mobs are 24x24, the same box sprites.js ENEMY_SIZE
 *     already uses, so a call site swaps without moving anything. Apexes are
 *     32x32 — bigger than a mob, smaller than the 48x48 boss, which is exactly
 *     the rank they hold.
 *  3. No Math.random and no Date.now on a draw path. Every variation is a hash
 *     of its own inputs, so two runs of one frame are the same bytes.
 *  4. Cached under a cap, evicted oldest-first, like every other rig here.
 *  5. Merge, then light, once. mergeGrids -> applyRim -> rimLowLeft, imported
 *     from sprites.js rather than reimplemented. A second lighting model is how
 *     a cast stops looking like a cast.
 *
 * SILHOUETTE IS THE WHOLE JOB
 *
 * A monster is seen at 24px with a tree in front of it. Interior shading is
 * worth very little at that size and outline is worth nearly everything, so
 * every creature was authored as a shape before it was authored as a colour:
 *
 *   FIRE       a bird with a crest and a wingspan; a low four-legged hound with
 *              a spined back; a legless rearing grub; a triangle of moth wing
 *   COLD       a high-shouldered wolf; a hunched hook-beaked shrike; a legless
 *              stack of shards; a tall thin mantis with raised forelimbs
 *   POISON     a spider's radial legs; a legless whipping stalk; a squat wide
 *              toad; a wading bird that is mostly leg
 *   BRUTE      a knuckle-walking ape; a boring grub; a low wedge on six legs;
 *              a square statue with no neck
 *   LIGHTNING  a horned ram; a swept-back darting bird; a coiled serpent; a
 *              stilt-legged mast of rusted rod
 *   VOID       a spear-carrying skeleton; a skeletal dog; a hooded legless
 *              shade; three skulls orbiting nothing
 *   NEUTRAL    per biome, and deliberately smaller in outline than any of the
 *              above: the first fields are where nothing should push back yet
 *
 * Each is checked with colour discarded by monsterSilhouette(), and the closest
 * pair in the whole roster is reported by monsterArtStats().
 *
 * AND SO IS THE WALK
 *
 * A skeleton walks wrong. Its lead leg lifts three rows and its trailing leg
 * lifts one, so it limps on a schedule instead of striding. A bird is never
 * quite still: wings up, wings down, and the body counter-bobbing against them,
 * three frames, none of which is the other two. An elemental has no legs to
 * plant, so the whole mass rises, the bottom edge frays to a different set of
 * cells, and the core beats — it never touches the ground in any frame. Those
 * are authored deformations of the grid, not brightness nudges. A frame that
 * differs by a few units of brightness is not a frame.
 *
 * THE APEXES ARE DIFFERENT, NOT BIGGER
 *
 * Scaling a mob 1.33x is the failure mode, so none of the seventeen is a scaled
 * anything: each is a silhouette that does not appear anywhere else in its
 * region. gauntlet/hunters.py names the seventeen and writes a silhouette for
 * each of them FOR AN ARTIST rather than for a tooltip, so these are drawn to
 * that text: the Mines get a phoenix whose wings are visibly a stack rather
 * than a fan; the Pass gets two mirrored ice-bearers converging, where the
 * shape you have to read is the GAP between them; the Recursive Forest gets one
 * figure at three sizes in a single outline; the Tower gets a narrow figure
 * with a much larger one cropped by the frame behind it. On top of that the
 * apex outline is THICKENED by one cell, which is the single loudest legibility
 * cue at this size, and it carries a sparse aura outside the outline. All three
 * are in the silhouette and all three are measured.
 *
 * The art keys ARE hunters.py's `sprite` keys, so `apexKeyFor(hunterRow)` and
 * `monsterFrame(row.sprite, ...)` both land without a translation table, and
 * scripts/verify/monsters.mjs reads hunters.py and fails if any of the seventeen
 * stops resolving, starts sharing a body with another, or drifts off its own
 * region.
 *
 * MEASURED
 *
 * Everything above is a claim, so here are the numbers behind them, taken off
 * the rendered raster rather than off this file's intentions. Re-take them with
 * monsterArtStats() and `node scripts/verify/monsters.mjs`.
 *
 *   colour budget   2,360 frames swept — fifty-nine bodies, two poses, four
 *                   frames, five palettes (own plus four server colours).
 *                   Worst frame: 13 colours. Budget 15. Nothing over, ever,
 *                   counted off pixels rather than off the palette dict.
 *   silhouette      closest pair in the whole roster: 21 of 256 outline cells
 *                   differ (fourth_orientation / sand_champion — two armoured
 *                   bipeds, in the Citadel and the Coliseum, which a player
 *                   never sees in the same place). Closest pair a player CAN
 *                   see side by side: 43 (tuftling / fieldadder, Fields of
 *                   Syntax). No region contains two creatures nearer than that.
 *   apex scale      every apex is between 1.34x and 3.16x the drawn pixels of
 *                   the biggest mob in its own region, thickened outline
 *                   included.
 *   motion          outline cells changing across one walk cycle: 76 at the low
 *                   end, 560 at the high. Across one idle cycle: 66 to 1,250.
 *                   Fourteen gaits. Nothing in here animates by brightness,
 *                   nothing stands still, and no legless creature touches the
 *                   floor in any frame of either pose.
 *   the hunters     all seventeen gauntlet/hunters.py apexes resolve to their
 *                   own region's body, by `sprite`, by `id` and by display
 *                   name, with no two sharing one body and no name out of step.
 *   the regions     71 enemies x 17 regions = 1,207 combinations drawn, none
 *                   over budget and none broken. All 28 of bestiary.py's sprite
 *                   keys resolve through the table; none falls through; every
 *                   one of them draws between 13 and 15 DIFFERENT creatures
 *                   across the seventeen regions, which is the whole point.
 *   determinism     472 frames hash identically warm, cold and rebuilt.
 *   steady state    240 redraws of one settled frame: 0 canvases. Every region's
 *                   whole cast, both poses, all frames, twice over: 376
 *                   canvases for 376 distinct frames, working set 377 under a
 *                   cap of 720.
 *
 * FALLING BACK WITHOUT LYING
 *
 * An unknown key does not throw and does not silently become a creature it is
 * not. It becomes `strayling`, `straywisp` or, at apex rank, `strayapex` —
 * deliberately featureless bodies, no markings and no species, painted in the
 * palette of the region it was asked for and drawn in the box its rank expects,
 * so the caller's layout does not move either. A harness can tell the difference: monsterIsAuthored() reports
 * whether a key was resolved by the table or by falling off the end of it, and
 * scripts/verify/monsters.mjs fails on the second.
 */

import {
  RAMPS, SHADE, OUTLINE, rampFor, warmer, cooler,
} from './palette.js';

import {
  mix, hash, gridSprite, mergeGrids, applyRim, rimLowLeft, normalise,
  silhouetteAt, rimTone,
} from './sprites.js';

/* ------------------------------------------------------------------ boxes */

/* The same 24 sprites.js ENEMY_SIZE uses. A monster drawn here drops into any
 * call site that was drawing an enemy, at the same offsets. */
export const MON_SIZE = 24;

/* An apex is a third again as tall and reads at a glance as something that does
 * not belong to the trash roster. It is not 48: a boss is a set piece with a
 * cutscene and this is a thing that walks up behind you in a field. */
export const APEX_SIZE = 32;

/* The row every ground-standing creature plants on, in its own box. */
export const MON_GROUND = MON_SIZE - 1;

/* ---------------------------------------------------------------- glyphs
 *
 * The same contract sprites.js and petart.js use: '.' is transparent, every
 * other character indexes the palette. applyRim() only ever rewrites 'B', so an
 * authored eye, claw or ember survives the shading pass untouched.
 *
 *   o   outline, the one near-black the whole cast shares
 *   B   undecided body mass; applyRim turns it into H / L / d / D
 *   a   accent, dark   — a mane, a stripe, a chitin band, a rune
 *   A   accent, light  — the lit face of the same
 *   g   hard material  — beak, claw, horn, bone, tooth, plate
 *   w   eye white
 *   e   pupil (resolves to the outline: a fourth near-black is a wasted slot)
 *   k   ink — a socket, an open mouth, a hole that is not shaded
 *   c   core — the ember, the arc, the cold light. Emissive; never lit.
 *   C   core specular, apexes only
 *   r   aura, apexes only; written outside the outline after lighting
 *   R   written by rimLowLeft; never authored
 */

/* ---------------------------------------------------------- the creatures
 *
 * Each entry is authored as a list of rows whose LAST row is the row the
 * creature stands on, so a quadruped and a bird plant on the same line without
 * anybody counting. `oy` overrides that for the things that do not stand:
 * elementals, and anything in flight.
 *
 * The extra fields are BANDS, not glyphs. A gait moves a rectangle of the grid
 * — a leg out of its own column range, a wing out of its own row range, a spine
 * dipped — which is what lets twelve gait functions drive fifty creatures
 * without any two of them sharing a walk.
 *
 *   legs     column ranges, ground up. legTop is the row a leg starts at.
 *   wing     [x0, x1, y0, y1] rectangles that beat
 *   head     [y0, y1] and headX [x0, x1]
 *   spine    [y0, y1] the band that dips and rises
 *   tail     [y0, y1] with tailX
 */

const M = {};

/* ================================================================
 * FIRE — Stack & Queue Mines (ember), Debugging Dungeon (the forge)
 * ================================================================
 * The brief asked for phoenix fire birds, and the fledgling is the mob; the
 * full bird is the Mines' apex. Around it: something that runs on four legs,
 * something that has no legs at all, and something that is mostly wing.
 */

/* A fledgling. Crest, wingspan, two thin legs, and a body that is small for the
 * wings it is carrying — which is what makes a young bird read as young. */
M.emberwing = {
  family: 'FIRE', gait: 'wingbeat', idle: 'preen',
  body: 'ember', accent: 'gold', hard: 'bone', core: 'ember',
  frames: 3, period: 520, bob: 1, sway: 0, phase: 0.00,
  rows: [
    '...........oo...........',
    '..........oaoo..........',
    '.........oao.oo.........',
    '.........oBBBo..........',
    '........oBBwBBo.........',
    '........oBBeBBoggo......',
    '........oBBBBBoggo......',
    '.........oBBBo..........',
    '....oo...oBBBo...oo.....',
    '...oao..oBBBBBo..oao....',
    '..oaBo.oBBBBBBBo.oBao...',
    '.oaBBooBBBBBBBBBooBBao..',
    'oaBBBBBBBBcBcBBBBBBBBao.',
    'oaBBBBBBBBBBBBBBBBBBBao.',
    '.oaBBBoBBBBBBBBBoBBBao..',
    '..oaaoooBBBBBBBoooaao...',
    '........oBaBBaBo........',
    '........oBBBBBBo........',
    '.........oBBBBo.........',
    '.........oBoBo..........',
    '........ogo.ogo.........',
    '........ogo.ogo.........',
    '.......oggo.oggo........',
    '.......ooo...ooo........',
  ],
  wing: [[0, 7, 8, 15], [16, 23, 8, 15]],
  head: [0, 7], headX: [7, 17], spine: [10, 18],
  legs: [[8, 10], [12, 14]], legTop: 20, tail: null, tailX: null,
};

/* Low, four-legged, and carrying its heat along its spine rather than in its
 * mouth. The mane is the read: a hound-shaped outline with a row of spikes on
 * top of it is not a hound anybody keeps. */
M.cinderhound = {
  family: 'FIRE', gait: 'fourbeat', idle: 'breathe',
  body: 'rust', accent: 'ember', hard: 'bone', core: 'ember',
  frames: 4, period: 460, bob: 1, sway: 0, phase: 0.20,
  rows: [
    '.......oao...oao........',
    '......oaco..oaco........',
    '.....oaBBo.oaBBo.oooo...',
    'oo...oaBBBoaBBBo.oBBBo..',
    '.oo..oBBBBBBBBBo.oBwBo..',
    '..oooBBBBBBBBBBBooBBeo..',
    '..oaBBBBBBBBBBBBBBBBggo.',
    '..oBBBBBBBBBBBBBBBBBggo.',
    '..oBBBBBBBBBBBBBBBBoo...',
    '...oBBBBBBBBBBBBBBo.....',
    '...oBBoBBBoBBBoBBBo.....',
    '...oBo.oBo.oBo.oBBo.....',
    '...oBo.oBo.oBo.oBBo.....',
    '...oBo.oBo.oBo.oBBo.....',
    '...ogo.ogo.ogo.oggo.....',
    '...ooo.ooo.ooo.oooo.....',
  ],
  wing: null,
  head: [2, 8], headX: [16, 23], spine: [6, 10],
  legs: [[3, 5], [7, 9], [11, 13], [15, 18]], legTop: 11,
  tail: [3, 6], tailX: [0, 4],
};

/* No legs anywhere in the grid and none in the gait. It rears, it is ringed,
 * and the seam down its front is the only part of it that is lit from inside. */
M.slagworm = {
  family: 'FIRE', gait: 'slither', idle: 'coil',
  body: 'ember', accent: 'rust', hard: 'bone', core: 'ember',
  frames: 4, period: 700, bob: 0, sway: 2, phase: 0.55,
  rows: [
    '.........oooo...........',
    '........oBBBBo..........',
    '.......oBBccBBo.........',
    '.......oBkBBkBo.........',
    '.......oBBBBBBo.........',
    '........oaaaao..........',
    '........oBBBBo..........',
    '.......oBBBBBBo.........',
    '.......oaBBBBao.........',
    '......oBBBBBBBBo........',
    '......oaBBBBBBao........',
    '.....oBBBBBBBBBo........',
    '.....oaBBBBBBBao........',
    '....oBBBBBBBBBBo........',
    '...oBBBBBBBBBBBoo.......',
    '..oaBBBBBBBBBBBBoo......',
    '..oBBBBBBBBBBBBBBo......',
    '.ooBBBBBBBBBBBBBBBoo....',
    '.oaBBBBBBBBBBBBBBBBBo...',
    'ooBBBBBBBBBBBBBBBBBBBoo.',
    'oooooooooooooooooooooooo',
  ],
  wing: null,
  head: [0, 5], headX: [6, 17], spine: [6, 18],
  legs: [], legTop: MON_SIZE, tail: [17, 20], tailX: [14, 23],
};

/* Mostly wing. The thorax is furred, the antennae are plumed, and the feet are
 * not part of the read at all — a moth at this size is one triangle. */
M.ashmoth = {
  family: 'FIRE', gait: 'flit', idle: 'twitch',
  body: 'leather', accent: 'ember', hard: 'bone', core: 'ember',
  frames: 3, period: 260, bob: 2, sway: 1, phase: 0.75,
  oy: 1,
  rows: [
    '.....o..........o.......',
    '....oao........oao......',
    '...oao..........oao.....',
    '...o..oo.oo.oo..o.......',
    '......oBooBooBo.........',
    '.....oaBBoBBoBao........',
    '....oaBBBoBBoBBao.......',
    '...oaBBBBoBBoBBBao......',
    '..oaBBBBBoBBoBBBBao.....',
    '.oaBBcBBBoBBoBBBcBao....',
    'oaBBBBBBBoBBoBBBBBBao...',
    'oaBBBBBBBoBBoBBBBBBao...',
    '.oaBBBBBBoBBoBBBBBao....',
    '..oaBBBBBoBBoBBBBao.....',
    '...oaBBBBoBBoBBBao......',
    '....oaBBBoBBoBBao.......',
    '.....oaaooBBooaao.......',
    '.......ooaBBaoo.........',
    '.........oBBo...........',
    '.........oaao...........',
    '..........oo............',
  ],
  wing: [[0, 9, 4, 17], [13, 22, 4, 17]],
  head: [3, 5], headX: [8, 15], spine: [4, 19],
  legs: [], legTop: MON_SIZE, tail: null, tailX: null,
};

/* ================================================================
 * COLD — Twin Pointer Pass (the snow line), Complexity Tower (azure)
 * ================================================================
 * The brief asked for an ice elemental. It is here as a mob and again, larger
 * and legless, as the Pass's apex.
 */

/* High shoulders, low head, a ruff of frozen guard hair. A wolf is read off the
 * line from the shoulder to the tail, so that line is never level. */
M.rimewolf = {
  family: 'COLD', gait: 'fourbeat', idle: 'breathe',
  body: 'frost', accent: 'cyan', hard: 'bone', core: 'cyan',
  frames: 4, period: 500, bob: 1, sway: 0, phase: 0.10,
  rows: [
    '.........oao............',
    '........oaao.....oo.....',
    '.......oaBBao...oaBo....',
    '..oo...oaBBBao.oaBBBo...',
    '.oaBo.oaBBBBBaooBBwBo...',
    'oaBBBooBBBBBBBBBBBBeo...',
    'oaBBBBBBBBBBBBBBBBBggo..',
    '.oBBBBBBBBBBBBBBBBBggo..',
    '..oBBBBBBBBBBBBBBBBoo...',
    '..oBBBBBBBBBBBBBBBo.....',
    '..oBBoBBBoBBBBoBBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..ogo.ogo.oggo.oggo.....',
    '..ooo.ooo.oooo.oooo.....',
  ],
  wing: null,
  head: [1, 8], headX: [14, 22], spine: [5, 10],
  legs: [[2, 4], [6, 8], [10, 13], [15, 18]], legTop: 11,
  tail: [3, 7], tailX: [0, 5],
};

/* A hunting bird with its wings TUCKED — a teardrop with a hook on the front,
 * which is the opposite read from the emberwing's spread T. Same family, and
 * nobody will confuse the two in outline. */
M.snowshrike = {
  family: 'COLD', gait: 'wingbeat', idle: 'preen',
  body: 'frost', accent: 'bone', hard: 'bone', core: 'cyan',
  frames: 3, period: 620, bob: 1, sway: 1, phase: 0.40,
  rows: [
    '........oooo............',
    '.......oBBBBo...........',
    '......oBBwBBo...........',
    '......oBBeBBogo.........',
    '......oBBBBBBggo........',
    '......oBBBBBBgo.........',
    '.....oBBBBBBBo..........',
    '....oaBBBBBBBo..........',
    '...oaABBBBBBBBo.........',
    '..oaABBBBBBBBBBo........',
    '..oaABBBBBBBBBBBo.......',
    '..oaABBBcBBBBBBBBo......',
    '..oaABBBBBBBBBBBBBo.....',
    '..oaABBBBBBBBBBBBBBo....',
    '..oaAABBBBBBBBBBBBBBo...',
    '...oaAABBBBBBBBBBBBBo...',
    '....oaaABBBBBBBBBBBo....',
    '.....ooaaBBBBBBBBoo.....',
    '.......ooBBBBBBoo.......',
    '.........oBoBo..........',
    '........ogo.ogo.........',
    '........ogo.ogo.........',
    '.......oggo.oggo........',
    '.......ooo...ooo........',
  ],
  wing: [[2, 8, 7, 18], [13, 21, 8, 18]],
  head: [0, 6], headX: [5, 15], spine: [8, 18],
  legs: [[8, 10], [12, 14]], legTop: 20, tail: null, tailX: null,
};

/* The ice elemental, at mob size. No legs, and no bottom edge either: it ends
 * in a fray that is a different set of cells on every frame, so there is never
 * a row you could call the one it is standing on. */
M.frostcairn = {
  family: 'COLD', gait: 'hover', idle: 'pulse',
  body: 'frost', accent: 'cyan', hard: 'chrome', core: 'cyan',
  frames: 3, period: 1400, bob: 2, sway: 1, phase: 0.65,
  oy: 1,
  rows: [
    '.....o.......o..........',
    '....oao.....oao.........',
    '...oaBo.o..oaBo.........',
    '..oaBBooao.oaBBo........',
    '..oaBBBaBooaBBBo........',
    '.oaBBBBBBBBBBBBBo.......',
    '.oaBBBBcccccBBBBo.......',
    'oaBBBBcCwwwCcBBBBo......',
    'oaBBBBcCcccCcBBBBo......',
    '.oaBBBBcccccBBBBo.......',
    '.oaBBBBBBBBBBBBo........',
    '..oaBBBBBBBBBBo.........',
    '..oaBBBBBBBBo...........',
    '...oaBBBBBBo............',
    '...oaBBBBo..............',
    '....oaBBo...............',
    '....oaBo................',
    '.....oo.................',
  ],
  wing: null,
  head: [5, 10], headX: [0, 18], spine: [3, 14],
  legs: [], legTop: MON_SIZE, fray: [12, 17], tail: null, tailX: null,
};

/* Tall, thin, and folded. The raised forelimbs are the whole silhouette; it is
 * the only creature in the game whose outline is mostly negative space. */
M.icemantis = {
  family: 'COLD', gait: 'stalk', idle: 'twitch',
  body: 'cyan', accent: 'frost', hard: 'chrome', core: 'cyan',
  frames: 4, period: 900, bob: 1, sway: 0, phase: 0.85,
  rows: [
    '..oo...............oo...',
    '.oao...............oao..',
    '.oBo...............oBo..',
    '.oBoo.....oo......ooBo..',
    '..oBo....oBBo....oBBo...',
    '...oBo..oBwwBo..oBBo....',
    '....oBooBeBeBooBBBo.....',
    '.....oBBoBggBoBBBo......',
    '......oBBoooBBBBo.......',
    '.......oBBBBBBBo........',
    '........oBBBBo..........',
    '.......oaBBBBao.........',
    '.......oBBcBBBo.........',
    '.......oaBBBBao.........',
    '.......oBBBBBBo.........',
    '......oBoBBBBoBo........',
    '.....oBo.oBBo.oBo.......',
    '....oBo..oBBo..oBo......',
    '...oBo...oBBo...oBo.....',
    '...oo....oBBo....oo.....',
    '.........oBBo...........',
    '.........oggo...........',
    '........oggggo..........',
    '........oo..oo..........',
  ],
  wing: null,
  head: [3, 9], headX: [7, 17], spine: [10, 15],
  legs: [[3, 6], [17, 20]], legTop: 15, arms: [[1, 6, 0, 8], [17, 22, 0, 8]],
  tail: null, tailX: null,
};

/* ================================================================
 * POISON — Stringwood Labyrinth (the rainforest), Sliding Window Marsh
 * ================================================================
 * The brief asked for hunting animals in the rainforest. These are the hunters
 * the rainforest actually has: the ones with more than four legs, the ones with
 * none, and the ones that are patient.
 */

/* Radial. Eight legs out of a small body, which is a shape no other creature in
 * the game makes — every other silhouette here is bilateral and vertical. */
M.webstalker = {
  family: 'POISON', gait: 'scuttle', idle: 'twitch',
  body: 'venom', accent: 'grass', hard: 'bone', core: 'venom',
  frames: 4, period: 380, bob: 1, sway: 1, phase: 0.05,
  rows: [
    '..o................o....',
    '..oo..............oo....',
    '...oo....oooo....oo.....',
    '.o..oo..oBBBBo..oo..o...',
    '.oo..ooooBwwBoooo..oo...',
    '..oo...oBeBBeBo...oo....',
    '...ooooBBaBBaBBoooo.....',
    'o...oBBBBBBBBBBBBo...o..',
    'oo.oBBBBcBBcBBBBBBo.oo..',
    '.ooBBBBBBBBBBBBBBBBoo...',
    '..oBBBaBBBBBBBBaBBBo....',
    '..oBBBBBBBBBBBBBBBBo....',
    '.o.oBBBBaBBBBaBBBBo..o..',
    'oo..oBBBBBBBBBBBBo..oo..',
    '.oo..ooBBBBBBBBoo..oo...',
    '..oo...oooooooo...oo....',
    '...oo............oo.....',
    '....o............o......',
    '....oo..........oo......',
    '.....o..........o.......',
    '.....oo........oo.......',
    '......o........o........',
    '......oo......oo........',
    '.......o......o.........',
  ],
  wing: null,
  head: [2, 7], headX: [7, 16], spine: [7, 15],
  legs: [[0, 4], [19, 23]], legTop: 16,
  arms: [[0, 5, 0, 16], [18, 23, 0, 16]], tail: null, tailX: null,
};

/* A plant that hunts. No legs, no eyes, a maw at the top of a stalk and two
 * leaf blades held out like arms. It is the only thing in the Stringwood that
 * is taller than it is wide. */
M.lashvine = {
  family: 'POISON', gait: 'slither', idle: 'coil',
  body: 'grass', accent: 'venom', hard: 'bone', core: 'venom',
  frames: 4, period: 820, bob: 0, sway: 2, phase: 0.30,
  rows: [
    '.......ogggggo..........',
    '......ogkkkkkgo.........',
    '.....ogkBBBBBkgo........',
    '.....ogkBccBBkgo........',
    '......ogkBBBkgo.........',
    '.......oggggo...........',
    '........oBBo............',
    '.......oaBBao...........',
    '.oo....oBBBBo.....oo....',
    'oaao..oaBBBBao...oaao...',
    'oaBao.oBBBBBBo..oaBao...',
    '.oaBaooaBBBBao.oaBao....',
    '..oaBBoBBBBBBooaBao.....',
    '...oaBBaBBBBaBBaBo......',
    '....ooBBBBBBBBBBo.......',
    '......oBBBBBBBBo........',
    '.......oaBBBBao.........',
    '.......oBBBBBBo.........',
    '......oaBBBBBBao........',
    '......oBBBBBBBBo........',
    '.....oaBBBBBBBBao.......',
    '.....oBBBBBBBBBBo.......',
    '....ooBBBBBBBBBBoo......',
    '....oooooooooooooo......',
  ],
  wing: null,
  head: [0, 5], headX: [5, 16], spine: [8, 18],
  legs: [], legTop: MON_SIZE,
  arms: [[0, 6, 8, 13], [15, 21, 8, 13]], tail: [18, 23], tailX: [4, 19],
};

/* Squat, wide, low to the ground, splayed. The mouth is a third of the width of
 * the animal, which is the whole joke and the whole silhouette. */
M.spinetoad = {
  family: 'POISON', gait: 'hop', idle: 'breathe',
  body: 'venom', accent: 'grass', hard: 'bone', core: 'venom',
  frames: 4, period: 1100, bob: 3, sway: 0, phase: 0.50,
  rows: [
    '......ooo......ooo......',
    '.....oaBao....oaBao.....',
    '....oBwwwBo..oBwwwBo....',
    '....oBweeBoooBweeBBo....',
    '....oBBBBBBBBBBBBBBo....',
    '...ooBBBBBBBBBBBBBBoo...',
    '..oaoooooooooooooooao...',
    '.oaBBBBBBBBBBBBBBBBBao..',
    'oaBBaBBcBBBBBBcBBaBBBao.',
    'oBBBBBBBBBBBBBBBBBBBBBo.',
    'oBBaBBBBBBBBBBBBBBaBBBo.',
    'oBBBBBBBBBBBBBBBBBBBBBo.',
    'oaBBBBBBBBBBBBBBBBBBBao.',
    '.oaBBBBBBBBBBBBBBBBBao..',
    '..ooBBBBBBBBBBBBBBBoo...',
    '.oo.oBBBBBBBBBBBBBo..oo.',
    'ogo..oBBBBBBBBBBBo...ogo',
    'ogo...oBBBBBBBBBo....ogo',
    'oggo..oBo.....oBo...oggo',
    'oggggooggo...oggooogggo.',
    '.ooooooooo...ooooooooo..',
  ],
  wing: null,
  head: [0, 6], headX: [4, 19], spine: [7, 14],
  legs: [[0, 4], [19, 23]], legTop: 15, tail: null, tailX: null,
};

/* Mostly leg. A wading bird is two lines, a body the size of a fist and a beak
 * that is a third line — nothing else in the game is drawn this thin. */
M.stiltheron = {
  family: 'POISON', gait: 'stalk', idle: 'preen',
  body: 'cloth', accent: 'venom', hard: 'bone', core: 'venom',
  frames: 4, period: 1000, bob: 1, sway: 0, phase: 0.70,
  rows: [
    '.......ooo..............',
    '......oBBBo.............',
    '......oBwBo.............',
    '......oBeBogggggggo.....',
    '......oBBBogggggggo.....',
    '.......oBBo.............',
    '.......oBBo.............',
    '.......oBBo.............',
    '.......oBBo.............',
    '......ooBBoo............',
    '.....oaBBBBao...........',
    '....oaBBBBBBao..........',
    '...oaBBBcBBBBao....o....',
    '...oBBBBBBBBBBo...oao...',
    '...oaBBBBBBBBao..oaBo...',
    '....oaBBBBBBao..oaBo....',
    '.....ooBBBBoo..oaBo.....',
    '......oBooBo..oaBo......',
    '......ogo.ogooaBo.......',
    '......ogo.ogoaBo........',
    '......ogo.ogoBo.........',
    '......ogo.oggo..........',
    '.....oggo.oggo..........',
    '.....ooo...ooo..........',
  ],
  wing: null,
  head: [0, 9], headX: [5, 18], spine: [10, 17],
  legs: [[6, 8], [10, 12]], legTop: 18, tail: [12, 20], tailX: [13, 20],
};

/* ================================================================
 * BRUTE — Array Caverns (stone, and the weight above it), Matrix Citadel
 * ================================================================
 * Brute is mass. Everything in this family is drawn wide at the shoulder and
 * narrow at the ground, which is how weight reads in two dimensions.
 */

/* Knuckles down, head sunk between the shoulders, arms longer than the legs.
 * The top third of the outline is shoulder and nothing else. */
M.gravelape = {
  family: 'BRUTE', gait: 'lumber', idle: 'breathe',
  body: 'stone', accent: 'earth', hard: 'bronze', core: 'bronze',
  frames: 4, period: 780, bob: 1, sway: 1, phase: 0.15,
  rows: [
    '.........oooo...........',
    '........oBBBBo..........',
    '.......oBwBBwBo.........',
    '.......oBeBBeBo.........',
    '.......oBBggBBo.........',
    '...oooooBBBBBBooooo.....',
    '..oaBBBBoBBBBoBBBBao....',
    '.oaBBBBBBBBBBBBBBBBao...',
    'oaBBBBBBBaBBaBBBBBBBao..',
    'oBBBBBBBBBBBBBBBBBBBBo..',
    'oBBBBoBBBBBBBBBBoBBBBo..',
    'oBBBo.oBBBcBBBo.oBBBBo..',
    'oBBBo.oBBBBBBo..oBBBBo..',
    'oBBBo..oBBBBo...oBBBBo..',
    'oBBBo..oBBBBo...oBBBBo..',
    'oBBBo..oBBBBo...oBBBBo..',
    'oBBBo.ooBBBBoo..oBBBBo..',
    'oBBBooaBBBBBBao.oBBBBo..',
    'oBBBBoBBBBBBBBooBBBBBo..',
    'oBBBBBBBoooooBBBBBBBBo..',
    'oggggBBo.....oBBggggoo..',
    'ogggggoo.....ooggggggo..',
    'ooooooo.......ooooooo...',
    '.ooooo.........ooooo....',
  ],
  wing: null,
  head: [0, 5], headX: [6, 17], spine: [6, 12],
  legs: [[6, 12], [6, 12]], legTop: 16,
  arms: [[0, 5, 6, 22], [16, 21, 6, 22]], tail: null, tailX: null,
};

/* A boring head and a body that is only there to push it. No eyes: it has never
 * needed any. Drawn along the HORIZONTAL, head at the left and the body
 * tapering away behind it, which is the one thing separating it from the Mines'
 * slagworm — two legless segmented things on the same axis would be one
 * creature with two names, and the roster-wide silhouette check says so. */
M.drillgrub = {
  family: 'BRUTE', gait: 'slither', idle: 'coil',
  body: 'earth', accent: 'bronze', hard: 'bronze', core: 'bronze',
  frames: 4, period: 640, bob: 0, sway: 1, phase: 0.35,
  rows: [
    '..............oooooo....',
    '...........ooo......o...',
    '.......ooooo.........o..',
    '...ooooBBBBBooo.......o.',
    '..ogBBBBBBBBBBBoo.....o.',
    '.oggkBBBBBBBBBBBBoo...o.',
    'ogkckBBaBBBBaBBBBBBooo..',
    'ogkckBBBBBBBBBBBBBBBBoo.',
    'ogkckBBaBBBBaBBBBBBBBBo.',
    '.oggkBBBBBBBBBBBBBBBBo..',
    '..ogBBBBBBBBBBBBBBBBo...',
    '...ooooBBBBBBBBBBBoo....',
    '.......ooooBBBBBoo......',
    '..........ooooooo.......',
  ],
  wing: null,
  head: [3, 10], headX: [0, 6], spine: [3, 13],
  legs: [], legTop: MON_SIZE, tail: [9, 13], tailX: [8, 23],
};

/* A wedge on six legs, close enough to the floor that the legs are most of what
 * moves. It is the small one in a family of large ones, on purpose: a cavern
 * with only huge things in it has no scale. */
M.chiselmite = {
  family: 'BRUTE', gait: 'scuttle', idle: 'twitch',
  body: 'iron', accent: 'stone', hard: 'bronze', core: 'bronze',
  frames: 4, period: 340, bob: 1, sway: 1, phase: 0.60,
  rows: [
    '..........oggo..........',
    '.........ogggggo........',
    '........oggBBBggo.......',
    '.......ogBBwBwBBgo......',
    '......oaBBBeBeBBBao.....',
    '.....oaBBBBBBBBBBBao....',
    '....oaBBBBBcccBBBBBao...',
    '...oaBBBBBBBBBBBBBBBao..',
    '..oaBBBBaBBBBBBBaBBBBao.',
    '.ooBBBBBBBBBBBBBBBBBBoo.',
    'ooBBBBBBBBBBBBBBBBBBBBoo',
    'o.ooooooooooooooooooo..o',
    'oo.o.oo.oo...oo.oo.o..oo',
    '.o..o..o.o...o.o..o...o.',
    'oo..oo.oo.....oo.oo..oo.',
    '.....................o..',
  ],
  wing: null,
  head: [0, 4], headX: [6, 17], spine: [4, 11],
  legs: [[0, 5], [18, 23]], legTop: 11, tail: null, tailX: null,
};

/* Square. No neck, no waist, and the same width from shoulder to floor — the
 * Citadel's architecture wearing a face. Nothing organic is drawn this straight
 * anywhere else in the game, which is the entire read. */
M.plinthguard = {
  family: 'BRUTE', gait: 'lumber', idle: 'breathe',
  body: 'stone', accent: 'gold', hard: 'chrome', core: 'gold',
  frames: 4, period: 1200, bob: 1, sway: 0, phase: 0.80,
  rows: [
    '......oooooooooooo......',
    '.....ogggggggggggggo....',
    '.....ogaaaaaaaaaaago....',
    '.....oggggggggggggo.....',
    '......oBBBBBBBBBBo......',
    '......oBwwBooBwwBo......',
    '......oBeeBooBeeBo......',
    '......oBBBBBBBBBBo......',
    'oooooooBBBBBBBBBBooooooo',
    'ogaaaggBBBBBBBBBBggaaago',
    'oggggggBBBaccaBBBggggggo',
    'oBBBBoaBBBBccBBBBaoBBBBo',
    'oBBBBoaBBBBBBBBBBaoBBBBo',
    'oBBBBoaBBBBBBBBBBaoBBBBo',
    'oBBBBooBBBBBBBBBBooBBBBo',
    'oBBBBo.oBBBBBBBBo.oBBBBo',
    'oBBBBo.oBBBBBBBBo.oBBBBo',
    'ooooo..oBBBBBBBBo..ooooo',
    '.......oBBBoBBBBo.......',
    '.......oBBo.oBBBo.......',
    '.......oBBo.oBBBo.......',
    '.....oggggo.oggggo......',
    '.....oggggo.oggggo......',
    '.....oooooo.oooooo......',
  ],
  wing: null,
  head: [0, 7], headX: [5, 18], spine: [8, 17],
  legs: [[7, 10], [12, 16]], legTop: 18,
  arms: [[0, 5, 8, 17], [18, 23, 8, 17]], tail: null, tailX: null,
};

/* ================================================================
 * LIGHTNING — Hashmap Highlands (the exposed plateau), Graph Wastes
 * ================================================================
 * A plateau and a lattice of ruins are both the tallest conductor for a day's
 * walk, and everything living on them has grown around that fact. The arcs are
 * authored cells, not a glow: 'c' is drawn where the current actually runs.
 */

/* Horns first. The curl is two thirds of the silhouette and the body is drawn
 * small under it deliberately — this animal is a delivery system for a shape
 * that collects a charge. */
M.stormram = {
  family: 'LIGHTNING', gait: 'fourbeat', idle: 'breathe',
  body: 'bone', accent: 'gold', hard: 'bronze', core: 'gold',
  frames: 4, period: 540, bob: 1, sway: 0, phase: 0.25,
  rows: [
    '..............ogggo.....',
    '............oggcccggo...',
    '...........oggcgggccgo..',
    '...........ogcgo.oggcgo.',
    '...oo.....oggggo..oggcgo',
    '..oaBoooooggBBBgo.oggggo',
    '.oaBBBBBBBBBwBBggooggggo',
    'oaBBBBBBBBBBeBBBggggggo.',
    'oBBBBBBBBBBBBBBBgggggo..',
    'oBBBBBBBBBBBBBBBBggoo...',
    '.oBBBBBBBBBBBBBBoo......',
    '.oBBoBBBoBBBoBBBo.......',
    '.oBo.oBo.oBo.oBBo.......',
    '.oBo.oBo.oBo.oBBo.......',
    '.oBo.oBo.oBo.oBBo.......',
    '.ogo.ogo.ogo.oggo.......',
    '.ooo.ooo.ooo.oooo.......',
  ],
  wing: null,
  head: [0, 9], headX: [10, 23], spine: [6, 11],
  legs: [[1, 3], [5, 7], [9, 11], [13, 16]], legTop: 12,
  tail: [4, 7], tailX: [0, 4],
};

/* Swept back, forked at the tail, and drawn as if it were already moving. It is
 * the smallest thing in the LIGHTNING family and the fastest — three frames on
 * a two-hundred-and-eighty millisecond cycle. */
M.arcshrike = {
  family: 'LIGHTNING', gait: 'wingbeat', idle: 'twitch',
  body: 'steel', accent: 'gold', hard: 'bronze', core: 'gold',
  frames: 3, period: 280, bob: 2, sway: 1, phase: 0.45,
  oy: 3,
  rows: [
    'oo.................oo...',
    '.oao...............oao..',
    '.oaao.............oaao..',
    '..oaBao..oooo...oaBao...',
    '...oaBBooBBBBooaBBao....',
    '....oaBBBBwBBBBBBao.....',
    '.....oaBBBeBBBBao.......',
    '......oBBBBBggggo.......',
    '.....oBBcBBBBgo.........',
    '.....oBBBBBBBo..........',
    '......oBBBBBo...........',
    '.......oBoBo............',
    '......ogo.ogo...........',
    '.....oggo.oggo..........',
    '.....ooo...ooo..........',
    '..ooo..........ooo......',
    '.oaao..........oaao.....',
    'oaao............oaao....',
    'oo................oo....',
  ],
  wing: [[0, 7, 0, 5], [15, 22, 0, 5]],
  head: [3, 8], headX: [8, 20], spine: [7, 11],
  legs: [[6, 8], [10, 12]], legTop: 12, tail: [15, 18], tailX: [0, 22],
};

/* Coiled, legless, and arcing across its own rings — the one creature here
 * whose animation is electrical rather than muscular. The arc jumps between
 * coils, which means it is in a different place on every frame. */
M.coilworm = {
  family: 'LIGHTNING', gait: 'slither', idle: 'coil',
  body: 'gunmetal', accent: 'gold', hard: 'bronze', core: 'gold',
  frames: 4, period: 760, bob: 0, sway: 2, phase: 0.55,
  rows: [
    '.....ooo................',
    '....oBBBo...............',
    '....oBwBogo.............',
    '....oBeBoggo............',
    '....oBBBggo.............',
    '.....oBBBo..............',
    '......oBBoo.............',
    '....oooBBBBoo...........',
    '...oaBBBBBBBBoo.........',
    '..oaBBcccccBBBBoo.......',
    '..oBBBoooooBBBBBBoo.....',
    '..oBBo.....ooBBBBBBoo...',
    '..oBBo.......ooBBBBBBo..',
    '..oBBoo........oBBBBBo..',
    '..oaBBBoo.......oBBBBo..',
    '...oaBBBBoo.....oBBBBo..',
    '....oaBBBBBoo..ooBBBBo..',
    '.....oaBBBBBBooBBBBBBo..',
    '......oaBBBBBBBBBBBBo...',
    '.......oaBBBBBBBBBBo....',
    '........ooooooooooo.....',
  ],
  wing: null,
  head: [0, 6], headX: [3, 11], spine: [7, 19],
  legs: [], legTop: MON_SIZE, tail: [14, 20], tailX: [2, 21],
};

/* Rusted rod welded into a mast, on two legs that are longer than everything
 * else. It is the tallest mob in the game and the thinnest, and in the Wastes
 * it is drawn against a horizon, which is the point. */
M.rodwalker = {
  family: 'LIGHTNING', gait: 'stalk', idle: 'pulse',
  body: 'rust', accent: 'gold', hard: 'gunmetal', core: 'gold',
  frames: 4, period: 980, bob: 1, sway: 0, phase: 0.90,
  rows: [
    '...........o............',
    '..........oco...........',
    '..........oco...........',
    '.........ooco...........',
    '........ogggggo.........',
    '.......oggcccggo........',
    '.......ogcgggcgo........',
    '.......oggcccggo........',
    '........oggggo..........',
    '.....oo..oBBo..oo.......',
    '....oaBooBBBBooaBo......',
    '....oaBBBBccBBBBBo......',
    '.....oBBBBBBBBBBo.......',
    '.....oaBBBBBBBBao.......',
    '......oBBBBBBBBo........',
    '......oBBoooBBBo........',
    '......oBo...oBBo........',
    '......oBo...oBBo........',
    '......oBo...oBBo........',
    '......oBo...oBBo........',
    '......oBo...oBBo........',
    '......ogo...oggo........',
    '.....oggo...oggo........',
    '.....oooo...oooo........',
  ],
  wing: null,
  head: [0, 8], headX: [6, 17], spine: [9, 15],
  legs: [[5, 8], [11, 15]], legTop: 15,
  arms: [[4, 8, 9, 12], [15, 19, 9, 12]], tail: null, tailX: null,
};

/* ================================================================
 * VOID — Recursive Forest (a recursion that does not return), the Castle
 * ================================================================
 * The brief asked for skeletons in the void, and it was right to: absence is
 * best drawn as the part of a thing that is left when the thing is gone.
 */

/* A skeleton with a spear. Ribs you can see through, a pelvis that is too wide
 * for the legs under it, and a walk that is deliberately broken — see the
 * `skeletal` gait, which lifts the lead leg three rows and the trailing leg
 * one. It limps on a schedule. */
M.bonepike = {
  family: 'VOID', gait: 'skeletal', idle: 'rattle',
  body: 'bone', accent: 'void', hard: 'bone', core: 'violet',
  frames: 4, period: 700, bob: 1, sway: 0, phase: 0.00,
  rows: [
    '......ogggggo.....og....',
    '.....oggggggo.....og....',
    '.....ogkkgkko.....og....',
    '.....ogkkgkko.....og....',
    '.....oggggggo.....og....',
    '.....ogogogo......og....',
    '......ogggo.......og....',
    '....ooogggooo.....og....',
    '...ogggooogggo....og....',
    '...ogoogggooogo...og....',
    '...oo.ogogo.ooo..oogo...',
    '......ogogo......ogggo..',
    '.....oogogoo....ogggggo.',
    '.....ogggggo...oggcgggo.',
    '.....oggggo.....ogggggo.',
    '.....oggggggo....ogggo..',
    '.....ogo..ogo.....ogo...',
    '.....ogo..ogo.....og....',
    '.....ogo..ogo.....og....',
    '.....ogo..ogo.....og....',
    '.....ogo..ogo.....og....',
    '....oggo..oggo....og....',
    '...ogggo..ogggo...og....',
    '...oooo....oooo...oo....',
  ],
  wing: null,
  head: [0, 7], headX: [4, 13], spine: [7, 16],
  legs: [[3, 8], [9, 14]], legTop: 16,
  arms: [[15, 22, 0, 15]], jaw: [4, 7], jawX: [4, 13],
  tail: null, tailX: null,
};

/* The same bones on four legs and no spear. The spine is exposed along the top,
 * the ribs are a gap, and the head hangs below the shoulder line — a dog that
 * has stopped needing to breathe holds its head differently. */
M.gravehound = {
  family: 'VOID', gait: 'skeletal', idle: 'rattle',
  body: 'bone', accent: 'void', hard: 'bone', core: 'violet',
  frames: 4, period: 620, bob: 1, sway: 0, phase: 0.30,
  rows: [
    '..o.....................',
    '.ogo....ogggggo.........',
    '.ogoooooogogogoo........',
    '..ogggggggogogoggo......',
    '...ooooooooooooogggo....',
    '...ogogogogogogooggggo..',
    '...ogogogogogogo.ogkkgo.',
    '...ogogogogogogo.ogkkgo.',
    '...ooooooooooooo.oggggo.',
    '...ogo.ogo.ogoogooggogo.',
    '...ogo.ogo.ogo.ogoggggo.',
    '...ogo.ogo.ogo.ogooggo..',
    '...ogo.ogo.ogo.ogo......',
    '...ogo.ogo.ogo.ogo......',
    '..oggo.oggo.oggooggo....',
    '..oooo.oooo.ooooooo.....',
  ],
  wing: null,
  head: [1, 11], headX: [16, 22], spine: [4, 9],
  legs: [[3, 5], [7, 9], [11, 13], [15, 18]], legTop: 9,
  tail: [0, 4], tailX: [0, 3], jaw: [8, 11], jawX: [16, 22],
};

/* No legs, no feet, no bottom edge. A hood, two lights where a face is not, and
 * a hem that frays to a different set of cells on every frame. The one creature
 * in the game that is never touching the floor. */
M.shade = {
  family: 'VOID', gait: 'hover', idle: 'drift',
  body: 'void', accent: 'violet', hard: 'bone', core: 'violet',
  frames: 3, period: 1600, bob: 2, sway: 2, phase: 0.60,
  oy: 1,
  rows: [
    '........oooooo..........',
    '.......oaaaaaao.........',
    '......oaBBBBBBao........',
    '.....oaBBkkkkBBao.......',
    '.....oaBkkccckkBao......',
    '....oaBBkcwwwckBBao.....',
    '....oaBBkkcccckBBao.....',
    '...oaBBBkkkkkkkBBBao....',
    '...oaBBBBkkkkkBBBBao....',
    '..oaBBBBBBkkkBBBBBBao...',
    '..oaBBBBBBBBBBBBBBBao...',
    '.oaBBBBBBBBBBBBBBBBBao..',
    '.oaBBBBBBBBBBBBBBBBBao..',
    'oaBBBBBBBBBBBBBBBBBBBao.',
    'oaBBBBBBBBBBBBBBBBBBBao.',
    '.oBBBBBBBBBBBBBBBBBBBo..',
    '..oBBBBBBBBBBBBBBBBBo...',
    '...oBoBBBoBBoBBBoBBo....',
    '....o.oBo.oo.oBo.oo.....',
    '.......o...o..o.........',
  ],
  wing: null,
  head: [0, 9], headX: [3, 20], spine: [9, 17],
  legs: [], legTop: MON_SIZE, fray: [16, 19], tail: null, tailX: null,
};

/* Three skulls and nothing holding them together. It is the only creature in
 * the game with a disconnected silhouette, which is worth one slot in the
 * roster all by itself: a gap where a body should be reads instantly. */
M.skullswarm = {
  family: 'VOID', gait: 'hover', idle: 'pulse',
  body: 'bone', accent: 'violet', hard: 'bone', core: 'violet',
  frames: 3, period: 1100, bob: 2, sway: 2, phase: 0.85,
  oy: 2,
  rows: [
    '.......oggggo...........',
    '......oggggggo..........',
    '......ogkkgkko..........',
    '......oggggggo..........',
    '.......ogogo............',
    '........ooo.............',
    '.o..................o...',
    'ogggo..........ogggggo..',
    'oggggo........oggggggo..',
    'ogkkgo........ogkkgkko..',
    'oggggo........oggggggo..',
    '.ogogo.........ogogo....',
    '..ooo...........ooo.....',
    '........ccc.............',
    '.......c...c............',
    '......c.....c...........',
    '.....ooo...ooo..........',
    '....oggggoggggo.........',
    '....ogkkgogkkgo.........',
    '....oggggoggggo.........',
    '.....ooooooooo..........',
  ],
  wing: null,
  head: [0, 5], headX: [5, 14], spine: [6, 20],
  legs: [], legTop: MON_SIZE, fray: null, tail: null, tailX: null,
  orbit: [[0, 6, 6, 12], [13, 22, 6, 12], [3, 15, 16, 20]],
};

/* ================================================================
 * NEUTRAL — the five biomes elements.py deliberately left off the wheel
 * ================================================================
 * Village, the first fields, the canopy, the DP Ruins and the Coliseum have no
 * affinity on purpose: they are where a player learns what a plain fight costs.
 * So these creatures are drawn SMALLER in outline than anything elemental, and
 * none of them has a core. Nothing here is lit from inside.
 */

/* Fields of Syntax. Two ears, a round body, no teeth to speak of. It is the
 * honest early-game creature and it is allowed to be cute, because the first
 * region is the one place in the game where nothing should push back yet. */
M.tuftling = {
  family: 'NEUTRAL', biome: 'grass', gait: 'hop', idle: 'breathe',
  body: 'leather', accent: 'grass', hard: 'bone', core: null,
  frames: 4, period: 900, bob: 3, sway: 0, phase: 0.10,
  rows: [
    '.......oo....oo.........',
    '......oaBo..oaBo........',
    '......oaBo..oaBo........',
    '......oaBo..oaBo........',
    '.......oBoooBo..........',
    '......oBBBBBBBo.........',
    '.....oBBwBBwBBBo........',
    '.....oBBeBBeBBBo........',
    '....oBBBBggBBBBBo.......',
    '....oBBBBBBBBBBBo.......',
    '...oBBBaBBBBaBBBBo......',
    '...oBBBBBBBBBBBBBo......',
    '...oBBBBBBBBBBBBBo......',
    '....oBBBBBBBBBBBo.......',
    '....ooBBoooBBBoo........',
    '.....oggo.oggo..........',
    '.....oooo.oooo..........',
  ],
  wing: null,
  head: [0, 8], headX: [3, 17], spine: [8, 14],
  legs: [[4, 8], [9, 13]], legTop: 14, tail: null, tailX: null,
};

/* The other thing in a field. A line, moving, with nothing to plant — which
 * makes the grass biome the one neutral region with two silhouettes that could
 * not be confused in a thumbnail. */
M.fieldadder = {
  family: 'NEUTRAL', biome: 'grass', gait: 'slither', idle: 'coil',
  body: 'grass', accent: 'earth', hard: 'bone', core: null,
  frames: 4, period: 680, bob: 0, sway: 2, phase: 0.55,
  rows: [
    '..............oooo......',
    '.............oBBBBo.....',
    '....ooooo....oBwBeo.....',
    '...oBBBBBoooooBBggo.....',
    '..oBBaBBaBBBBoBBoo......',
    '..oBBBBBBBBBBBBBo.......',
    '...oBBaBBaBBBBoo........',
    '....oBBBBBBBBo..........',
    '.....oBBBBBBo...........',
    '......oBBBBo............',
    '.......oooo.............',
  ],
  wing: null,
  head: [0, 5], headX: [12, 19], spine: [2, 9],
  legs: [], legTop: MON_SIZE, tail: [2, 9], tailX: [2, 12],
};

/* Binary Tree Canopy. Hanging, long-armed, and drawn from the branch down —
 * the only creature in the game whose weight is at the TOP of the box. */
M.leafmonkey = {
  family: 'NEUTRAL', biome: 'canopy', gait: 'brachiate', idle: 'twitch',
  body: 'leather', accent: 'grass', hard: 'bone', core: null,
  frames: 3, period: 700, bob: 1, sway: 2, phase: 0.20,
  oy: 0,
  rows: [
    '...ogo.............ogo..',
    '...ogo.............ogo..',
    '..oaBo.............oaBo.',
    '..oaBo.....oooo....oaBo.',
    '..oaBo....oBBBBo...oaBo.',
    '..oaBo...oBwBBwBo..oaBo.',
    '..oaBBo..oBeBBeBo.oaBBo.',
    '...oaBBo.oBBggBBo.oaBo..',
    '....oaBBooBBBBBoooaBo...',
    '.....oaBBBBBBBBBBBBo....',
    '......oaBBBBBBBBBBo.....',
    '.......oBBBaaBBBBo......',
    '.......oBBBBBBBBoo......',
    '.......oBBBBBBBBBoo.....',
    '.......oBBBBBBBBBBBo....',
    '.......oBoBBBBoBBBBo....',
    '......ogo.oBBo.oBBBo....',
    '......ogo.oBBo..oBBo....',
    '.....oggo.oggo..oBBo....',
    '.....ooo..oooo..oaBo....',
    '................oaBo....',
    '.................ooo....',
  ],
  wing: null,
  head: [3, 8], headX: [8, 17], spine: [9, 15],
  legs: [[6, 9], [10, 13]], legTop: 16,
  arms: [[2, 7, 0, 9], [16, 22, 0, 9]], tail: [12, 21], tailX: [16, 21],
};

/* The other thing in a canopy: something very small that will not hold still.
 * Three frames on a two-hundred-millisecond cycle — the fastest wing in the
 * game, and deliberately in the calmest region. */
M.dartwren = {
  family: 'NEUTRAL', biome: 'canopy', gait: 'wingbeat', idle: 'preen',
  body: 'wood', accent: 'gold', hard: 'bone', core: null,
  frames: 3, period: 200, bob: 2, sway: 1, phase: 0.65,
  oy: 5,
  rows: [
    '.oo.................oo..',
    'oaao...oooo........oaao.',
    'oaBo..oBBBBo......oaBo..',
    '.oaBo.oBwBBo.....oaBo...',
    '..oaBooBeBBoggo.oaBo....',
    '...oaBBBBBBBoo.oaBo.....',
    '....oaBBBBBBBooaBo......',
    '.....oaBBBBBBBBBo.......',
    '......oBBBBBBBBo........',
    '.......oBBBBBBo.........',
    '.......oaBBBao..........',
    '........oBoBo...........',
    '.......ogo.ogo..........',
    '.......ogo.ogo..........',
    '......oggo.oggo.........',
    '......ooo...ooo.........',
  ],
  wing: [[0, 6, 0, 7], [14, 21, 0, 7]],
  head: [1, 6], headX: [5, 14], spine: [5, 11],
  legs: [[7, 9], [11, 13]], legTop: 12, tail: null, tailX: null,
};

/* DP Ruins, where every solved tile stays lit. A scarab carrying a raised
 * gilded shell — the accent here is gold leaf on a dull body, which is the
 * region's own physical description repeated on an animal. */
M.gildscarab = {
  family: 'NEUTRAL', biome: 'ruins', gait: 'scuttle', idle: 'twitch',
  body: 'stone', accent: 'gold', hard: 'goldleaf', core: null,
  frames: 4, period: 420, bob: 1, sway: 1, phase: 0.35,
  oy: 4,
  rows: [
    '.......o.......o........',
    '......oao.....oao.......',
    '.......ogo...ogo........',
    '........ogoooogo........',
    '.......ogBBBBBgo........',
    '......ogBwBBwBBgo.......',
    '.....oggBeBBeBBggo......',
    '....ooggggggggggggoo....',
    '...oaggAAAAAAAAggao.....',
    '..oaggAAAAAAAAAAggao....',
    '.oaggAAAAggggAAAAggao...',
    'oaggAAAAggggggAAAAggao..',
    'oaggAAAAggggggAAAAggao..',
    '.oaggAAAAggggAAAAggao...',
    '..oaggAAAAAAAAAAggao....',
    '...oaggggAAAAggggao.....',
    '....ooggggggggggoo......',
    '..oo..oo.oo.oo..oo......',
    '.oo...o...o..o...oo.....',
    'oo....oo.oo.oo....oo....',
  ],
  wing: null,
  head: [0, 7], headX: [4, 18], spine: [7, 17],
  legs: [[0, 4], [17, 22]], legTop: 17, tail: null, tailX: null,
};

/* A crawling assembly of flat slabs. It is the low horizontal one in the Ruins
 * against the scarab's tall domed one, and it has no head at all — a shape that
 * is all shoulder reads as architecture, which is what it is. */
M.tilewight = {
  family: 'NEUTRAL', biome: 'ruins', gait: 'lumber', idle: 'breathe',
  body: 'stone', accent: 'gold', hard: 'chrome', core: null,
  frames: 4, period: 1100, bob: 1, sway: 1, phase: 0.75,
  rows: [
    '...ooooo.......ooooo....',
    '..oaaaaao.....oaaaaao...',
    '..ogggggo.....ogggggo...',
    '.ooBBBBBoo...ooBBBBBoo..',
    'oaBBBBBBBao.oaBBBBBBBao.',
    'oBBwBBwBBBoooBBBBBBBBBo.',
    'oBBeBBeBBBBBBBBBBBBBBBo.',
    'oBBBBBBBBBBBBBBBBBBBBBo.',
    'oaBBBBBBBBBBBBBBBBBBBao.',
    '.ooBBBBBBBBBBBBBBBBBoo..',
    '..oBBBoooBBBBooooBBBo...',
    '..oBBo...oBBo....oBBo...',
    '..oggo...oggo....oggo...',
    '..oooo...oooo....oooo...',
  ],
  wing: null,
  head: [3, 9], headX: [0, 10], spine: [3, 10],
  legs: [[2, 5], [9, 12], [17, 20]], legTop: 11, tail: null, tailX: null,
};

/* The Coliseum. A sand floor, a clock, and no hints — so the jackal is drawn
 * lean, plain and fast, with nothing decorative on it anywhere. */
M.sandjackal = {
  family: 'NEUTRAL', biome: 'arena', gait: 'fourbeat', idle: 'breathe',
  body: 'bone', accent: 'leather', hard: 'bone', core: null,
  frames: 4, period: 420, bob: 1, sway: 0, phase: 0.15,
  rows: [
    '................oo.oo...',
    '...............oaooao...',
    '..oo...........oaBBao...',
    '.oaBo.........ooBBBBo...',
    'oaBBBoooooooooBBBwBBo...',
    'oBBBBBBBBBBBBBBBBeBggo..',
    '.oBBBBBBBBBBBBBBBBBggo..',
    '..oBBBBBBBBBBBBBBBBoo...',
    '..oBBoBBBoBBBBoBBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..oBo.oBo.oBBo.oBBo.....',
    '..ogo.ogo.oggo.oggo.....',
    '..ooo.ooo.oooo.oooo.....',
  ],
  wing: null,
  head: [0, 7], headX: [13, 22], spine: [4, 8],
  legs: [[2, 4], [6, 8], [10, 13], [15, 18]], legTop: 9,
  tail: [2, 5], tailX: [0, 4],
};

/* A column of lifted sand. Legless, neutral, and the one place a neutral region
 * gets to use the elemental gait: it rises, it frays at the bottom, and it is
 * never in contact with the floor of the arena. */
M.sanddervish = {
  family: 'NEUTRAL', biome: 'arena', gait: 'hover', idle: 'pulse',
  body: 'bone', accent: 'leather', hard: 'bone', core: null,
  frames: 3, period: 900, bob: 2, sway: 2, phase: 0.55,
  oy: 1,
  rows: [
    '.........oaaao..........',
    '........oaBBBao.........',
    '.......oaBBBBBao........',
    '......oaBBwBBwBao.......',
    '......oaBBeBBeBao.......',
    '.......oaBBBBBao........',
    '........oaBBBao.........',
    '.........oaBao..........',
    '........oaBBBao.........',
    '.......oaBBBBBao........',
    '......oaBBBBBBBao.......',
    '.....oaBBBBBBBBBao......',
    '......oaBBBBBBBao.......',
    '.......oaBBBBBao........',
    '........oaBBBao.........',
    '.........oaBao..........',
    '........oaBBBao.........',
    '.......oaBBBBBao........',
    '......oaBBBBBBBao.......',
    '.....oBBoBBBoBBBo.......',
    '......o.oo.o..oo........',
  ],
  wing: null,
  head: [0, 7], headX: [6, 17], spine: [8, 18],
  legs: [], legTop: MON_SIZE, fray: [18, 20], tail: null, tailX: null,
};

/* ================================================================
 * THE FALLBACKS
 * ================================================================
 * Two bodies with nothing on them. No markings, no species, no face worth
 * reading — deliberately, because the job here is to be plausible in a region
 * without claiming to be one of that region's creatures. A key that lands on
 * one of these is a key nobody has drawn yet, and monsterIsAuthored() says so
 * out loud rather than letting the sprite lie about it.
 */

M.strayling = {
  family: 'NEUTRAL', gait: 'fourbeat', idle: 'breathe', fallback: true,
  body: 'cloth', accent: 'cloth', hard: 'bone', core: null,
  frames: 4, period: 700, bob: 1, sway: 0, phase: 0.00,
  rows: [
    '.......oooooooo.........',
    '.....ooBBBBBBBBoo.......',
    '....oBBBBBBBBBBBBo......',
    '...oBBBBBBBBBBBBBBo.....',
    '...oBBwBBBBBBBBwBBo.....',
    '...oBBeBBBBBBBBeBBo.....',
    '...oBBBBBBBBBBBBBBo.....',
    '...oBBBBBBBBBBBBBBo.....',
    '....oBBBBBBBBBBBBo......',
    '....oBBoBBBBBBoBBo......',
    '....oBo.oBBBBo.oBo......',
    '....oBo.oBBBBo.oBo......',
    '....oBo.oBBBBo.oBo......',
    '....ogo.ogoogo.ogo......',
    '....ooo.ooooooo.ooo.....',
  ],
  wing: null,
  head: [0, 8], headX: [3, 18], spine: [3, 9],
  legs: [[4, 6], [8, 10], [11, 13], [15, 17]], legTop: 10,
  tail: null, tailX: null,
};

M.straywisp = {
  family: 'NEUTRAL', gait: 'hover', idle: 'drift', fallback: true,
  body: 'cloth', accent: 'cloth', hard: 'bone', core: null,
  frames: 3, period: 1300, bob: 2, sway: 1, phase: 0.00,
  oy: 3,
  rows: [
    '........oooooo..........',
    '......ooBBBBBBoo........',
    '.....oBBBBBBBBBBo.......',
    '....oBBBwBBBBwBBBo......',
    '....oBBBeBBBBeBBBo......',
    '....oBBBBBBBBBBBBo......',
    '.....oBBBBBBBBBBo.......',
    '.....oBBBBBBBBBBo.......',
    '......oBBBBBBBBo........',
    '......oBBBBBBBBo........',
    '.......oBBBBBBo.........',
    '.......oBoBBoBo.........',
    '........o.oo.o..........',
  ],
  wing: null,
  head: [0, 6], headX: [4, 18], spine: [6, 11],
  legs: [], legTop: MON_SIZE, fray: [10, 12], tail: null, tailX: null,
};

/* ================================================================
 * THE APEXES — one per region, 32x32
 * ================================================================
 * gauntlet/hunters.py had not landed when this file was written, so these are
 * keyed on REGION rather than on hunter ids. Whatever that file calls its
 * seventeen, apexKeyFor(regionId) answers, and a hunter name nobody here has
 * heard of still draws the right apex as long as it carries a region.
 *
 * The rule for all seventeen: not a scaled mob. Each is a silhouette that does
 * not occur anywhere else in its region — a different number of limbs, a
 * different axis, a different relationship with the ground. On top of that the
 * outline is thickened by one cell at draw time and a sparse aura is written
 * outside it, both of which are in the silhouette and both of which are
 * measured by monsterArtStats().
 */

const A = {};

/* Python Village. gauntlet/hunters.py calls it The Margin-Walker and describes
 * a surveyor two heads too tall in a shroud of blank unprinted board, with a
 * rectangle of paper where the face should be. So: a crossbar, a mantle and a
 * stake, and a blank plate for a head. It has no legs, which is the point — the
 * outline is a plumb line with shoulders, and nothing else in the game is drawn
 * as a vertical with a bar across it. */
A.margin_walker = {
  region: 'python_village', name: 'The Margin-Walker', family: 'NEUTRAL',
  gait: 'sway', idle: 'drift',
  body: 'cloth', accent: 'leather', hard: 'wood', core: 'gold',
  frames: 3, period: 1500, bob: 1, sway: 1, phase: 0.00,
  rows: [
    '..............oooo..............',
    '.............oggggo.............',
    '............ogBBBBgo............',
    '............ogBkkBgo............',
    '............ogBkkBgo............',
    '............ogBBBBgo............',
    '............ogBaaBgo............',
    '.............oggggo.............',
    '..............oBBo..............',
    'ooooooooooooooBBoooooooooooooooo',
    'oaaaaaaaaaaaaaBBaaaaaaaaaaaaaaao',
    'oooooooooooooBBBBooooooooooooooo',
    '.....ooo.....oBBBBo......ooo....',
    '....oaBo....oBBBBBBo....oaBo....',
    '....oaBo...oBBBBBBBBo...oaBo....',
    '....oaBo..oaBBBBBBBBao..oaBo....',
    '....oaBo..oBBBBccBBBBo..oaBo....',
    '.....oBo..oBBBBccBBBBo..oBo.....',
    '.....oBo..oaBBBBBBBBao..oBo.....',
    '.....oBo...oBBBBBBBBo...oBo.....',
    '......oo...oaBBBBBBao...oo......',
    '............oBBBBBBo............',
    '...........oBBoBBoBBo...........',
    '..........oBo.oBo.oBo...........',
    '..........oo..oBo..oo...........',
    '..............oBo...............',
    '..............oBo...............',
    '..............oBo...............',
    '..............oBo...............',
    '.............ogggo..............',
    '............oggggggo............',
    '............ooooooooo...........',
  ],
  head: [0, 8], headX: [11, 20], spine: [12, 21],
  legs: [], legTop: 32, fray: null, arms: [[0, 9, 9, 21], [22, 31, 9, 21]],
};

/* Graph Wastes. A stag of road-iron whose antlers have grown into the lattice of
 * the Wastes roads: every tine is a route and the tines connect to each other,
 * which no real antler does. The antlers are two thirds of the outline, which
 * makes it the only thing out there that is wider at the top than at the
 * bottom, and it is bigger than the ruins it walks between. */
A.lattice_stag = {
  region: 'graph_wastes', name: 'The Lattice Stag', family: 'NEUTRAL',
  gait: 'fourbeat', idle: 'breathe',
  body: 'leather', accent: 'bone', hard: 'bone', core: 'gold',
  frames: 4, period: 620, bob: 1, sway: 0, phase: 0.20,
  rows: [
    '......og..............go........',
    '.....ogo.o..........o.ogo.......',
    '.....ogoogo........ogoogo.......',
    '..o..ogggo.o......o.ogggo..o....',
    '.ogo..oggoogo....ogooggo..ogo...',
    '.ogoo..ogggggo..ogggggo..oogo...',
    '..ogggooggggggooggggggooggggo...',
    '...ogggggggggggggggggggggggo....',
    '.....ooggggggooooggggggggoo.....',
    '.......oggggo....oggggggo.......',
    '.........ogo......ogggo.........',
    '..........o........ogo..........',
    '.....ooo...........oBBo.........',
    '...ooaBooooooooooooBBBBo........',
    '..oaBBBBBBBBBBBBBBBBwBBo........',
    '.oaBBBBBBBBBBBBBBBBBeBBo........',
    'oaBBBBBBBBBBBBBBBBBBBBggo.......',
    'oBBBBBBBBBBBBBBBBBBBBBggo.......',
    '.oBBBBBBBBBBBBBBBBBBBoo.........',
    '..oBBBBBBBBBBBBBBBBBo...........',
    '..oBBBoBBBBoBBBBoBBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oBBo.oBBo.oBBo.oBBo...........',
    '..oggo.oggo.oggo.oggo...........',
    '..oooo.oooo.oooo.oooo...........',
  ],
  head: [0, 18], headX: [17, 25], spine: [13, 20],
  legs: [[2, 5], [7, 10], [12, 15], [17, 20]], legTop: 21,
  tail: [12, 16], tailX: [0, 5], fray: null, arms: null,
};

/* Hashmap Highlands. A bull carrying a mast between its horns, because the
 * plateau is the tallest metal for a day's walk and something out there was
 * always going to grow into the job. The arc between the horn tips is authored,
 * and it is in a different place on every frame. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.thunderhorn = {
  region: '', name: 'Thunderhorn', unassigned: true, family: 'LIGHTNING',
  gait: 'lumber', idle: 'pulse',
  body: 'gunmetal', accent: 'gold', hard: 'bronze', core: 'gold',
  frames: 4, period: 900, bob: 1, sway: 1, phase: 0.35,
  rows: [
    '.......ogggo......ogggo.........',
    '......oggcggo....oggcggo........',
    '......ogcccgo....ogcccgo........',
    '......oggcggoccccoggcggo........',
    '.......oggggoccccoggggo.........',
    '........oggggoccoggggo..........',
    '.....oooooggggooogggooooo.......',
    '...ooaBBBBBoggoooggooBBBBaoo....',
    '..oaBBBBBBBBoooooooBBBBBBBBao...',
    '.oaBBBBBwwBBBBBBBBBBBwwBBBBBao..',
    'oaBBBBBBeeBBBBBBBBBBBeeBBBBBBao.',
    'oBBBBBBBBBBBBggggBBBBBBBBBBBBBo.',
    'oBBBBBBBBBBBggkkggBBBBBBBBBBBBo.',
    '.oBBBBBBBBBBggkkggBBBBBBBBBBBo..',
    '..oBBBBBBBBBBggggBBBBBBBBBBBo...',
    '...oaBBBBBBBBBBBBBBBBBBBBBao....',
    '....oBBBBBBBcccccBBBBBBBBBo.....',
    '....oBBBBBBBcccccBBBBBBBBo......',
    '.....oBBBBBBBBBBBBBBBBBBo.......',
    '.....oBBBBBBBBBBBBBBBBBo........',
    '.....oBBBoBBBBBBBBoBBBBo........',
    '.....oBBo.oBBBBBBo.oBBBo........',
    '.....oBBo.oBBBBBBo.oBBBo........',
    '.....oBBo.oBBBBBBo.oBBBo........',
    '.....oBBo.oBBBBBBo.oBBBo........',
    '....ogggo.oggooggo.ogggo........',
    '....ooooo.oooooooo.ooooo........',
  ],
  head: [0, 15], headX: [5, 27], spine: [7, 20],
  legs: [[4, 9], [10, 13], [14, 18], [19, 23]], legTop: 20,
  tail: null, tailX: null, fray: null, arms: null,
};

/* Binary Tree Canopy. A long cat built for branches: six limbs, the front pair
 * held up and folded, and a spine that stays below the line of its own
 * shoulder. Up here the danger has four legs rather than a cosmology, which is
 * exactly what hunters.py asks for — and nothing else in the canopy stands on
 * four and reaches with two. */
A.bough_stalker = {
  region: 'binary_tree_canopy', name: 'The Bough Stalker', family: 'POISON',
  gait: 'stalk', idle: 'twitch',
  body: 'venom', accent: 'grass', hard: 'bone', core: 'venom',
  frames: 4, period: 760, bob: 1, sway: 0, phase: 0.50,
  rows: [
    '..........oao.....oao...........',
    '.........oaAao...oaAao..........',
    '.........oaAao...oaAao..........',
    '..........ooo.....ooo...........',
    '..oo......oao.....oao...........',
    '.oaBo......o.......o......oooo..',
    '.oaBBo.....ooooooooo....oBBBBBo.',
    '..oaBBoooooBBBBBBBBBoooBBBwBwBo.',
    '...oaBBBBBBBBBBBBBBBBBBBBBeBeBo.',
    '...oaBBBBBBBBBBBBBBBBBBBBBBggBo.',
    '...oaBBBBBBBBBBBBBBBBBBBBBggggo.',
    '....oBBBBBBBBBBBBBBBBBBBBoggggo.',
    '....oBBBBBBBcccBBBBBBBBoooggoo..',
    '....oBBBBBBBBBBBBBBBBBo.ooo.....',
    '....oBBoBBBBBBBBBBoBBBo.........',
    '....oBo.oBBBBBBBBo.oBBoo........',
    '....oBo.oBBBBBBBBo.oBBBBoo......',
    '....oBo.oBBoooBBo..oBBBBBBo.....',
    '....oBo.oBo.oBBo...ooBBBBBo.....',
    '....oBo.oBo.oBBo.....oBBBBo.....',
    '....oBo.oBo.oBBo.....oaBBao.....',
    '....oBo.oBo.oBBo......oBBo......',
    '...oggo.oggooggo......oBBo......',
    '...oooo.oooooooo.......oo.......',
  ],
  head: [5, 13], headX: [22, 31], spine: [7, 14],
  legs: [[3, 7], [8, 12], [13, 17], [18, 22]], legTop: 14,
  arms: [[8, 21, 0, 6]], tail: [15, 23], tailX: [18, 27], fray: null,
};

/* Array Caverns. Membrane, not muscle: the wings are most of the box and the
 * body hangs under them. The Caverns' mobs are an ape, a grub and a mite, all
 * of them on the floor; this is the only thing down there that is above you. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.vaultbat = {
  region: '', name: 'The Vaultwing', unassigned: true, family: 'BRUTE',
  gait: 'wingbeat', idle: 'drift',
  body: 'stone', accent: 'earth', hard: 'bone', core: 'bronze',
  frames: 3, period: 640, bob: 2, sway: 1, phase: 0.65,
  oy: 2,
  rows: [
    'oo............................oo',
    'oao..........oooo...........oao.',
    'oaBo........oBBBBo.........oaBo.',
    'oaBBo.......oBwBwo........oaBBo.',
    'oaBBBo.....ogBeBeBgo.....oaBBBo.',
    'oaBBBBo....ogBBBBBgo....oaBBBBo.',
    'oaBBBBBo...ogggBBggo...oaBBBBBo.',
    'oaBBBBBBo...oBBBBBo...oaBBBBBBo.',
    'oaBBBBBBBo.ooBBBBBoo.oaBBBBBBBo.',
    'oaBBBBBBBBooaBBBBBaooBBBBBBBBBo.',
    'oaBBBBBBBBBBBBcBcBBBBBBBBBBBBBo.',
    'oaBoBBBBBBBBBBBBBBBBBBBBBBBoBBo.',
    'oaBooBBBBBBBBBBBBBBBBBBBBBooBBo.',
    'oaBo.oBBBBBBBBBBBBBBBBBBBo.oBBo.',
    'oaBo..oBBBoBBBBBBBBBoBBBo..oBBo.',
    'ooo...oBBo.oBBBBBBBo.oBBo...ooo.',
    '......oBBo.oaBBBBBao.oBBo.......',
    '.......oo..oBBBBBBBo..oo........',
    '...........oaBBBBBao............',
    '............oBBBBBo.............',
    '............oBoBoBo.............',
    '...........ogo.o.ogo............',
    '...........ooo...ooo............',
  ],
  head: [1, 8], headX: [10, 21], spine: [9, 20],
  legs: [[11, 13], [17, 19]], legTop: 20,
  wing: [[0, 10, 0, 16], [21, 31, 0, 16]], tail: null, tailX: null, fray: null,
};

/* Sliding Window Marsh. Long, low and almost entirely horizontal — the frame
 * that slides across the reeds, with teeth. Its own region's mobs are a toad, a
 * heron and a wasp, none of which is longer than it is tall. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.mirelord = {
  region: '', name: 'The Mirelord', unassigned: true, family: 'POISON',
  gait: 'fourbeat', idle: 'breathe',
  body: 'venom', accent: 'grass', hard: 'bone', core: 'venom',
  frames: 4, period: 980, bob: 1, sway: 0, phase: 0.75,
  rows: [
    '.........oao..oao..oao..........',
    '....oo..oaBao.oaBao.oaBao.......',
    '...oaBooaBBBaoaBBBaoaBBBao......',
    '..oaBBBBBBBBBBBBBBBBBBBBBBoo....',
    '.oaBBBBBBBBBBBBBBBBBBBBBBBBBoo..',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBBBBoo',
    'oBBBBBBBBBBBBBBBBBBBBBBBwBBBwBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBBeBBBeBBo',
    'oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo',
    '.oBBBBBBBBBBBBBBBBBBBBBBBBBBBBBo',
    '..oBBBBBBBBBBBBBBBBBBBogBgBgBgBo',
    '...oBBBBBBBBBBBBBBBBBBogggggggoo',
    '....oBBBoBBBBBBoBBBBBBoooooooo..',
    '....oBBo.oBBBBo.oBBBBo..........',
    '....oBBo.oBBBBo.oBBBBo..........',
    '....oBBo.oBBBBo.oBBBBo..........',
    '...oggo..oggggo.oggggo..........',
    '...oooo..oooooo.oooooo..........',
  ],
  head: [0, 12], headX: [20, 31], spine: [3, 12],
  legs: [[3, 7], [8, 14], [15, 21]], legTop: 12,
  tail: [1, 5], tailX: [0, 6], fray: null, arms: null,
};

/* Twin Pointer Pass. The brief's ice elemental, at apex scale: broad at the
 * shoulder, tapering to a fray that is never the same two frames running, and
 * with no feet anywhere in the grid. It does not walk the Pass; it is carried
 * down it. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.hoarcolossus = {
  region: '', name: 'The Hoar Colossus', unassigned: true, family: 'COLD',
  gait: 'hover', idle: 'pulse',
  body: 'frost', accent: 'cyan', hard: 'chrome', core: 'cyan',
  frames: 3, period: 1800, bob: 2, sway: 1, phase: 0.10,
  oy: 1,
  rows: [
    '.........o.........o............',
    '........oao.......oao...........',
    '.......oaBo...o...oaBo..........',
    '......oaBBo..oao..oaBBo.........',
    '.....oaBBBooaBBBooaBBBBo........',
    '.....oaBBBBBBBBBBBBBBBBo........',
    '....oaBBBBBBBBBBBBBBBBBBo.......',
    '....oaBBBcccccccccBBBBBBo.......',
    '....oaBBcCwwwCCwwwCcBBBBo.......',
    '....oaBBcCcccccccCcBBBBBo.......',
    '....oaBBBcccccccccBBBBBBo.......',
    'oo..oaBBBBBBBBBBBBBBBBBBo..oo...',
    'oao.oaBBBBBBBBBBBBBBBBBBBo.oao..',
    'oaBooaBBBBBBBBBBBBBBBBBBBooaBo..',
    'oaBBoaBBBBBCCCCCCCBBBBBBBBoaBBo.',
    'oaBBBoBBBBBCcccccCBBBBBBBoaBBBo.',
    'oaBBBoBBBBBCCCCCCCBBBBBBBoaBBBo.',
    'oaBBBooBBBBBBBBBBBBBBBBBooaBBBo.',
    'oaBBBo.oBBBBBBBBBBBBBBBo.oaBBBo.',
    '.oaBBo..oBBBBBBBBBBBBBo..oaBBo..',
    '..oaBo...oBBBBBBBBBBBo...oaBo...',
    '..ooo.....oBBBBBBBBBo.....ooo...',
    '...........oBBBBBBBo............',
    '...........oBBBBBBo.............',
    '............oBBBBo..............',
    '............oBBBo...............',
    '.............oBo................',
    '.............ooo................',
  ],
  head: [2, 11], headX: [3, 26], spine: [6, 21],
  legs: [], legTop: 32, fray: [21, 27], tail: null, tailX: null,
  arms: [[0, 5, 11, 21], [25, 31, 11, 21]],
};

/* Stack & Queue Mines. The brief asked for a phoenix and hunters.py named one:
 * a bird of ore-cart iron and flame whose wings are stacked plates that unload
 * from the top, one at a time, and burn on the way down. Its legs are lift
 * cable. It is the only creature in the game whose wingspan touches both walls
 * of its own box, with twin tail streamers below and a crest above. */
A.cinder_phoenix = {
  region: 'stack_queue_mines', name: 'The Cinder Phoenix', family: 'FIRE',
  gait: 'wingbeat', idle: 'preen',
  body: 'ember', accent: 'gold', hard: 'bone', core: 'ember',
  frames: 3, period: 700, bob: 2, sway: 0, phase: 0.40,
  oy: 0,
  rows: [
    '..............oo................',
    '.............oaoo...............',
    '............oao.o...............',
    '............oBBBo...............',
    '...........oBBwBBo..............',
    '...........oBBeBBoggo...........',
    '...........oBBBBBoggo...........',
    '.o..........oBBBo...........o...',
    'oao.........oBBBo..........oao..',
    'oaBo.......oBBBBBo........oaBo..',
    'oaBBo.....oBBBBBBBo......oaBBo..',
    'oaBBBoooooBBBBBBBBBooooooaBBBo..',
    'oaBBBBBBBBBBBcBcBBBBBBBBBBBBBo..',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBBBo..',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBBBo..',
    '.oaBBBBoBBBBBBBBBBBBBoBBBBBao...',
    '..oaaooooBBBBBBBBBBBooooaao.....',
    '.........oBaBBBBBaBo............',
    '.........oBBBBBBBBBo............',
    '..........oBBBBBBBo.............',
    '..........oBBoBBBo..............',
    '.........ogoo.oogo..............',
    '.........ogo...ogo..............',
    '........oggo...oggo.............',
    '........ooo.....ooo.............',
    '.......oao.......oao............',
    '......oaco.......ocao...........',
    '.....oaco.........ocao..........',
    '.....oco...........oco..........',
    '.....oc..............co.........',
    '.....o................o.........',
  ],
  head: [0, 7], headX: [10, 20], spine: [11, 20],
  legs: [[8, 12], [14, 18]], legTop: 21,
  wing: [[0, 9, 7, 17], [20, 30, 7, 17]], tail: [25, 30], tailX: [4, 22],
  fray: null, arms: null,
};

/* Matrix Citadel. A knight cast into the Citadel floor and prised back out of
 * it, so the armour has been through four rotations and settled into none: the
 * pauldrons face forward, the helm faces left, the greaves face back. It walks
 * without turning. The cutout is a human figure assembled from four different
 * human figures, which is the region's own ninety-degree trick wearing a face. */
A.fourth_orientation = {
  region: 'matrix_citadel', name: 'The Fourth Orientation', family: 'BRUTE',
  gait: 'lumber', idle: 'breathe',
  body: 'stone', accent: 'gold', hard: 'chrome', core: 'gold',
  frames: 4, period: 1400, bob: 1, sway: 0, phase: 0.85,
  rows: [
    '..........oooooooooo............',
    '.........oggggggggggo...........',
    '.........ogaaaaaaaago...........',
    '.........oggggggggggo...........',
    '..........oBBBBBBBBo............',
    '..........oBwwBBwwBo............',
    '..........oBeeBBeeBo............',
    '..........oBBBBBBBBo............',
    '.......ooooBBBggBBBoooo.........',
    '.....ooaaaoBBBggBBBoaaaoo.......',
    '...ooaaaoooBBBBBBBBooooaaaoo....',
    '..oggggo..oBBBBBBBBo..ogggggo...',
    '.oggggo.oooBBccccBBooo.ogggggo..',
    '.ogggo.oaaoBBccccBBoaao.oggggo..',
    '.oggo.oaaaoBBBBBBBBoaaao.oggo...',
    '.ooo.oggggoBBBBBBBBoggggo.ooo...',
    '.....ogggooBBBBBBBBooggggo......',
    '.....oggo.oBBBBBBBBo.oggo.......',
    '.....ooo..oBBBBBBBBo..ooo.......',
    '..........oBBBBBBBBo............',
    '.........ooBBBoBBBBoo...........',
    '........oggBBo.oBBggo...........',
    '........oggBBo.oBBggo...........',
    '........oggBBo.oBBggo...........',
    '.......oggggo...oggggo..........',
    '.......oggggo...oggggo..........',
    '.......oooooo...oooooo..........',
  ],
  head: [0, 7], headX: [9, 21], spine: [8, 20],
  legs: [[7, 13], [15, 21]], legTop: 20,
  arms: [[0, 9, 8, 18], [21, 31, 8, 18]], tail: null, tailX: null, fray: null,
};

/* Recursive Forest. One figure at three sizes in a single outline: a walker
 * stepping into a smaller copy of itself, which is stepping into a smaller copy
 * of itself, and the smallest is not finished. The region's own physical
 * description is that every clearing contains a smaller copy of the forest, so
 * its hunter is the only creature in the game whose silhouette contains its own
 * silhouette. Nothing about it resolves, and that is correct. */
A.unreturning = {
  region: 'recursive_forest', name: 'The Unreturning', family: 'VOID',
  gait: 'hover', idle: 'drift',
  body: 'void', accent: 'violet', hard: 'bone', core: 'violet',
  frames: 3, period: 2000, bob: 2, sway: 2, phase: 0.55,
  oy: 1,
  rows: [
    '...........oooooooo.............',
    '.........ooaaaaaaaaoo...........',
    '........oaBBBBBBBBBBao..........',
    '.......oaBBkkkkkkkkBBao.........',
    '.......oaBkkcccccckkBao.........',
    '......oaBBkcwwwwwwckBBao........',
    '......oaBBkkcccccckkBBao........',
    '.....oaBBBBkkkkkkkkBBBBao.......',
    '.....oaBBBBBkkkkkkBBBBBao.......',
    '....oaBBBBBBBBBBBBBBBBBBao......',
    '....oaBBBoooooooooooBBBBao......',
    '...oaBBBBoaaaaaaaaaoBBBBBao.....',
    '...oaBBBBoaBBkkkkBaoBBBBBao.....',
    '..oaBBBBBoaBkcccckBoBBBBBBao....',
    '..oaBBBBBoaBkcwwckBoBBBBBBao....',
    '..oaBBBBBoaBBkkkkBaoBBBBBBao....',
    '.oaBBBBBBoaBooooooBaoBBBBBBao...',
    '.oaBBBBBBoaBoaaaaoBaoBBBBBBao...',
    'oaBBBBBBBoaBoaBkBaoBaoBBBBBBBao.',
    'oaBBBBBBBoaBoaBkBaoBaoBBBBBBBao.',
    'oaBBBBBBBoaBoaaaaoBaoBBBBBBBBao.',
    'oaBBBBBBBoaBooooooBaoBBBBBBBBao.',
    '.oBBBBBBBoaBBBBBBBBaoBBBBBBBBo..',
    '.oBBBBBBBBoaaaaaaaaoBBBBBBBBo...',
    '..oBBBBBBBBoooooooooBBBBBBBBo...',
    '..oBBBBBBBBBBBBBBBBBBBBBBBBo....',
    '...oBBBBBBBBBBBBBBBBBBBBBBo.....',
    '...oBoBBBoBBBoBBBoBBBoBBBoo.....',
    '....o.oBo.oBo.oBo.oBo.oBo.......',
    '......o...o....o...o...o........',
  ],
  head: [0, 9], headX: [4, 27], spine: [9, 26],
  legs: [], legTop: 32, fray: [26, 29], tail: null, tailX: null, arms: null,
};

/* Stringwood Labyrinth. A great owl whose feathers are letters laid like
 * shingles and whose crown is a fruiting body grown through the skull from the
 * inside. It shakes spores the way an owl shakes rain. The cutout is a wide low
 * wedge — the only bird in the game drawn wider than it is tall — with a head
 * that is half the body. */
A.sporecrown = {
  region: 'stringwood_labyrinth', name: 'The Sporecrown', family: 'NEUTRAL',
  gait: 'wingbeat', idle: 'preen',
  body: 'wood', accent: 'bone', hard: 'bone', core: 'gold',
  frames: 3, period: 1200, bob: 1, sway: 0, phase: 0.25,
  rows: [
    '.....oo..................oo.....',
    '....oaao................oaao....',
    '....oaBao..............oaBao....',
    '.....oaBBoooooooooooooooaBBo....',
    '......oaBBBBBBBBBBBBBBBBBBBo....',
    '.....oaBBBBBBBBBBBBBBBBBBBBBo...',
    '....oaBBBBwwwwBBBBwwwwBBBBBBBo..',
    '...oaBBBBwwwwwwBBwwwwwwBBBBBBo..',
    '...oaBBBBwweewwooweewwBBBBBBBo..',
    '..oaBBBBBwwwwwwggwwwwwwBBBBBBo..',
    '..oaBBBBBBwwwwggggwwwwBBBBBBBo..',
    '..oaBBBBBBBBBBggggBBBBBBBBBBBo..',
    '.oaBBBBBBBBBBBBggBBBBBBBBBBBBo..',
    '.oaBBaBBaBBaBBBBBBaBBaBBaBBBBo..',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBBBo..',
    'oaBBaBBaBBaBBcccBBaBBaBBaBBBBo..',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBBo...',
    '.oaBBaBBaBBaBBBBaBBaBBaBBBBo....',
    '.oaBBBBBBBBBBBBBBBBBBBBBBBo.....',
    '..oaBBBBBBBBBBBBBBBBBBBBBo......',
    '...oaaBBBBBBBBBBBBBBBBBao.......',
    '.....ooaaBBBBBBBBBBBaao.........',
    '........ooBBBooBBBoo............',
    '.........oggo..oggo.............',
    '........oggggooggggo............',
    '........oooooooooooo............',
  ],
  head: [3, 13], headX: [2, 29], spine: [13, 21],
  legs: [[8, 12], [14, 18]], legTop: 22,
  wing: [[0, 6, 0, 21], [24, 31, 0, 21]], tail: null, tailX: null, fray: null,
};

/* Fields of Syntax. A harvester on stilt legs, tall and mostly empty, with a
 * drum of hooked blades where a body should be. The drum turns whether or not
 * it is cutting. Read as a cutout it is a wheel held up on insect legs and the
 * legs are longer than the wheel is wide, which in a region whose mobs are a
 * hopper and a grass snake is the loudest possible arrival. */
A.thresher = {
  region: 'fields_of_syntax', name: 'The Thresher', family: 'LIGHTNING',
  gait: 'stalk', idle: 'pulse',
  body: 'rust', accent: 'gold', hard: 'gunmetal', core: 'gold',
  frames: 4, period: 1100, bob: 1, sway: 0, phase: 0.95,
  rows: [
    '...............oo...............',
    '..............ocoo..............',
    '.............oco.o..............',
    '............oco.................',
    '...........ogggggggo............',
    '..........oggcccccggo...........',
    '.........oggcgggggcggo..........',
    '.........ogcgwgggwgcgo..........',
    '.........oggcgggggcggo..........',
    '.........oggcccccccggo..........',
    '..........ogggggggggo...........',
    '...oo......oggkkkggo......oo....',
    '..oaBoooooooBBBBBBBoooooooaBo...',
    '..oaBBBBBBBBBcccccBBBBBBBBBBo...',
    '..oaBBBoBBBBBBBBBBBBBBBoBBBBo...',
    '..oaBBo.oBBBBBBBBBBBBBo.oBBBo...',
    '...ooo..oBBo.......oBBo..ooo....',
    '........oBo.........oBo.........',
    '.......oBo...........oBo........',
    '.......oBo...........oBo........',
    '......oBo.............oBo.......',
    '......oBo.............oBo.......',
    '.....oBo...............oBo......',
    '.....oBo...............oBo......',
    '....oBo.................oBo.....',
    '....oBo.................oBo.....',
    '...oBo...................oBo....',
    '...oBo...................oBo....',
    '..ogo.....................ogo...',
    '.oggo.....................oggo..',
    '.oooo.....................oooo..',
  ],
  head: [0, 11], headX: [8, 22], spine: [12, 16],
  legs: [[1, 9], [5, 12], [19, 26], [22, 30]], legTop: 16,
  arms: [[2, 6, 11, 16], [25, 29, 11, 16]], tail: null, tailX: null, fray: null,
};

/* Dynamic Programming Ruins. A lion with a mask where its face should be, lying
 * where the solved tiles are already lit. Long and horizontal, gilded along the
 * back, and the only creature in the game whose head is a flat plate. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.memoriam = {
  region: '', name: 'The Memoriam', unassigned: true, family: 'NEUTRAL',
  gait: 'fourbeat', idle: 'breathe',
  body: 'bone', accent: 'gold', hard: 'goldleaf', core: 'gold',
  frames: 4, period: 1000, bob: 1, sway: 0, phase: 0.45,
  rows: [
    '......................oooooo....',
    '.....................ogggggggo..',
    '...................oogaaaaaago..',
    '..................oggggggggggo..',
    '..................ogAAgAAgAAgo..',
    '.........oo.......ogAwgAAgAwgo..',
    '........oaBo......ogAegAAgAego..',
    '.......oaBBBo.....ogAAgAAgAAgo..',
    '.....ooaBBBBBoooooggggggggggo...',
    '..oooaBBBBBBBBBBBBBBBgggggoo....',
    '.oaBBBBBBBBBBBBBBBBBBBBBBo......',
    'oaBBBBaaaaaaaaaaaaaaaBBBBBo.....',
    'oBBBBBBBBBBBBBBBBBBBBBBBBBo.....',
    'oBBBBBBBBBBBccccBBBBBBBBBo......',
    '.oBBBBBBBBBBBBBBBBBBBBBBo.......',
    '..oBBBBBBBBBBBBBBBBBBBBo........',
    '..oBBBoBBBBoBBBBBoBBBBBo........',
    '..oBBo.oBBo.oBBBo.oBBBBo........',
    '..oBBo.oBBo.oBBBo.oBBBBo........',
    '..oBBo.oBBo.oBBBo.oBBBBo........',
    '..oBBo.oBBo.oBBBo.oBBBBo........',
    '..oBBo.oBBo.oBBBo.oBBBBo........',
    '.oggggooggggoggggooggggggo......',
    '.oooooooooooooooooooooooo.......',
  ],
  head: [0, 9], headX: [17, 30], spine: [9, 16],
  legs: [[2, 5], [7, 10], [12, 16], [18, 23]], legTop: 16,
  tail: [5, 9], tailX: [5, 12], fray: null, arms: null,
};

/* Debugging Dungeon, which world.py calls the Armorer's forge. A furnace-bellied
 * figure hung with cracked plate, dragging the cells' failed armour behind it.
 * The belly is open and lit. It is also the only ASYMMETRIC silhouette in the
 * game — one arm short and down, the other holding a hammer head above the
 * shoulder line — which is deliberate: every other heavy thing in the roster is
 * bilateral, and without it the Citadel's knight and this were nineteen outline
 * pixels apart at 16px, which is two golems with different names. */
A.slagmother = {
  region: 'debugging_dungeon', name: 'The Slagmother', family: 'FIRE',
  gait: 'lumber', idle: 'pulse',
  body: 'iron', accent: 'ember', hard: 'bronze', core: 'ember',
  frames: 4, period: 1300, bob: 1, sway: 1, phase: 0.05,
  rows: [
    '.........................oooooo.',
    '..........oooooooo.......oggggo.',
    '.........oggggggggo......oggggo.',
    '.........ogBBBBBBgo......oggggo.',
    '.........ogBwwBwwgo......ooggoo.',
    '.........ogBeeBeego........oBo..',
    '.........oggBBBBggo.......oBBo..',
    '.........ogccccccgo......oaBBo..',
    '.......ooooBBBBBoooo....oaBBo...',
    '.....ooaaaoBBBBBoaaaooooaBBo....',
    '..oooaaaoooBBBBBooaaaaaaBBo.....',
    '..ogggo...oBBBBBBBoooooooo......',
    '..ogggo..ooBBBBBBBoo............',
    '..oggo..oaBBccccccBBao..........',
    '..ooo..oaBBccCCCCccBBao.........',
    '.......oaBccCkkkkCccBao.........',
    '.......oaBccCkkkkCccBao.........',
    '.......oaBBccCCCCccBBao.........',
    '........oaBBccccccBBao..........',
    '........oaBBBBBBBBBBao..........',
    '.........oBBBBBBBBBBo...........',
    '.........oBBBoBBBBBBo...........',
    '........ogBBo.oBBBBgo...........',
    '........ogBBo.oBBBBgo...........',
    '........ogBBo.oBBBBgo...........',
    '.......oggggo.ogggggo...........',
    '.......oggggo.ogggggo...........',
    '.......oooooo.oooooo............',
  ],
  head: [0, 7], headX: [9, 19], spine: [8, 21],
  legs: [[7, 13], [14, 20]], legTop: 21,
  arms: [[2, 8, 9, 14], [20, 31, 0, 11]], tail: null, tailX: null, fray: null,
};

/* Complexity Tower. A serpent stood on end: every coil above the last one costs
 * more to climb, which is the region's own rule drawn as an animal. Vertical,
 * legless, and the tallest silhouette in the game. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.spirewyrm = {
  region: '', name: 'The Spirewyrm', unassigned: true, family: 'COLD',
  gait: 'slither', idle: 'coil',
  body: 'cyan', accent: 'frost', hard: 'chrome', core: 'cyan',
  frames: 4, period: 1500, bob: 0, sway: 2, phase: 0.30,
  rows: [
    '..........oooo..................',
    '.........oBBBBo.................',
    '........oBBwwBBoggo.............',
    '........oBBeeBBoggggo...........',
    '........oBBBBBBggggggo..........',
    '.........oBBBBBBoooooo..........',
    '.........oaBBBao................',
    '........ooBBBBBoo...............',
    '.......oaBBBBBBBao..............',
    '......oaBBBcccBBBao.............',
    '......oBBBBBBBBBBBo.............',
    '.....oaBBBBBBBBBBBBo............',
    '.....oBBBBBBBBBBBBBBo...........',
    '....oaBBBBBBBBBBBBBBBo..........',
    '....oBBBBBBcccccBBBBBBo.........',
    '...oaBBBBBBBBBBBBBBBBBo.........',
    '...oBBBBBBBBBBBBBBBBBBBo........',
    '..oaBBBBBBBBBBBBBBBBBBBo........',
    '..oBBBBBBBBBBBBBBBBBBBBBo.......',
    '.oaBBBBBBBBcccccccBBBBBBo.......',
    '.oBBBBBBBBBBBBBBBBBBBBBBBo......',
    'oaBBBBBBBBBBBBBBBBBBBBBBBo......',
    'oBBBBBBBBBBBBBBBBBBBBBBBBBo.....',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBo.....',
    'oBBBBBBBBBBBBBBBBBBBBBBBBBBo....',
    'oaBBBBBBBBBBBBBBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBBBBBBBBBBo....',
    '.ooooooooooooooooooooooooooo....',
  ],
  head: [0, 6], headX: [7, 21], spine: [7, 26],
  legs: [], legTop: 32, tail: [22, 27], tailX: [0, 27], fray: null, arms: null,
};

/* The Coding Coliseum. A gladiator of compacted sand and fused glass carrying a
 * clock face as a shield — a sand floor, a clock, and no hints, assembled into
 * one animal. It is the only apex whose outline reads as a person doing a job,
 * and the only thing in the game shaped like the player. That is the meanest
 * joke the bestiary makes and it is made on purpose. */
A.sand_champion = {
  region: 'coding_coliseum', name: 'The Sand Champion', family: 'NEUTRAL',
  gait: 'lumber', idle: 'breathe',
  body: 'bronze', accent: 'blood', hard: 'chrome', core: 'gold',
  frames: 4, period: 800, bob: 1, sway: 1, phase: 0.60,
  rows: [
    '..............oaao..............',
    '.............oaaaao.............',
    '............oaaoaaoo............',
    '...........oaao.oaao............',
    '..........ooooooooooo...........',
    '.........oggggggggggo...........',
    '.........ogwwgggwwggo...........',
    '.........ogeegggeeggo.....o.....',
    '.........oggggggggggo....ogo....',
    '..........ogggggggo.....oggo....',
    '....oooo...oggggggo....oggggo...',
    '...ogggo...ooBBBBoo...oggggo....',
    '..oggggoooogBBBBBBgoooggggo.....',
    '..ogggggggggBBccBBggggggggo.....',
    '..oggaaaggggBBccBBgggggggo......',
    '..ogggaaggggBBBBBBgggggggo......',
    '..oggggggogoBBBBBBogogggo.......',
    '..ogggggo.ogBBBBBBgo.ogo........',
    '...ooooo..ogBBBBBBgo............',
    '..........ogBBBBBBgo............',
    '..........oggBBBBggo............',
    '..........oBBBoBBBBo............',
    '.........ogBBo.oBBBgo...........',
    '.........ogBBo.oBBBgo...........',
    '.........ogBBo.oBBBgo...........',
    '........oggggo.ogggggo..........',
    '........oggggo.ogggggo..........',
    '........oooooo.oooooo...........',
  ],
  head: [0, 9], headX: [9, 20], spine: [10, 21],
  legs: [[8, 13], [14, 20]], legTop: 21,
  arms: [[2, 9, 10, 18], [19, 27, 7, 17]], tail: null, tailX: null, fray: null,
};

/* The Null King's Castle. The brief asked for skeletons in the void, so the
 * last apex is the one the rest of the castle is made of, wearing a crown with
 * nothing under it. Robed, so there are no legs in the outline at all — it is
 * the shade's silhouette with a skull and a crown added, which is the one place
 * in this roster where two apexes are allowed to rhyme. *
 * NOT CURRENTLY A HUNTER. gauntlet/hunters.py gives this region a different
 * animal; this one is kept, drawn and measured so a later pass has it. */
A.bonecrown = {
  region: '', name: 'The Bonecrown', unassigned: true, family: 'VOID',
  gait: 'hover', idle: 'rattle',
  body: 'bone', accent: 'void', hard: 'goldleaf', core: 'violet',
  frames: 3, period: 1700, bob: 1, sway: 1, phase: 0.70,
  oy: 0,
  rows: [
    '.....og....og....go....go.......',
    '.....ogo..ogo..ogo..ogo.........',
    '.....oggooggooggooggoggo........',
    '.....oggggggggggggggggo.........',
    '.....ogaaaaaaaaaaaaaago.........',
    '.....oggggggggggggggggo.........',
    '.......oggggggggggggo...........',
    '.......ogggggggggggo............',
    '.......ogkkggggkkggo............',
    '.......ogkcggggkcggo............',
    '.......oggkkggkkgggo............',
    '.......oggggggggggo.............',
    '........ogogogogoo..............',
    '.........oggggggo...............',
    '.......ooooBBBooooo.............',
    '....oooaaaoBBBoaaaoooo..........',
    '..ooaaaBBBoBBBoBBBaaaooo........',
    '.oaBBBBBBBBBBBBBBBBBBBBao.......',
    'oaBBBBBBBBBBcccBBBBBBBBBao......',
    'oaBBBBBBBBBcCCCcBBBBBBBBao......',
    'oaBBBBBBBBBBcccBBBBBBBBBao......',
    '.oBBBBBBBBBBBBBBBBBBBBBBo.......',
    '.oaBBBBBBBBBBBBBBBBBBBBao.......',
    '..oBBBBBBBBBBBBBBBBBBBBo........',
    '..oaBBBBBBBBBBBBBBBBBBao........',
    '...oBBBBBBBBBBBBBBBBBBo.........',
    '...oBBBBBBBBBBBBBBBBBo..........',
    '...oBoBBBoBBBoBBBoBBBoo.........',
    '....o.oBo.oBo.oBo.oBo...........',
    '......o...o....o...o............',
  ],
  head: [0, 13], headX: [4, 23], spine: [14, 27],
  legs: [], legTop: 32, fray: [25, 29],
  arms: [[0, 8, 14, 21], [17, 25, 14, 21]], jaw: [10, 13], jawX: [6, 19],
  tail: null, tailX: null,
};

/* Hashmap Highlands. A lightning rod wearing a crown it cannot put down: one
 * grounded spike, a shaft, and a ring of spent vault keys turning around a
 * keyhole with nothing behind it. It is the only creature in the game whose
 * silhouette is a vertical line with a halo on top, and the only one whose
 * animation is a rotation rather than a step. */
A.storm_ordinal = {
  region: 'hashmap_highlands', name: 'The Storm Ordinal', family: 'LIGHTNING',
  gait: 'orbit', idle: 'pulse',
  body: 'gunmetal', accent: 'gold', hard: 'bronze', core: 'gold',
  frames: 4, period: 1200, bob: 0, sway: 1, phase: 0.35,
  rows: [
    '.............ogo................',
    '............ogcgo...............',
    '...ogo......ogcgo......ogo......',
    '..ogcgo.....ogcgo.....ogcgo.....',
    '..ogggo.ooo.ogggo.ooo.ogggo.....',
    '..oggo.oaggo.ogo.oggao.oggo.....',
    '.oggo.ogggggoooogggggo.oggo.....',
    '.oggo.oggkkggggggkkggo.oggo.....',
    '.oggo.oggkkggkkggkkggo.oggo.....',
    '.oggo.ogggggokkoggggo..oggo.....',
    '..oggo..ogggokkogggo..oggo......',
    '..oggo...ooggkkggoo...oggo......',
    '...ogo....ooggggoo.....ogo......',
    '...ogo.....oaBBao......ogo......',
    '....o.....oaBBBBao......o.......',
    '..........oBBccBBo..............',
    '.........oaBBccBBBao............',
    '.........oBBBccBBBBo............',
    '.........oaBBccBBBao............',
    '..........oBBccBBo..............',
    '..........oBBccBBo..............',
    '...........oBccBo...............',
    '...........oBccBo...............',
    '...........oBccBo...............',
    '...........oBccBo...............',
    '...........oBccBo...............',
    '...........oggggo...............',
    '............oggo................',
    '............ogo.................',
    '............ogo.................',
    '.............oo.................',
    '.............o..................',
  ],
  head: [0, 14], headX: [0, 31], spine: [13, 26],
  legs: [], legTop: 32, fray: null, tail: null, tailX: null, arms: null,
  orbit: [[0, 31, 0, 14]],
};

/* Array Caverns. An anvil that has been given a stoop: shoulder-heavy, short in
 * the leg, and carrying the whole cavern roof. A single cut zero is scored
 * across the chest, deep, because the alcoves here are numbered from zero and
 * this is what the first one weighs. */
A.zeroth_weight = {
  region: 'array_caverns', name: 'The Zeroth Weight', family: 'BRUTE',
  gait: 'lumber', idle: 'breathe',
  body: 'stone', accent: 'gold', hard: 'chrome', core: 'gold',
  frames: 4, period: 1400, bob: 1, sway: 0, phase: 0.85,
  rows: [
    '.........oooooooooooo...........',
    '........ogggggggggggggo.........',
    '.......oggBBBBBBBBBBggo.........',
    '.......ogBBwwBBBBwwBBgo.........',
    '.......ogBBeeBBBBeeBBgo.........',
    '.......oggBBBBggBBBBggo.........',
    '......oooggggggggggggooo........',
    '...oooaaaooggggggggooaaaooo.....',
    '..oaaaaaaaoBBBBBBBBoaaaaaaao....',
    '.oaggggggaoBBBBBBBBoaggggggao...',
    'oaggggggggoBBBBBBBBoggggggggao..',
    'oaggggggggoBBBBBBBBoggggggggao..',
    'oaggggggggoBBBBBBBBoggggggggao..',
    'oaggggggg.oBBoooBBo.gggggggggo..',
    'ooggggggo.oBoaaaoBo.oggggggoo...',
    '.ooooooo..oBoaoaoBo..ooooooo....',
    '..........oBoaoaoBo.............',
    '..........oBoaaaoBo.............',
    '.........ooBBoooBBoo............',
    '........oaBBBBBBBBBBao..........',
    '.......oaBBBBBBBBBBBBao.........',
    '......oaBBBBBBBBBBBBBBao........',
    '......oBBBBBBBBBBBBBBBBo........',
    '......oBBBBoooooooBBBBBo........',
    '......oBBBo.......oBBBBo........',
    '.....ogBBBo.......oBBBBgo.......',
    '.....ogBBBo.......oBBBBgo.......',
    '....oggggggo.....oggggggo.......',
    '....oggggggo.....oggggggo.......',
    '....oooooooo.....oooooooo.......',
  ],
  head: [0, 8], headX: [6, 23], spine: [7, 22],
  legs: [[4, 11], [17, 24]], legTop: 23,
  arms: [[0, 9, 7, 15], [22, 31, 7, 15]], tail: null, tailX: null, fray: null,
};

/* Sliding Window Marsh. A drowned lamp-carrier holding one corner of a frame
 * with four corners, in seven hands, so the frame never closes — which is the
 * joke the region has been making since the player arrived. Read as a cutout it
 * is a wading bird made of held-up rectangles, and the lamp is inside the frame
 * lighting the reeds from the wrong side. */
A.fenlight = {
  region: 'sliding_window_marsh', name: 'The Fenlight', family: 'POISON',
  gait: 'stalk', idle: 'twitch',
  body: 'cloth', accent: 'venom', hard: 'bone', core: 'venom',
  frames: 4, period: 1100, bob: 1, sway: 0, phase: 0.70,
  rows: [
    '........ooooooooooooooooo.......',
    '.......oaaaaaaaaaaaaaaaao.......',
    '.......ogooooooooooooooogo......',
    '.......ogo.............ogo......',
    '.......ogo.............ogo......',
    '.......ogo....ooo......ogo......',
    '.......ogo...oBBBo.....ogo......',
    '.......ogo...oBwBo.....ogo......',
    '.oo....ogo...oBeBogggggogo......',
    'oaBo...ogo...oBBBoggggggogo.....',
    '.oBo...ogo....oBBo.....ogo......',
    '.oBo...ogo....oBBo.....ogo......',
    '.oBo...ogo...ooBBoo....ogo......',
    '.oBo...ogo..oaBBBBao...ogo......',
    '.oBo...ogo.oaBBccBBao..ogo......',
    '.oBo...ogo.oBBcCCcBBo..ogo......',
    '.oBo...o.o.oaBBccBBao..ogo......',
    '.oBo.......oaBBBBBBao..ogo......',
    '.oBo........ooBBBBoo...ogo......',
    '.oBoo........oBooBo....ogo......',
    '.oBBo........oBo.oBo...ogo......',
    '..oBo........oBo.oBo...ogo......',
    '..oBo.......oBo..oBo...ogo......',
    '..oBo.......oBo..oBo...ogo......',
    '..oBo......oBo....oBo..ogo......',
    '..oBo......oBo....oBo..ogo......',
    '..oBo.....oBo.....oBo..ogo......',
    '..oBo.....oBo.....oBo..ogo......',
    '..oBo....oggo.....oggo.ogo......',
    '..ooo....oooo.....oooo.ooo......',
  ],
  head: [5, 10], headX: [11, 20], spine: [11, 19],
  legs: [[12, 16], [17, 21]], legTop: 19,
  arms: [[0, 5, 8, 29], [22, 27, 0, 29]], tail: null, tailX: null, fray: null,
};

/* Twin Pointer Pass. Two lantern-bearers of blue ice, mirrored, walking the
 * bridge from both ends at once — and the shape you have to read is the GAP
 * between them, which is the region's own lesson drawn as a monster. The
 * lumbering gait moves one body and then the other, so the gap opens and
 * closes on a four-frame cycle and never quite shuts. */
A.rimewarden = {
  region: 'twin_pointer_pass', name: 'The Rimewarden', family: 'COLD',
  gait: 'lumber', idle: 'breathe',
  body: 'frost', accent: 'cyan', hard: 'chrome', core: 'cyan',
  frames: 4, period: 1000, bob: 1, sway: 0, phase: 0.10,
  rows: [
    '....oooo.................oooo...',
    '...oggggo...............oggggo..',
    '...ogaago...............ogaago..',
    '...oggggo...............oggggo..',
    '....oBBo.................oBBo...',
    '...oBwBBo...............oBBwBo..',
    '...oBeBBo...............oBBeBo..',
    '...oBBBBo...............oBBBBo..',
    '..ooBBBBoo.............ooBBBBoo.',
    '.oaBBBBBBao...........oaBBBBBBao',
    'oaBBBBBBBBao.........oaBBBBBBBBa',
    'oBBBBccBBBBo.........oBBBBccBBBB',
    'oBBBcCCcBBBo.........oBBBcCCcBBB',
    'oBBBBccBBBBo.........oBBBBccBBBB',
    'oaBBBBBBBBao.........oaBBBBBBBBa',
    '.oBBBBBBBBo...........oBBBBBBBBo',
    '.oBBBBBBBBo...........oBBBBBBBBo',
    '.oaBBBBBBao...........oaBBBBBBao',
    '..oBBBBBBo.............oBBBBBBo.',
    '..oBBBBBBo.............oBBBBBBo.',
    '..oBBBBBBo.............oBBBBBBo.',
    '..oBBBBBBo.............oBBBBBBo.',
    '..oBBoBBBo.............oBBBoBBo.',
    '..oBo.oBBo.............oBBo.oBo.',
    '..oBo.oBBo.............oBBo.oBo.',
    '..oBo.oBBo.............oBBo.oBo.',
    '.oggo.oggo.............oggo.oggo',
    '.oooo.oooo.............oooo.oooo',
  ],
  head: [0, 8], headX: [0, 31], spine: [9, 22],
  legs: [[2, 9], [22, 29]], legTop: 22,
  arms: null, tail: null, tailX: null, fray: null,
};

/* Dynamic Programming Ruins. A lamp-lighter on stilts, walking backwards, with
 * a snuffer on the end of the pole instead of a wick. Its coat is prised-up
 * floor tiles that are still lit, hung in overlapping rows — every tile in that
 * hem is a problem somebody already solved, being carried away. The cutout is a
 * tall thin cross on two poles dragging a hem of squares. */
A.relighter = {
  region: 'dp_ruins', name: 'The Relighter', family: 'NEUTRAL',
  gait: 'stalk', idle: 'pulse',
  body: 'stone', accent: 'gold', hard: 'goldleaf', core: 'gold',
  frames: 4, period: 1200, bob: 1, sway: 0, phase: 0.45,
  rows: [
    '.....................o..........',
    '....................ogo.........',
    '...................ogggo........',
    '..................oggcggo.......',
    '..................oggcggo.......',
    '...................ogggo........',
    '....................ogo.........',
    '.........oooo.......ogo.........',
    '........oBBBBo.....ogo..........',
    '........oBwBwo.....ogo..........',
    '........oBeBeo....ogo...........',
    '........oBBBBo....ogo...........',
    'ooooooooooBBoooooogo............',
    'oaaaaaaaaoBBBoaaaogo............',
    'ooooooooooBBBoooogo.............',
    '.........oBBBBBo.ogo............',
    '........oaBBBBBao.o.............',
    '.......oAoAoAoAoAo..............',
    '.......oAoAoAoAoAo..............',
    '.......oAoAoAoAoAo..............',
    '......oAoAoAoAoAoAo.............',
    '......oAoAoAoAoAoAo.............',
    '......oooooooooooooo............',
    '.......oBo......oBo.............',
    '.......oBo......oBo.............',
    '.......oBo......oBo.............',
    '.......oBo......oBo.............',
    '.......oBo......oBo.............',
    '......oggo......oggo............',
    '......oooo......oooo............',
  ],
  head: [7, 12], headX: [7, 14], spine: [12, 22],
  legs: [[6, 10], [14, 19]], legTop: 23,
  arms: [[16, 23, 0, 17]], tail: null, tailX: null, fray: null,
};

/* Complexity Tower. A thin cold figure on the stair, and behind it another
 * exactly twice its size, cropped by the frame — and behind that another, which
 * is why the crop runs off three edges at once. Only the front one walks: the
 * `loom` gait moves the small figure and leaves the mass behind it absolutely
 * still, because a horror that bobs is a costume. Every floor of this tower
 * costs twice the one below, and this is that sentence as a silhouette. */
A.the_doubling = {
  region: 'complexity_tower', name: 'The Doubling', family: 'COLD',
  gait: 'loom', idle: 'drift',
  body: 'cyan', accent: 'frost', hard: 'chrome', core: 'cyan',
  frames: 4, period: 1500, bob: 1, sway: 0, phase: 0.30,
  rows: [
    '....................oooooooo....',
    '.................ooaaaaaaaaaao..',
    '...............ooaaaaaaaaaaaaao.',
    '..............oaaaaaaaaaaaaaaaao',
    '.............oaaaaaaaaaaaaaaaaaa',
    '.............oaaaaaaaaaaaaaaaaaa',
    '.............oaaaaaaaaaaaaaaaaaa',
    '.............oaaaaaaaaaaaaaaaaaa',
    '..............oaaaaaaaaaaaaaaaaa',
    '...............oaaaaaaaaaaaaaaaa',
    '................ooaaaaaaaaaaaaaa',
    '..ooooo............oaaaaaaaaaaaa',
    '..oBBBo...........oaaaaaaaaaaaaa',
    '..oBwBo..........oaaaaaaaaaaaaaa',
    '..oBeBo.........oaaaaaaaaaaaaaaa',
    '..oBBBo........oaaaaaaaaaaaaaaaa',
    '.ooBBBoo......oaaaaaaaaaaaaaaaaa',
    'oaBBBBBao....oaaaaaaaaaaaaaaaaaa',
    'oBBBccBBo....oaaaaaaaaaaaaaaaaaa',
    'oBBcCCcBo....oaaaaaaaaaaaaaaaaaa',
    'oBBBccBBo....oaaaaaaaaaaaaaaaaaa',
    'oaBBBBBao....oaaaaaaaaaaaaaaaaaa',
    '.oBBBBBoo....oaaaaaaaaaaaaaaaaaa',
    '.oBBBBBo.....oaaaaaaaaaaaaaaaaaa',
    '.oBBBBBo.....oaaaaaaaaaaaaaaaaaa',
    '.oBBoBBo.....oaaaaaaaaaaaaaaaaaa',
    '.oBo.oBo.....oaaaaaaaaaaaaaaaaaa',
    '.oBo.oBo.....oaaaaaaaaaaaaaaaaaa',
    '.oBo.oBo.....oaaaaaaaaaaaaaaaaaa',
    'oggo.oggo....oaaaaaaaaaaaaaaaaaa',
    'oooo.oooo....oaaaaaaaaaaaaaaaaaa',
  ],
  head: [11, 17], headX: [1, 8], spine: [16, 28],
  legs: [[1, 4], [5, 8]], legTop: 25,
  front: [0, 8, 11, 30], arms: null, tail: null, tailX: null, fray: null,
};

/* The Null King's Castle. A tall absence in the shape of a knight, carrying
 * nothing and wearing nothing. The part of the shape that would say what it is
 * has been removed, and the removal is REAL: the notch through the chest is
 * transparency, not a dark colour, so the ground behind it is visible through
 * the hole. It is the last thing in the bestiary and the only creature drawn by
 * what is missing from it. */
A.the_unnamed = {
  region: 'null_kings_castle', name: 'The Unnamed', family: 'VOID',
  gait: 'hover', idle: 'drift',
  body: 'void', accent: 'violet', hard: 'bone', core: 'violet',
  frames: 3, period: 1800, bob: 2, sway: 1, phase: 0.60,
  oy: 0,
  rows: [
    '............oooooo..............',
    '..........ookkkkkkoo............',
    '.........okkkkkkkkkko...........',
    '.........okkkccckkkko...........',
    '.........okkcwwwckkko...........',
    '.........okkkccckkkko...........',
    '.........okkkkkkkkkko...........',
    '..........okkkkkkkko............',
    '..........ookkkkkkoo............',
    '.......ooooooBBBBoooooo.........',
    '.....ooBBBBBoBBBBoBBBBBoo.......',
    '...ooBBBBBBBoBBBBoBBBBBBBoo.....',
    '..oBBBBBBBBBoBBBBoBBBBBBBBBo....',
    '.oBBBBBBBBBBBBBBBBBBBBBBBBBBo...',
    '.oBBBBBoooooooooooooooooBBBBo...',
    'oBBBBBo................oBBBBBo..',
    'oBBBBo..................oBBBBo..',
    'oBBBBo..................oBBBBo..',
    'oBBBBo..................oBBBBo..',
    'oBBBBoooooooooooooooooooooBBBo..',
    'oBBBBBBBBBBBBBBBBBBBBBBBBBBBBo..',
    '.oBBBBBBBBBBBBBBBBBBBBBBBBBBo...',
    '.oBBBBBBBBBBBBBBBBBBBBBBBBBo....',
    '..oBBBBBBBBBBBBBBBBBBBBBBBo.....',
    '..oBBBBBBBBBBBBBBBBBBBBBBo......',
    '...oBBBBBBBBBBBBBBBBBBBBo.......',
    '...oBBBBBBBBBBBBBBBBBBBo........',
    '....oBBBoBBBoBBBoBBBoBBo........',
    '.....o..o.o..o.o..o.o..o........',
    '.....................o..........',
  ],
  head: [0, 9], headX: [8, 22], spine: [9, 27],
  legs: [], legTop: 32, fray: [26, 29], arms: null, tail: null, tailX: null,
};

/* The apex fallback. The same unmarked body as `strayling`, in the apex box, so
 * a hunter whose region nobody recognises still occupies thirty-two pixels and
 * the caller's layout does not move. It is not a creature and does not pretend
 * to be one: no markings, no species, and monsterIsAuthored() reports it as a
 * fall-through so a harness can see it. */
A.strayapex = {
  region: '', name: 'Something Out There', family: 'NEUTRAL', fallback: true,
  gait: 'lumber', idle: 'breathe',
  body: 'cloth', accent: 'cloth', hard: 'bone', core: null,
  frames: 4, period: 900, bob: 1, sway: 0, phase: 0.00,
  oy: 6,
  rows: [
    '.........ooooooooooo............',
    '.......ooBBBBBBBBBBBoo..........',
    '......oBBBBBBBBBBBBBBBo.........',
    '.....oBBBBBBBBBBBBBBBBBo........',
    '.....oBBwBBBBBBBBBBBwBBo........',
    '.....oBBeBBBBBBBBBBBeBBo........',
    '.....oBBBBBBBBBBBBBBBBBo........',
    '.....oBBBBBBBBBBBBBBBBBo........',
    '......oBBBBBBBBBBBBBBBo.........',
    '......oBBBBBBBBBBBBBBBo.........',
    '......oBBBoBBBBBBBoBBBo.........',
    '......oBBo.oBBBBBo.oBBo.........',
    '......oBBo.oBBBBBo.oBBo.........',
    '......oBBo.oBBBBBo.oBBo.........',
    '......oBBo.oBBBBBo.oBBo.........',
    '......oggo.ogggggo.oggo.........',
    '......oooo.ooooooo.oooo.........',
  ],
  head: [0, 9], headX: [5, 22], spine: [1, 10],
  legs: [[6, 9], [11, 17], [19, 22]], legTop: 10,
  tail: null, tailX: null, fray: null, arms: null,
};

/* ================================================================
 * THE TABLE
 * ================================================================ */

/* Every band above was authored against the creature's OWN row list, because
 * that is the list an author is looking at while drawing it. The rows are then
 * placed in the box at `oy`, so every row coordinate has to move with them —
 * once, here, rather than at every call site that reads one.
 *
 * This was a real bug and not a hypothetical: before this pass the cinderhound's
 * breathing idle was lifting rows 2 to 6 of a box whose animal started at row 8,
 * which moved nothing at all and produced a monster that stood perfectly still
 * while the player read a problem statement. The harness caught it by measuring
 * cells changed per idle cycle, which is why that number is measured. */
function place(spec, size) {
  const oy = spec.oy == null ? size - spec.rows.length : spec.oy;
  spec.oy = oy;
  if (!oy) return;
  const band = (b) => (b ? [b[0] + oy, b[1] + oy] : b);
  spec.head = band(spec.head);
  spec.spine = band(spec.spine);
  spec.tail = band(spec.tail);
  spec.jaw = band(spec.jaw);
  spec.fray = band(spec.fray);
  if (spec.legTop != null && spec.legTop < size) spec.legTop += oy;
  for (const field of ['wing', 'arms', 'orbit']) {
    if (!spec[field]) continue;
    spec[field] = spec[field].map(([x0, x1, y0, y1]) => [x0, x1, y0 + oy, y1 + oy]);
  }
}

for (const key of Object.keys(M)) {
  M[key].key = key; M[key].size = MON_SIZE; M[key].apex = false;
  place(M[key], MON_SIZE);
}
for (const key of Object.keys(A)) {
  A[key].key = key; A[key].size = APEX_SIZE; A[key].apex = true;
  place(A[key], APEX_SIZE);
}

/** Every creature, mob and apex, keyed by its own name. */
export const MONSTERS = Object.assign({}, M, A);
export const MOB_KEYS = Object.keys(M).filter(k => !M[k].fallback);
export const APEX_KEYS = Object.keys(A)
  .filter(k => !A[k].fallback && !A[k].unassigned && A[k].region);

/* Authored, good, and not currently the hunter of anywhere. Kept rather than
 * deleted: gauntlet/hunters.py reassigns its seventeen freely and a later pass
 * that wants a second apex tier, a dungeon set piece or a region nobody has
 * written yet gets these for nothing. They are excluded from APEX_KEYS so the
 * count still equals the number of regions. */
export const APEX_UNASSIGNED = Object.keys(A).filter(k => A[k].unassigned);
export const MONSTER_KEYS = Object.keys(MONSTERS);

/* The shape class of each creature, which is what an alias resolves TO.
 *
 * The bestiary's twenty-eight sprite keys are region-agnostic — `wisp` appears
 * in five chapters — so mapping them one-to-one onto creatures would put the
 * same animal in every region and rebuild the exact problem this file exists to
 * fix. They map onto a ROLE instead, and the role is filled by whatever that
 * REGION's roster keeps in that slot. A `wisp` in the Tower is a frostcairn, a
 * `wisp` in the Castle is a shade, and a screenshot still tells you where you
 * are. That is a decision, recorded here, not a fallback. */
export const MONSTER_ROLES = {
  emberwing: 'flyer', cinderhound: 'runner', slagworm: 'legless', ashmoth: 'flyer',
  rimewolf: 'runner', snowshrike: 'flyer', frostcairn: 'bodiless', icemantis: 'creeper',
  webstalker: 'creeper', lashvine: 'legless', spinetoad: 'runner', stiltheron: 'creeper',
  gravelape: 'heavy', drillgrub: 'legless', chiselmite: 'creeper', plinthguard: 'heavy',
  stormram: 'runner', arcshrike: 'flyer', coilworm: 'legless', rodwalker: 'heavy',
  bonepike: 'heavy', gravehound: 'runner', shade: 'bodiless', skullswarm: 'bodiless',
  tuftling: 'runner', fieldadder: 'legless', leafmonkey: 'creeper', dartwren: 'flyer',
  gildscarab: 'creeper', tilewight: 'heavy', sandjackal: 'runner', sanddervish: 'bodiless',
  strayling: 'runner', straywisp: 'bodiless',
};

export const MONSTER_ROLE_KINDS = ['flyer', 'runner', 'creeper', 'legless',
                                   'heavy', 'bodiless'];

/* ---------------------------------------------------------------- regions
 *
 * MIRRORS of world.py REGIONS and elements.py BIOME_AFFINITY. They are copied
 * rather than imported because this is a browser module and Python is not
 * available to it, which makes them exactly the kind of duplicate that goes
 * stale — so scripts/verify/monsters.mjs reads both tables out of Python and
 * fails if either of these has drifted by one row. A mirror nobody checks is a
 * bug with a delay on it.
 */
export const REGION_BIOME = {
  python_village: 'village', fields_of_syntax: 'grass',
  hashmap_highlands: 'highland', stringwood_labyrinth: 'forest',
  array_caverns: 'cave', sliding_window_marsh: 'swamp',
  twin_pointer_pass: 'mountain', stack_queue_mines: 'mine',
  matrix_citadel: 'citadel', recursive_forest: 'deepforest',
  binary_tree_canopy: 'canopy', graph_wastes: 'wastes', dp_ruins: 'ruins',
  debugging_dungeon: 'dungeon', complexity_tower: 'tower',
  coding_coliseum: 'arena', null_kings_castle: 'castle',
};

export const BIOME_ELEMENT = {
  highland: 'LIGHTNING', forest: 'POISON', cave: 'BRUTE', swamp: 'POISON',
  mountain: 'COLD', mine: 'FIRE', citadel: 'BRUTE', deepforest: 'VOID',
  wastes: 'LIGHTNING', dungeon: 'FIRE', tower: 'COLD', castle: 'VOID',
  village: 'NEUTRAL', grass: 'NEUTRAL', canopy: 'NEUTRAL', ruins: 'NEUTRAL',
  arena: 'NEUTRAL',
};

/* What lives where.
 *
 * Three per elemental biome and two per neutral one, and the two biomes that
 * share an element do not share the same three: the Mines keep the hound and
 * the grub, the forge keeps the moth, and the bird walks both. That is the
 * honest amount of separation four creatures can buy two regions. The apexes
 * carry the rest of it — no two regions have the same one, and no apex looks
 * like anything else in its own region.
 */
export const BIOME_ROSTER = {
  village:    ['tuftling', 'fieldadder'],
  grass:      ['tuftling', 'fieldadder'],
  canopy:     ['leafmonkey', 'dartwren'],
  ruins:      ['gildscarab', 'tilewight'],
  arena:      ['sandjackal', 'sanddervish'],
  mine:       ['cinderhound', 'slagworm', 'emberwing'],
  dungeon:    ['ashmoth', 'emberwing', 'slagworm'],
  mountain:   ['rimewolf', 'snowshrike', 'frostcairn'],
  tower:      ['icemantis', 'frostcairn', 'snowshrike'],
  forest:     ['webstalker', 'lashvine', 'spinetoad'],
  swamp:      ['stiltheron', 'spinetoad', 'lashvine'],
  cave:       ['gravelape', 'drillgrub', 'chiselmite'],
  citadel:    ['plinthguard', 'chiselmite', 'gravelape'],
  highland:   ['stormram', 'arcshrike', 'coilworm'],
  wastes:     ['rodwalker', 'coilworm', 'arcshrike'],
  deepforest: ['gravehound', 'shade', 'bonepike'],
  castle:     ['bonepike', 'skullswarm', 'shade'],
};

/** The region's apex, by region id. */
export const REGION_APEX = {};
for (const key of APEX_KEYS) REGION_APEX[A[key].region] = key;

/** The apexes' display names, for a UI that wants to print one before
 *  gauntlet/hunters.py has opinions of its own. hunters.py wins wherever it
 *  ships a name; these exist so nothing is nameless in the meantime. */
export const APEX_NAMES = {};
for (const key of APEX_KEYS) APEX_NAMES[key] = A[key].name;

/** Who belongs to which element, mobs and apexes together. For a bestiary
 *  screen that wants to show a family, and for anything checking that an
 *  element has more than one creature in it. */
export const ELEMENT_FAMILIES = {};
for (const key of MONSTER_KEYS) {
  const fam = MONSTERS[key].family || 'NEUTRAL';
  (ELEMENT_FAMILIES[fam] ||= []).push(key);
}

/** Anything a caller might hand over as a region: an id, a biome, or a row. */
/* OWN PROPERTIES ONLY.
 *
 * Every table in this file is a plain object literal, so it inherits from
 * Object.prototype, so `TABLE['constructor']` is a function rather than a miss.
 * `strip()` lowercases and removes separators and therefore cannot disarm a key
 * that is already lowercase and unseparated — and `constructor` is exactly
 * that. Measured before this existed: `monsterKeyFor('constructor')` returned
 * `function Object() { [native code] }` and `monsterIsAuthored('constructor')`
 * returned true, so a name arriving from a save file, a quest row or a URL
 * could hand a caller a FUNCTION where this module's own docstring promises
 * "never returns something that is not in MONSTERS". Nothing threw, which is
 * the worst version: the fallback that exists so unknown keys are harmless
 * simply did not run.
 *
 * One guard, used at every point an outside string chooses a row. */
const own = (table, key) =>
  (typeof key === 'string'
   && Object.prototype.hasOwnProperty.call(table, key)) ? table[key] : undefined;

export function biomeOf(region) {
  const raw = (region && typeof region === 'object')
    ? (region.biome || region.region || region.id || '') : region;
  const k = String(raw == null ? '' : raw).toLowerCase().trim();
  const biome = own(REGION_BIOME, k);
  if (biome) return biome;
  if (own(BIOME_ROSTER, k)) return k;
  return '';
}

/** The element of a place. Unknown places are NEUTRAL, never an exception —
 *  the same contract elements.py affinity_for() honours. */
export function elementOf(region) {
  return own(BIOME_ELEMENT, biomeOf(region)) || 'NEUTRAL';
}

/** What lives in a region, in roster order. Always at least two names. */
export function rosterFor(region) {
  return own(BIOME_ROSTER, biomeOf(region)) || BIOME_ROSTER.grass;
}

/* --------------------------------------------------------------- aliases
 *
 * Every sprite key gauntlet/bestiary.py ships, placed deliberately. A key with
 * an entry here is somebody's decision about what shape that monster is; a key
 * without one falls through to an unmarked body, and monsterIsAuthored() tells
 * a harness which happened. The bestiary is rewritten often, so this list is
 * expected to grow — and to fail loudly in scripts/verify/monsters.mjs the day
 * it does not.
 */
export const MONSTER_ALIAS = {
  // bestiary.py ENEMY sprite keys, as of 71 enemies over 28 keys
  slime: 'bodiless', marshling: 'bodiless', wisp: 'bodiless',
  echoling: 'bodiless', lightwave: 'bodiless', linewraith: 'bodiless',
  riddler: 'bodiless', mirrorspawn: 'bodiless',
  hoarder: 'heavy', construct: 'heavy', clockwork: 'heavy', mimic: 'heavy',
  twinblade: 'heavy', pilekeeper: 'heavy', vaultling: 'heavy', vault: 'heavy',
  halfling: 'runner', cartgoblin: 'runner', sentinel: 'runner',
  deepcrawler: 'creeper', bugling: 'creeper', beetle: 'creeper',
  gridling: 'creeper', lattice: 'creeper', ledgerling: 'creeper',
  ledger: 'creeper', orderling: 'creeper', indexling: 'creeper',
  sorter: 'creeper', keeper: 'heavy',
  branchling: 'legless', wyrmling: 'legless', overlapper: 'legless',
  drake: 'flyer', runeling: 'flyer', imp: 'flyer', wave: 'bodiless',
  serpent: 'legless', crawler: 'creeper', golem: 'heavy', wraith: 'bodiless',
  hydra: 'legless', warden: 'heavy',
};

/* Names that mean a creature we have drawn. Not roles — these are the direct
 * spellings a quest or a designer is likely to type, and they all name MOBS.
 *
 * The rule an apex is held to outside apex mode: it comes back only when the
 * caller named it exactly, by its own key or by its full display name. A
 * nickname is not exact enough, because the callers most likely to use one are
 * asking for an ordinary monster and expecting an ordinary monster's box. */
export const MONSTER_NAME_ALIAS = {
  skeleton: 'bonepike', skeletonwarrior: 'bonepike', bones: 'bonepike',
  skeletondog: 'gravehound', bonehound: 'gravehound',
  ghost: 'shade', wight: 'shade', spectre: 'shade', specter: 'shade',
  iceelemental: 'frostcairn', fireelemental: 'slagworm',
  shadowelemental: 'shade',
  spider: 'webstalker', wolf: 'rimewolf', ram: 'stormram',
  heron: 'stiltheron', moth: 'ashmoth', toad: 'spinetoad', frog: 'spinetoad',
  beetlekin: 'gildscarab', scarab: 'gildscarab', ape: 'gravelape',
  statue: 'plinthguard', mantis: 'icemantis', jackal: 'sandjackal',
  monkey: 'leafmonkey', wren: 'dartwren', rabbit: 'tuftling',
  adder: 'fieldadder', snake: 'fieldadder', worm: 'slagworm',
};

/* The same thing for APEX rank, kept separate on purpose.
 *
 * A caller asking for "a bat" wants an ordinary monster and must get a 24px
 * body; only a caller who has said `apex: true` should ever be handed a 32px
 * one by a generic word. Mixing the two tables put an apex-class body in front
 * of scripts/verify/bossseam.mjs when it asked for four ordinary mobs, and it
 * measured its bosses against the wrong reference as a result. */
export const APEX_NAME_ALIAS = {
  phoenix: 'cinder_phoenix', firebird: 'cinder_phoenix',
  gladiator: 'sand_champion', champion: 'sand_champion',
  surveyor: 'margin_walker', scarecrow: 'margin_walker',
  harvester: 'thresher', reaper: 'thresher',
  lamplighter: 'relighter', knight: 'fourth_orientation',
  owl: 'sporecrown', stag: 'lattice_stag', deer: 'lattice_stag',
  bat: 'vaultbat', crocodile: 'mirelord', croc: 'mirelord',
  icegolem: 'hoarcolossus', icecolossus: 'hoarcolossus',
  bull: 'thunderhorn', sphinx: 'memoriam', seaserpent: 'spirewyrm',
  skeletonking: 'bonecrown', lichking: 'bonecrown',
};

export const MONSTER_FALLBACK = 'strayling';
export const APEX_FALLBACK = 'strayapex';
export const MONSTER_FALLBACK_BODILESS = 'straywisp';

/* The bodiless regions. A key that falls off the end of every table in a region
 * whose creatures mostly do not touch the floor gets the legless unmarked body
 * rather than the four-legged one, because a strayling standing in the middle
 * of the Castle is a worse lie than a straywisp is. */
const BODILESS_BIOMES = new Set(['castle', 'deepforest', 'tower']);

/* One lookup for every spelling of every creature. gauntlet/hunters.py ships
 * `margin_walker`; a quest might say "Margin-Walker"; a designer types "the
 * margin walker". All three are the same animal and none of them should have to
 * know how this table spells it, so separators are stripped and a leading "the"
 * is dropped before anything is looked up. */
const strip = (v) => String(v == null ? '' : v).toLowerCase().trim()
  .replace(/^the[\s_-]+/, '').replace(/[\s_'-]+/g, '');

const INDEX = {};
for (const key of MONSTER_KEYS) {
  INDEX[strip(key)] = key;
  const name = MONSTERS[key].name;
  if (name) INDEX[strip(name)] = key;
}

/** Resolve anything to a drawable key, and say HOW it resolved.
 *
 *  @returns { key, via } where via is one of
 *    'authored'  the name is a creature in this file
 *    'name'      a deliberate spelling alias
 *    'apex'      a region id or hunter row that named an apex
 *    'role'      a bestiary sprite key, filled from the region's roster
 *    'fallback'  nobody has drawn this; an unmarked body, in region colours
 */
export function resolveMonster(name, opts) {
  const o = opts || {};
  const raw = (name && typeof name === 'object')
    ? (name.sprite || name.monster || name.key || name.id || name.name || '')
    : name;
  const k = strip(raw);
  const biome = biomeOf(o.region || (name && typeof name === 'object' ? name.region : ''));
  const hit = own(INDEX, k);

  if (o.apex) {
    if (hit && own(MONSTERS, hit).apex) return { key: hit, via: 'authored' };
    const named = own(APEX_NAME_ALIAS, k) || own(MONSTER_NAME_ALIAS, k);
    if (named && own(A, named)) return { key: named, via: 'name' };
    const byRegion = own(REGION_APEX, String(o.region || '').toLowerCase().trim())
                  || own(REGION_APEX, String(raw || '').toLowerCase().trim());
    if (byRegion) return { key: byRegion, via: 'apex' };
    // An apex with a region nobody recognises. Unmarked body in the apex box, so
    // the caller's layout holds and nothing claims to be a creature it is not.
    return { key: APEX_FALLBACK, via: 'fallback' };
  }

  if (hit) return { key: hit, via: 'authored' };
  const named = own(MONSTER_NAME_ALIAS, k);
  const namedRow = named ? own(MONSTERS, named) : undefined;
  if (namedRow && !namedRow.apex) return { key: named, via: 'name' };

  const role = own(MONSTER_ALIAS, k);
  if (role) {
    const roster = rosterFor(biome || o.region);
    for (const c of roster) if (own(MONSTER_ROLES, c) === role) return { key: c, via: 'role' };
    // The region has nothing in that slot — a bodiless key in the Ruins, say.
    // Take the roster's first, which is still one of that region's OWN animals
    // and therefore still true about where the player is standing.
    return { key: roster[0], via: 'role' };
  }

  return { key: BODILESS_BIOMES.has(biome) ? MONSTER_FALLBACK_BODILESS
                                           : MONSTER_FALLBACK, via: 'fallback' };
}

/** Just the key. Never throws, never returns something that is not in MONSTERS. */
export function monsterKeyFor(name, opts) { return resolveMonster(name, opts).key; }

/** Whether a name was drawn on purpose or fell off the end of every table.
 *  scripts/verify/monsters.mjs fails on the second, which is the whole point of
 *  separating them. */
export function monsterIsAuthored(name, opts) {
  return resolveMonster(name, opts).via !== 'fallback';
}

/** The apex that hunts a region. Accepts a region id, a biome, an apex key, an
 *  apex display name, or a hunters.py row carrying any of those. */
export function apexKeyFor(region, opts) {
  const o = Object.assign({}, opts, { apex: true });
  if (!o.region && typeof region === 'string') o.region = region;
  if (region && typeof region === 'object' && region.region) o.region = region.region;
  return resolveMonster(region, o).key;
}

/** Deterministic roster pick. Same region and same seed, same creature, every
 *  run — a spawn table can call this from a draw path without reaching for
 *  Math.random, which is not allowed here. */
export function pickFor(region, seed) {
  const roster = rosterFor(region);
  const n = hash(`${biomeOf(region) || 'grass'}:${seed == null ? 0 : seed}`);
  return roster[n % roster.length];
}

/* ------------------------------------------------------------- grid surgery
 *
 * The ops a gait is written in. They take and return arrays of strings of
 * exactly `w` characters, they never mutate their input, and none of them
 * allocates anything that outlives the frame it is building.
 */

const EMPTY_CH = (ch) => ch === '.' || ch === ' ' || ch === undefined;

function rowsOf(grid, w) { return normalise(grid, w); }

/* Move a rectangle of the grid. A leg lifted out of its own column range is one
 * call to this and nothing else, which is what lets one gait function drive a
 * stag and a crocodile without either of them borrowing the other's walk. */
function moveBlock(grid, x0, x1, y0, y1, dx, dy, w) {
  if (!dx && !dy) return grid;
  const g = rowsOf(grid, w).map(r => r.split(''));
  const h = g.length;
  const taken = [];
  for (let y = Math.max(0, y0); y <= Math.min(h - 1, y1); y++) {
    for (let x = Math.max(0, x0); x <= Math.min(w - 1, x1); x++) {
      const ch = g[y][x];
      if (EMPTY_CH(ch)) continue;
      taken.push([y, x, ch]);
      g[y][x] = '.';
    }
  }
  for (const [y, x, ch] of taken) {
    const ty = y + dy, tx = x + dx;
    if (ty < 0 || ty >= h || tx < 0 || tx >= w) continue;
    g[ty][tx] = ch;
  }
  return g.map(r => r.join(''));
}

/* A whole band, full width. The body rising off the legs on a pass frame. */
function bobBand(grid, y0, y1, dy, w) {
  return moveBlock(grid, 0, w - 1, y0, y1, 0, dy, w);
}

function shiftBand(grid, y0, y1, dx, w) {
  return moveBlock(grid, 0, w - 1, y0, y1, dx, 0, w);
}

/* An integer wave, so an undulation is exact rather than a rounded sine. Six
 * steps: two up, two down, one flat at each end — enough shape to read as a
 * travelling wave and short enough that a four-frame cycle visits all of it. */
const WAVE = [0, 1, 1, 0, -1, -1];

function waveBand(grid, y0, y1, phase, w, amp = 1) {
  let g = rowsOf(grid, w);
  const out = [];
  for (let y = 0; y < g.length; y++) {
    if (y < y0 || y > y1) { out.push(g[y]); continue; }
    const dx = WAVE[(((y + phase) % WAVE.length) + WAVE.length) % WAVE.length] * amp;
    if (!dx) { out.push(g[y]); continue; }
    const row = new Array(w).fill('.');
    for (let x = 0; x < w; x++) {
      const ch = g[y][x];
      if (EMPTY_CH(ch)) continue;
      const tx = x + dx;
      if (tx >= 0 && tx < w) row[tx] = ch;
    }
    out.push(row.join(''));
  }
  return out;
}

/* Swap the two accent tones. Used by anything whose tell is a glow rather than
 * a movement — a core beating, an arc jumping, a rune brightening. Never the
 * ONLY thing a frame does: a six-unit brightness change is not a frame. */
function swapAccent(grid) {
  return grid.map(row => row.replace(/[aA]/g, ch => (ch === 'a' ? 'A' : 'a')));
}

/* Erase part of the bottom edge, deterministically, by a hash of the cell's own
 * coordinates and the frame. This is how a thing with no legs ends: not on a
 * row, but in a different handful of cells every frame. */
function frayEdge(grid, band, seed, w) {
  if (!band) return grid;
  const g = rowsOf(grid, w).map(r => r.split(''));
  const h = g.length;
  for (let y = Math.max(0, band[0]); y <= Math.min(h - 1, band[1]); y++) {
    for (let x = 0; x < w; x++) {
      if (EMPTY_CH(g[y][x])) continue;
      const below = y + 1 < h ? g[y + 1][x] : '.';
      if (!EMPTY_CH(below)) continue;              // only the edge itself
      if (hash(`${seed}:${x}:${y}`) % 3 === 0) g[y][x] = '.';
    }
  }
  return g.map(r => r.join(''));
}

/* One extra cell of outline in every direction. This is the loudest legibility
 * cue available at 24px and it costs one pass, so it is what separates an apex
 * from a mob before any colour is looked at. It runs BEFORE the lighting, so
 * the thickened edge is lit as one outline rather than as two. */
function thicken(grid, w) {
  const src = rowsOf(grid, w);
  const h = src.length;
  const out = src.map(r => r.split(''));
  const at = (y, x) => (y < 0 || y >= h || x < 0 || x >= w) ? '.' : src[y][x];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!EMPTY_CH(src[y][x])) continue;
      if (at(y - 1, x) === 'o' || at(y + 1, x) === 'o'
       || at(y, x - 1) === 'o' || at(y, x + 1) === 'o') out[y][x] = 'o';
    }
  }
  return out.map(r => r.join(''));
}

/* A sparse ring outside the outline. Sparse because a solid ring is a halo and
 * a halo is a blob: every third candidate cell by a hash of its own coordinates,
 * so it is stable frame to frame and identical on two runs. */
function aura(grid, seed, density, w) {
  const src = rowsOf(grid, w);
  const h = src.length;
  const out = src.map(r => r.split(''));
  const at = (y, x) => (y < 0 || y >= h || x < 0 || x >= w) ? '.' : src[y][x];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!EMPTY_CH(src[y][x])) continue;
      let touch = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          if (!EMPTY_CH(at(y + dy, x + dx))) touch++;
        }
      }
      if (!touch) continue;
      if (hash(`${seed}:${x}:${y}`) % density === 0) out[y][x] = 'r';
    }
  }
  return out.map(r => r.join(''));
}

/* ------------------------------------------------------------------ gaits
 *
 * How a thing moves is most of what it is, so no two families share a walk.
 * Each of these is an authored deformation of the base grid: a leg out of its
 * own column range, a wing out of its own row range, a spine dipped. Frame 0 is
 * always the base grid untouched, so a caller that only ever asks for frame 0
 * gets the authored pose and nothing surprising.
 */

const GAITS = {};

/* Four legs, two beats. Diagonal pairs, and the body lifts on the pass. */
GAITS.fourbeat = (m, g, f, w) => {
  const L = m.legs || [];
  const h = m.size;
  if (f === 0) return g;
  const lift = (i, dy, dx) => {
    const leg = L[i];
    if (!leg) return;
    g = moveBlock(g, leg[0], leg[1], m.legTop, h - 1, dx || 0, -dy, w);
  };
  if (f === 2) return bobBand(g, 0, m.legTop - 1, -1, w);
  const pair = f === 1 ? [0, 2] : [1, 3];
  for (const i of pair) lift(i, 2, f === 1 ? 1 : -1);
  if (m.head) g = shiftBand(g, m.head[0], Math.min(m.head[1], m.legTop - 1),
                            f === 1 ? 1 : -1, w);
  return g;
};

/* The wrong walk. The lead leg lifts three rows and swings forward, the
 * trailing leg lifts one and does not, and the body drops onto whichever is
 * planted. A skeleton has nothing keeping it honest, so it limps on a schedule
 * — and that schedule is the same every cycle, which is what makes it read as
 * broken rather than as random. */
GAITS.skeletal = (m, g, f, w) => {
  const L = m.legs || [];
  const h = m.size;
  const lead = L[0], trail = L[L.length > 2 ? 2 : 1];
  if (f === 0) return g;
  if (f === 1) {
    if (lead) g = moveBlock(g, lead[0], lead[1], m.legTop, h - 1, 1, -3, w);
    g = bobBand(g, 0, m.legTop - 1, 1, w);
    if (m.jaw) g = moveBlock(g, m.jawX[0], m.jawX[1], m.jaw[0], m.jaw[1], 0, 1, w);
    return g;
  }
  if (f === 2) {
    g = bobBand(g, 0, m.legTop - 1, -1, w);
    if (m.head) g = shiftBand(g, m.head[0], Math.min(m.head[1], m.legTop - 1), 1, w);
    return g;
  }
  if (trail) g = moveBlock(g, trail[0], trail[1], m.legTop, h - 1, -1, -1, w);
  if (m.head) g = shiftBand(g, m.head[0], Math.min(m.head[1], m.legTop - 1), -1, w);
  return g;
};

/* A bird is never quite still. Wings up, wings down, and the body counter-
 * bobbing against them — the outer half of each wing travels one row further
 * than the inner half, which is the difference between a wing and a plank. */
GAITS.wingbeat = (m, g, f, w) => {
  if (f === 0) return g;
  const dir = f === 1 ? -1 : 1;
  for (const [x0, x1, y0, y1] of (m.wing || [])) {
    const midX = Math.round((x0 + x1) / 2);
    const outer = x0 < w / 2 ? [x0, midX] : [midX, x1];
    const inner = x0 < w / 2 ? [midX + 1, x1] : [x0, midX - 1];
    g = moveBlock(g, outer[0], outer[1], y0, y1, 0, dir * 3, w);
    g = moveBlock(g, inner[0], inner[1], y0, y1, 0, dir * 2, w);
  }
  g = bobBand(g, 0, m.size - 1, -dir, w);
  return g;
};

/* No legs to plant. The whole mass rises, the bottom edge frays to a different
 * set of cells, and the accent flips — and at no point in the cycle is there a
 * row you could call the one it is standing on. */
GAITS.hover = (m, g, f, w) => {
  const dy = [0, -2, -1][f % 3];
  let out = dy ? bobBand(g, 0, m.size - 1, dy, w) : g;
  out = frayEdge(out, m.fray, `${m.key}:${f}`, w);
  if (f === 1) out = swapAccent(out);
  if (m.orbit && f) {
    const spin = f === 1 ? 1 : -1;
    for (const [x0, x1, y0, y1] of m.orbit) {
      out = moveBlock(out, x0, x1, y0, y1, spin, 0, w);
    }
  }
  return out;
};

/* Many legs, low, fast. The legs are two clusters rather than four columns, so
 * the whole cluster shuffles and the body ticks against it. */
GAITS.scuttle = (m, g, f, w) => {
  if (f === 0) return g;
  const L = m.legs || [];
  const dx = (f === 1 || f === 2) ? 1 : -1;
  const h = m.size;
  if (L[0]) g = moveBlock(g, L[0][0], L[0][1], m.legTop, h - 1, dx, 0, w);
  if (L[1]) g = moveBlock(g, L[1][0], L[1][1], m.legTop, h - 1, -dx, 0, w);
  if (f === 2) g = bobBand(g, 0, m.legTop - 1, -1, w);
  return g;
};

/* A line, moving. No legs in the grid and none in the gait — the wave travels
 * up the body one row per frame, which is the only honest way to draw a thing
 * with no limbs going somewhere. */
GAITS.slither = (m, g, f, w) => {
  const s = m.spine || [0, m.size - 1];
  let out = waveBand(g, s[0], s[1], f, w);
  if (m.head && f % 2) {
    out = shiftBand(out, m.head[0], m.head[1], f === 1 ? 1 : -1, w);
  }
  return out;
};

/* Weight, shifted. A heavy thing does not lift a foot, it leans onto one and
 * lets the other come along — so the top sinks a row and the base slides. */
GAITS.lumber = (m, g, f, w) => {
  if (f === 0) return g;
  const h = m.size;
  const L = m.legs || [];
  const dir = f === 1 ? 1 : f === 3 ? -1 : 0;
  if (f === 2) return bobBand(g, 0, m.legTop - 1, -1, w);
  const leg = dir > 0 ? L[0] : L[L.length - 1];
  if (leg) g = moveBlock(g, leg[0], leg[1], m.legTop, h - 1, 0, -1, w);
  g = bobBand(g, 0, m.legTop - 1, 1, w);
  g = shiftBand(g, 0, Math.max(0, m.legTop - 4), dir, w);
  return g;
};

/* Too fast to see, so it is drawn as two positions and a blur of bob. */
GAITS.flit = (m, g, f, w) => {
  if (f === 0) return g;
  const dir = f === 1 ? -1 : 1;
  for (const [x0, x1, y0, y1] of (m.wing || [])) {
    g = moveBlock(g, x0, x1, y0, y1, 0, dir * 2, w);
  }
  return bobBand(g, 0, m.size - 1, dir, w);
};

/* Long legs, slow. One leg comes all the way up and forward and the neck dips
 * to keep the head where it was, which is what a wading bird actually does and
 * what nothing else in the roster does at all. */
GAITS.stalk = (m, g, f, w) => {
  if (f === 0) return g;
  const L = m.legs || [];
  const h = m.size;
  if (f === 2) {
    if (m.head) g = moveBlock(g, m.headX[0], m.headX[1], m.head[0], m.head[1], 0, 1, w);
    return g;
  }
  const i = f === 1 ? 0 : L.length - 1;
  const leg = L[i];
  if (leg) g = moveBlock(g, leg[0], leg[1], m.legTop, h - 1, f === 1 ? 1 : -1, -4, w);
  if (m.arms) {
    for (const [x0, x1, y0, y1] of m.arms) {
      g = moveBlock(g, x0, x1, y0, y1, 0, f === 1 ? -1 : 1, w);
    }
  }
  return g;
};

/* Crouch, air, land. The whole creature leaves the ground on one frame of four,
 * which is the loudest thing any gait in here does. */
GAITS.hop = (m, g, f, w) => {
  const h = m.size;
  const L = m.legs || [];
  if (f === 0) return bobBand(g, 0, m.legTop - 1, 1, w);       // crouch
  if (f === 1) {
    let out = bobBand(g, 0, h - 1, -3, w);                     // air
    for (const leg of L) out = moveBlock(out, leg[0], leg[1], m.legTop - 3, h - 1, 0, -2, w);
    return out;
  }
  if (f === 2) return bobBand(g, 0, h - 1, -1, w);
  return g;                                                     // land
};

/* Hanging. The arms hold the branch and the body swings under them, which puts
 * the only moving mass in the BOTTOM two thirds of the box — the reverse of
 * every other gait here. */
GAITS.brachiate = (m, g, f, w) => {
  if (f === 0) return g;
  const top = m.arms && m.arms[0] ? m.arms[0][3] : 8;
  let out = shiftBand(g, top, m.size - 1, f === 1 ? 1 : -1, w);
  out = bobBand(out, top + 2, m.size - 1, f === 1 ? 1 : 0, w);
  return out;
};

/* Planted. A thing on a stake cannot walk and does not hover: the base stays
 * exactly where it is and everything above it leans, which is the only motion
 * available to a scarecrow and is therefore the whole read. */
GAITS.sway = (m, g, f, w) => {
  if (f === 0) return g;
  const top = m.head ? m.head[1] + 4 : Math.round(m.size / 2);
  const dir = f === 1 ? 1 : -1;
  let out = shiftBand(g, 0, top, dir, w);
  if (m.arms) {
    for (const [x0, x1, y0, y1] of m.arms) out = moveBlock(out, x0, x1, y0, y1, 0, f === 2 ? 1 : 0, w);
  }
  return out;
};

/* A rotation, not a step. The ring of keys turns around a shaft that does not
 * move at all — which is the only honest way to animate a thing whose whole
 * silhouette is a vertical line. */
GAITS.orbit = (m, g, f, w) => {
  if (!m.orbit || !f) return g;
  const dx = [0, 1, 0, -1][f % 4];
  const dy = [0, 0, -1, 0][f % 4];
  let out = g;
  for (const [x0, x1, y0, y1] of m.orbit) out = moveBlock(out, x0, x1, y0, y1, dx, dy, w);
  return out;
};

/* One figure walks and the mass behind it does not. `front` is the column-and-
 * row rectangle the walking figure occupies; everything outside it is held
 * perfectly still, because the thing standing behind this creature is the whole
 * point of it and a horror that bobs along is a costume. */
GAITS.loom = (m, g, f, w) => {
  if (!f || !m.front) return g;
  const [fx0, fx1, fy0, fy1] = m.front;
  const L = m.legs || [];
  let out = g;
  if (f === 2) return moveBlock(out, fx0, fx1, fy0, m.legTop - 1, 0, -1, w);
  const leg = f === 1 ? L[0] : L[L.length - 1];
  if (leg) out = moveBlock(out, leg[0], leg[1], m.legTop, fy1, 0, -2, w);
  out = moveBlock(out, fx0, fx1, fy0, m.legTop - 1, f === 1 ? 1 : -1, 0, w);
  return out;
};

GAITS.default = GAITS.fourbeat;

/* ------------------------------------------------------------------ idles
 *
 * Four frames each, always, and the fourth is a TELL that belongs to that
 * family alone. A player reads a problem statement for ten seconds with a
 * monster on screen, and a monster that holds perfectly still for ten seconds
 * is a dead monster.
 */

const IDLES = {};

IDLES.breathe = (m, g, f, w) => {
  if (f === 1) return bobBand(g, m.head ? m.head[0] : 0, m.spine ? m.spine[0] : 4, 1, w);
  if (f === 3 && m.tail) {
    return moveBlock(g, m.tailX[0], m.tailX[1], m.tail[0], m.tail[1], 0, -1, w);
  }
  if (f === 3 && m.head) return shiftBand(g, m.head[0], m.head[1], 1, w);
  return g;
};

IDLES.rattle = (m, g, f, w) => {
  if (f === 1 && m.jaw) return moveBlock(g, m.jawX[0], m.jawX[1], m.jaw[0], m.jaw[1], 0, 1, w);
  if (f === 1) return bobBand(g, 0, m.spine ? m.spine[0] : 4, 1, w);
  if (f === 3) {
    let out = m.head ? shiftBand(g, m.head[0], m.head[1], 1, w) : g;
    if (m.jaw) out = moveBlock(out, m.jawX[0], m.jawX[1], m.jaw[0], m.jaw[1], 1, 1, w);
    return out;
  }
  return g;
};

IDLES.preen = (m, g, f, w) => {
  if (f === 1) return moveBlock(g, m.headX[0], m.headX[1], m.head[0], m.head[1], 0, 1, w);
  if (f === 3) return moveBlock(g, m.headX[0], m.headX[1], m.head[0], m.head[1], -1, 2, w);
  return g;
};

IDLES.pulse = (m, g, f, w) => {
  if (f === 1) return swapAccent(bobBand(g, 0, m.size - 1, -1, w));
  if (f === 2) return frayEdge(g, m.fray, `${m.key}:idle`, w);
  if (f === 3) return swapAccent(g);
  return g;
};

IDLES.twitch = (m, g, f, w) => {
  const arms = m.arms || m.wing;
  if (f === 1 && arms) {
    let out = g;
    for (const [x0, x1, y0, y1] of arms) out = moveBlock(out, x0, x1, y0, y1, 0, -1, w);
    return out;
  }
  if (f === 3) {
    let out = m.head ? moveBlock(g, m.headX[0], m.headX[1], m.head[0], m.head[1], 1, 0, w) : g;
    if (arms) for (const [x0, x1, y0, y1] of arms) out = moveBlock(out, x0, x1, y0, y1, 0, 1, w);
    return out;
  }
  return g;
};

IDLES.coil = (m, g, f, w) => {
  const s = m.spine || [0, m.size - 1];
  if (f === 0) return g;
  return waveBand(g, s[0], s[1], f === 3 ? 4 : f, w, 1);
};

IDLES.drift = (m, g, f, w) => {
  const dy = [0, -1, -1, 0][f % 4];
  let out = dy ? bobBand(g, 0, m.size - 1, dy, w) : g;
  out = frayEdge(out, m.fray, `${m.key}:idle:${f}`, w);
  if (f === 3) out = swapAccent(out);
  return out;
};

IDLES.default = IDLES.breathe;

/* --------------------------------------------------------------- palette
 *
 * Every tone comes off a shared ramp in palette.js, which is the rule that makes
 * a monster belong in the same world as the hero fighting it. A creature whose
 * greens were picked by eye would be a creature that reads as a sticker.
 *
 * Thirteen slots for a mob and fifteen for an apex, and the two extra are both
 * apex furniture: the core specular and the aura. Counted off the raster by
 * scripts/verify/monsters.mjs, never off this dict.
 *
 * The server sends one colour per enemy (bestiary.py `colour`), not a ramp.
 * When it does, rampFor() derives a five-step material from it under the same
 * low hot key light every other ramp here was built against, so an enemy nobody
 * has drawn a palette for still arrives lit correctly.
 */

const FAMILY_TINT = {
  FIRE: 6, LIGHTNING: 4, NEUTRAL: 0, BRUTE: 0, POISON: -2, COLD: -6, VOID: -6,
};

export function monsterPalette(entry, opts) {
  const o = opts || {};
  const m = typeof entry === 'string' ? MONSTERS[entry] : entry;
  const spec = m || M[MONSTER_FALLBACK];

  const body = (typeof o.colour === 'string' && o.colour.charAt(0) === '#')
    ? rampFor(o.colour, 'organic', SHADE.LIGHT)
    : (RAMPS[spec.body] || RAMPS.cloth);
  const accent = RAMPS[spec.accent] || RAMPS.earth;
  const hard = RAMPS[spec.hard] || RAMPS.bone;
  const core = spec.core ? (RAMPS[spec.core] || RAMPS.ember) : null;

  // The family's temperature. FIRE and LIGHTNING rotate toward the hot key
  // light, COLD and VOID away from it — so two creatures sharing a ramp still
  // read as belonging to different weather, and a region's monsters agree with
  // its sky without any of them leaving the shared material set.
  const t = FAMILY_TINT[spec.family] || 0;
  const lit = t === 0 ? (c => c) : t > 0 ? (c => warmer(c, t)) : (c => cooler(c, -t));

  const pal = {
    // The outline stays heavy and the rim does all the lighting, exactly as the
    // hero rig does it: applyRim's lifted outline plus a rim reads as a smeared
    // double edge at this size.
    o: OUTLINE, O: OUTLINE, e: OUTLINE,
    D: body[SHADE.DEEP], d: body[SHADE.DARK], B: body[SHADE.MID],
    L: lit(body[SHADE.LIGHT]), H: lit(body[SHADE.SPEC]),
    a: accent[SHADE.DARK], A: accent[SHADE.LIGHT],
    g: hard[SHADE.LIGHT],
    w: '#f2f6ff',
    // Ink is a hole, not a shadow: a socket, an open mouth, the gap between
    // ribs. It is darker than the body's deepest step and it is never lit, so a
    // skull reads as having nothing behind its eyes rather than as having a
    // very dark forehead.
    k: mix(OUTLINE, body[SHADE.DEEP], 0.35),
    c: core ? core[SHADE.SPEC] : accent[SHADE.SPEC],
    R: rimTone(body[SHADE.SPEC]),
  };
  if (spec.apex) {
    pal.C = core ? mix(core[SHADE.SPEC], '#ffffff', 0.45) : mix(pal.c, '#ffffff', 0.45);
    pal.r = core ? core[SHADE.LIGHT] : accent[SHADE.LIGHT];
  }
  return pal;
}

/* ------------------------------------------------------------------ cache
 *
 * A Map keyed by an authored string, a cap, and oldest-out eviction, the same
 * discipline every other rig here uses.
 *
 * Sized against the worst case the UI can actually produce rather than against
 * the common one. A battle asks for one creature x four frames x two poses: 8
 * entries. The bestiary screen is the real load — a region's whole roster plus
 * its apex, at four frames and two poses, with a colour override per enemy:
 * 4 creatures x 8 x a handful of colours. 720 clears the largest region twice
 * over with room for the fallbacks.
 */
const monCache = new Map();
const MON_CACHE_MAX = 720;
const baseCache = new Map();
const BASE_CACHE_MAX = 96;

function capCache(map, max) {
  while (map.size > max) {
    const oldest = map.keys().next();
    if (oldest.done) break;
    map.delete(oldest.value);
  }
}

export function clearMonsterCache() { monCache.clear(); baseCache.clear(); }
export function monsterCacheStats() {
  return { size: monCache.size, cap: MON_CACHE_MAX, bases: baseCache.size,
           baseCap: BASE_CACHE_MAX, full: monCache.size >= MON_CACHE_MAX };
}

/* The authored rows placed in their own box, once. `oy` defaults to standing on
 * the last row, so a quadruped and a wading bird plant on the same line without
 * anybody counting rows. */
function baseGrid(key) {
  const hit = baseCache.get(key);
  if (hit) return hit;
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  const g = mergeGrids(size, size, [{ grid: m.rows, ox: m.ox | 0, oy: m.oy | 0 }]);
  if (baseCache.size >= BASE_CACHE_MAX) baseCache.delete(baseCache.keys().next().value);
  baseCache.set(key, g);
  return g;
}

/* ------------------------------------------------------------------ frames */

/** The most frames any creature has. Per-family counts are in monsterMotion(),
 *  and they run from two to four: a tortoise-paced statue does not need four
 *  and a hummingbird cannot be read at two. */
export const MON_FRAME_COUNT = 4;

/** The idle is always four, for every creature, because the idle is what the
 *  player actually looks at while reading a problem statement. */
export const MON_IDLE_FRAMES = 4;

/** The mirrored box for a creature. Mobs 24, apexes 32. */
export function monsterSize(name, opts) {
  return (MONSTERS[monsterKeyFor(name, opts)] || {}).size || MON_SIZE;
}

/* The authored grid for one creature, frame and pose, before it is lit. Split
 * out from monsterFrame because the silhouette check wants the shape without
 * paying for a raster. */
function monsterGrid(key, frame, pose) {
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  const g0 = baseGrid(key);
  const idle = pose === 'idle';
  const n = idle ? MON_IDLE_FRAMES : Math.max(2, Math.min(MON_FRAME_COUNT, m.frames || 4));
  const f = ((((frame | 0) % n) + n) % n);
  const fn = idle ? (IDLES[m.idle] || IDLES.default) : (GAITS[m.gait] || GAITS.default);
  let g = fn(m, g0, f, size);
  // A fray band is the creature's own bottom edge, so a hover creature's base
  // frame must fray too or frame 0 is the only one with a flat hem and the
  // cycle ticks.
  if (!idle && m.fray && f === 0) g = frayEdge(g, m.fray, `${key}:0`, size);
  return g;
}

/** One frame, cached.
 *
 *  @param name   a bestiary `sprite`, an authored key, a hunters.py row, or a
 *                whole enemy object. A name nobody has drawn resolves to an
 *                unmarked body in the region's colours and never throws.
 *  @param frame  any integer; wrapped into that creature's own cycle
 *  @param opts   { region, colour, pose: 'walk'|'idle', apex, flip }
 *  @returns a canvas, 24x24 or 32x32. It is the CACHED instance — draw it, do
 *           not edit it.
 */
export function monsterFrame(name, frame = 0, opts) {
  const o = opts || {};
  const key = monsterKeyFor(name, o);
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  const pose = o.pose === 'idle' ? 'idle' : 'walk';
  const colour = (typeof o.colour === 'string' && o.colour.charAt(0) === '#')
    ? o.colour : '';
  // An apex drawn from a mob body — the honest fallback for a region nobody
  // recognises — still gets the apex furniture, or the rank is invisible.
  const apex = !!m.apex;
  const n = pose === 'idle' ? MON_IDLE_FRAMES
                            : Math.max(2, Math.min(MON_FRAME_COUNT, m.frames || 4));
  const f = ((((frame | 0) % n) + n) % n);

  const ck = `${key}:${f}:${pose}:${colour}:${apex ? 1 : 0}:${o.flip ? 1 : 0}`;
  const hit = monCache.get(ck);
  if (hit) return hit;

  let grid = monsterGrid(key, f, pose);
  if (o.flip) grid = normalise(grid, size).map(r => r.split('').reverse().join(''));
  // Thicken BEFORE lighting so the doubled edge is lit as one outline. Doing it
  // afterwards produces two edges, one lit and one not, which reads as a sprite
  // with a bad drop shadow.
  if (apex) grid = thicken(grid, size);

  // One merge, then one light, in the order sprites.js fixed for the whole cast:
  // the soft upper-left fill, then the single hot rim from low-left INSIDE the
  // heavy outline. The eye, the ink, the core and the aura are protected — an
  // authored pixel that the shading pass eats is an authored pixel wasted.
  grid = rimLowLeft(applyRim(grid), 'R', 'wekcCr');

  // The aura goes on last of all, outside the outline, after the lighting has
  // finished. It is not a surface, so it must not be lit like one.
  if (apex) grid = aura(grid, `${key}:${f}:${pose}`, 4, size);

  const canvas = gridSprite(grid, monsterPalette(m, { colour }), size, size);
  monCache.set(ck, canvas);
  capCache(monCache, MON_CACHE_MAX);
  return canvas;
}

/** Every frame of one pose, ready to index. */
export function monsterFrames(name, opts) {
  const o = opts || {};
  const m = MONSTERS[monsterKeyFor(name, o)] || M[MONSTER_FALLBACK];
  const n = o.pose === 'idle' ? MON_IDLE_FRAMES
                              : Math.max(2, Math.min(MON_FRAME_COUNT, m.frames || 4));
  const out = [];
  for (let f = 0; f < n; f++) out.push(monsterFrame(name, f, o));
  return out;
}

/** The sprites.js enemySprite() signature, so a call site already drawing an
 *  enemy swaps to this without moving an argument. `pattern` is accepted and
 *  ignored on purpose: colouring a monster by the problem it happens to be
 *  carrying is what made the bestiary unmemorable, and the species owns its own
 *  colour here. Pass `opts.region` to get the region's creature rather than the
 *  default roster's. */
export function monsterSprite(spriteKey, pattern, frame = 0, override, opts) {
  return monsterFrame(spriteKey, frame,
    Object.assign({}, opts, { colour: override || (opts && opts.colour) || '' }));
}

/** The readability check: the shape at 16px with colour discarded entirely.
 *  Returns rows of '#' and '.', which is what makes it diffable and countable. */
export function monsterSilhouette(name, frame = 0, opts) {
  const o = opts || {};
  const key = monsterKeyFor(name, o);
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  let g = monsterGrid(key, frame, o.pose === 'idle' ? 'idle' : 'walk');
  if (m.apex) g = thicken(g, size);
  return silhouetteAt(g, 16);
}

/* --------------------------------------------------------------- motion */

/** What a renderer needs to move a creature that is standing still. `bob` is
 *  peak vertical travel in source pixels, `sway` horizontal, `phase` staggers
 *  creatures of the same species so a group never pulses in lockstep, `period`
 *  is one full cycle in milliseconds, `frames` is that family's own count. */
export function monsterMotion(name, opts) {
  const m = MONSTERS[monsterKeyFor(name, opts)] || M[MONSTER_FALLBACK];
  return {
    frames: Math.max(2, Math.min(MON_FRAME_COUNT, m.frames || 4)),
    idleFrames: MON_IDLE_FRAMES,
    period: m.period || 800, idlePeriod: (m.period || 800) * 3,
    bob: m.bob || 0, sway: m.sway || 0, phase: m.phase || 0,
    gait: m.gait, idle: m.idle, apex: !!m.apex, size: m.size || MON_SIZE,
  };
}

/** The frame index and sub-pixel offsets for a given wall-clock time. Everything
 *  in it is a function of `timeMs` and `seed`, so two runs agree. */
export function monsterFrameAt(name, timeMs = 0, pose = 'walk', seed = 0, opts) {
  const mo = monsterMotion(name, opts);
  const n = pose === 'idle' ? mo.idleFrames : mo.frames;
  const period = pose === 'idle' ? mo.idlePeriod : mo.period;
  const t = (timeMs / period) + mo.phase + (seed % 16) / 16;
  const f = Math.floor(t * n) % n;
  const step = (t * n) % 1;
  return {
    frame: (f + n) % n,
    dx: mo.sway ? Math.round(Math.sin(t * Math.PI * 2) * mo.sway) : 0,
    dy: mo.bob ? -Math.round(Math.abs(Math.sin(t * Math.PI)) * mo.bob) : 0,
    step,
  };
}

/** A ground shadow sized off the creature's own footprint, so a wading bird
 *  does not sit on a shadow a crocodile's width. A hovering creature gets a
 *  smaller, softer one on purpose: it is further off the floor. */
export function monsterShadow(name, opts) {
  const key = monsterKeyFor(name, opts);
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  const g = baseGrid(key);
  let lo = size, hi = -1;
  for (let y = size - 4; y < size; y++) {
    if (y < 0) continue;
    for (let x = 0; x < size; x++) {
      if (EMPTY_CH(g[y][x])) continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
  }
  const rx = hi >= lo ? Math.max(4, Math.round((hi - lo + 1) / 2)) : Math.round(size / 4);
  const bodiless = !(m.legs && m.legs.length);
  return { rx: bodiless ? Math.max(3, rx - 2) : rx,
           ry: Math.max(2, Math.round(rx * 0.38)),
           alpha: bodiless ? 0.22 : 0.34 };
}

/* ------------------------------------------------------------------ stats
 *
 * What this module will let itself be measured on. Everything here is counted
 * off the authored grids rather than asserted, and scripts/verify/monsters.mjs
 * reads it and fails on the numbers rather than on an opinion.
 */

function silhouetteArea(rows) {
  return rows.reduce((n, r) => n + [...r].filter(c => c === '#').length, 0);
}

/* The size a creature is actually DRAWN at, in its own pixels, after the apex
 * outline pass. This is the number that carries "an apex reads as an apex
 * before any health bar is seen" — the 16px silhouette below normalises scale
 * away by construction, which makes it the right instrument for telling two
 * shapes apart and the wrong one for telling a big thing from a small one. Both
 * are reported, because they answer different questions. */
function drawnCells(key, frame = 0, pose = 'walk') {
  const m = MONSTERS[key] || M[MONSTER_FALLBACK];
  const size = m.size || MON_SIZE;
  let g = monsterGrid(key, frame, pose);
  if (m.apex) g = thicken(g, size);
  let n = 0, top = size, bottom = -1, left = size, right = -1;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (EMPTY_CH(g[y][x])) continue;
      n++;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
      if (x < left) left = x;
      if (x > right) right = x;
    }
  }
  return { area: n, h: bottom - top + 1, w: right - left + 1 };
}

function silDiff(a, b) {
  let n = 0;
  for (let y = 0; y < a.length; y++) {
    for (let x = 0; x < a[y].length; x++) if (a[y][x] !== b[y][x]) n++;
  }
  return n;
}

export function monsterArtStats() {
  const rows = [];
  const sils = {};
  const drawnBy = {};
  for (const key of MONSTER_KEYS) {
    const m = MONSTERS[key];
    const size = m.size || MON_SIZE;
    const n = Math.max(2, Math.min(MON_FRAME_COUNT, m.frames || 4));
    const walk = [];
    for (let f = 0; f < n; f++) walk.push(monsterGrid(key, f, 'walk'));
    // How much of the walk actually moves, with colour discarded. A frame that
    // differs from the last by nothing is not a frame, and this is the number
    // that says so.
    let moved = 0;
    for (let i = 0; i < walk.length; i++) {
      const b = walk[(i + 1) % walk.length];
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const p = !EMPTY_CH(walk[i][y][x]), q = !EMPTY_CH(b[y][x]);
          if (p !== q) moved++;
        }
      }
    }
    let idleMoved = 0;
    const idle = [];
    for (let f = 0; f < MON_IDLE_FRAMES; f++) idle.push(monsterGrid(key, f, 'idle'));
    for (let i = 0; i < idle.length; i++) {
      const b = idle[(i + 1) % idle.length];
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          if (idle[i][y][x] !== b[y][x]) idleMoved++;
        }
      }
    }
    // Does it ever touch the floor? A thing with no legs must not, in any frame
    // of either pose, or the gait is lying about what the creature is.
    let touchesFloor = false;
    for (const g of walk.concat(idle)) {
      const last = g[size - 1] || '';
      if ([...last].some(c => !EMPTY_CH(c))) touchesFloor = true;
    }
    const sil = monsterSilhouette(key, 0);
    sils[key] = sil;
    const drawn = drawnCells(key);
    drawnBy[key] = drawn;
    rows.push({
      monster: key, apex: !!m.apex, family: m.family,
      role: m.apex ? 'apex' : MONSTER_ROLES[key], gait: m.gait, idle: m.idle,
      frames: n, legs: (m.legs || []).length,
      silhouette16: silhouetteArea(sil),
      drawnPixels: drawn.area, drawnBox: `${drawn.w}x${drawn.h}`,
      outlineChangedPerWalkCycle: moved,
      cellsChangedPerIdleCycle: idleMoved,
      touchesFloor,
    });
  }

  // The closest pair in the whole roster, with colour gone. Two creatures with
  // the same 16px outline are one creature with two names.
  let worst = Infinity, worstPair = null;
  const keys = MONSTER_KEYS;
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const d = silDiff(sils[keys[i]], sils[keys[j]]);
      if (d < worst) { worst = d; worstPair = [keys[i], keys[j]]; }
    }
  }

  // And the closest pair WITHIN a region, which is the pair a player actually
  // sees side by side and the only one that has to survive a thumbnail.
  const perRegion = [];
  for (const region of Object.keys(REGION_BIOME)) {
    const cast = rosterFor(region).concat([apexKeyFor(region)]);
    let near = Infinity, pair = null;
    for (let i = 0; i < cast.length; i++) {
      for (let j = i + 1; j < cast.length; j++) {
        const d = silDiff(sils[cast[i]], sils[cast[j]]);
        if (d < near) { near = d; pair = [cast[i], cast[j]]; }
      }
    }
    const apexKey = apexKeyFor(region);
    const apexDrawn = drawnBy[apexKey];
    const biggestMob = rosterFor(region)
      .reduce((p, k) => (drawnBy[k].area > drawnBy[p].area ? k : p), rosterFor(region)[0]);
    const mobDrawn = drawnBy[biggestMob];
    perRegion.push({
      region, biome: REGION_BIOME[region], element: elementOf(region),
      cast, closestPair: pair, pixelsOfOutlineThatDiffer: near,
      apex: apexKey,
      apexSilhouette16: silhouetteArea(sils[apexKey]),
      apexDrawnPixels: apexDrawn.area, apexDrawnBox: `${apexDrawn.w}x${apexDrawn.h}`,
      largestMob: biggestMob, largestMobDrawnPixels: mobDrawn.area,
      largestMobDrawnBox: `${mobDrawn.w}x${mobDrawn.h}`,
      apexTimesLargerThanAnyMob: Math.round((apexDrawn.area / mobDrawn.area) * 100) / 100,
      apexIsLarger: apexDrawn.area > mobDrawn.area,
    });
  }

  return {
    creatures: MONSTER_KEYS.length, mobs: MOB_KEYS.length, apexes: APEX_KEYS.length,
    box: `${MON_SIZE}x${MON_SIZE}`, apexBox: `${APEX_SIZE}x${APEX_SIZE}`,
    regions: Object.keys(REGION_BIOME).length,
    gaits: [...new Set(MONSTER_KEYS.map(k => MONSTERS[k].gait))].length,
    cache: monsterCacheStats(),
    closestPairAnywhere: { pair: worstPair, pixelsOfOutlineThatDiffer: worst },
    perRegion, rows,
  };
}

/* ------------------------------------------------------------------ notes
 *
 * INTEGRATION, for whoever wires this up.
 *
 *   import * as monsterart from './monsterart.js';
 *
 *   // battle, in place of sprites.enemySprite:
 *   const img = monsterart.monsterFrame(enemy.sprite, frame,
 *                 { region: scene.region, colour: enemy.colour });
 *
 *   // overworld, for a hunter walking toward the player:
 *   const mo = monsterart.monsterMotion(hunter.sprite, { apex: true, region });
 *   const at = monsterart.monsterFrameAt(hunter.sprite, timeMs, 'walk', seed);
 *   const img = monsterart.monsterFrame(hunter.sprite, at.frame,
 *                 { apex: true, region, flip: hunter.vx < 0 });
 *   const sh  = monsterart.monsterShadow(hunter.sprite, { apex: true, region });
 *
 * The canvases are cached instances. Draw them; do not draw INTO them. `region`
 * is the one option worth threading everywhere: without it a bestiary sprite
 * key resolves against the default roster and the Marsh gets the Fields'
 * animals, which is the bug this whole file is a fix for.
 *
 * Sizes are not uniform and must not be assumed: monsterSize(name, opts) is 24
 * for a mob and 32 for an apex, and monsterShadow() returns the footprint that
 * goes under it. Both answer for a fallback too.
 *
 * WHEN gauntlet/hunters.py LANDS. Nothing here needs to change. Pass the hunter
 * row straight to apexKeyFor(): a row carrying `region` resolves by region, a
 * row whose name happens to match an apex resolves by name, and a row with
 * neither draws APEX_FALLBACK at apex size rather than throwing. If hunters.py
 * ships names worth showing, APEX_NAMES is the table to retire.
 */
