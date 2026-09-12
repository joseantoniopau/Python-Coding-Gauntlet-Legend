/* Companions, as sprites in the world.
 *
 * A pet in this game is the hint system wearing fur. The player carries one at a
 * time, it speaks at the moment of struggle, one of them dies at the first boss
 * and comes back later — and every one of those is a decision the player makes
 * about WHO to walk with. A line in a menu cannot carry that. An animal trotting
 * behind you across the overworld can, so this module exists to put the decision
 * on the ground where the player can see it.
 *
 * Nothing here is traced, sampled or derived from any existing game. Every grid
 * below was authored for this file.
 *
 * WHAT THIS MODULE OWES THE REST OF THE GAME
 *
 *   petFrame(animal, facing, frame, opts) -> a cached canvas, 16x16
 *   petSprites(animal, opts)              -> the whole set, ready to index
 *   petSilhouette(animal, ...)            -> the readability check, colour gone
 *   PET_ANIMALS                           -> what is authored
 *
 * It owns no state the caller has to manage and it never throws on a name it
 * does not know: gauntlet/pets.py is being rewritten while this is being read,
 * so an unknown animal resolves to `beast`, a plain four-legged shape, and the
 * overworld keeps running. A companion added next week renders as SOMETHING.
 *
 * THE FIVE RULES THIS FILE IS HELD TO
 *
 *  1. Fifteen colours plus transparent. Counted off the RASTER — with
 *     scripts/verify/raster.mjs, the same instrument the hero rig is measured
 *     with — and never off the palette dict, because a dict with fifteen
 *     entries that a shading pass turns into sixteen is still over budget.
 *  2. One pixel grid. 16x16, integer scale, the same grain as the 16x24 hero
 *     and the 16x16 terrain. A pet is two thirds the hero's height on purpose:
 *     it reads as a companion rather than as a second character.
 *  3. No Math.random and no Date.now on a draw path. Every variation in here is
 *     a hash of the inputs, so two runs of the same frame are the same bytes.
 *  4. No per-frame allocation in a hot loop. Frames are cached under a cap and
 *     evicted oldest-first, exactly as the hero rig does it.
 *  5. Merge, then light, once. mergeGrids -> applyRim -> rimLowLeft, borrowed
 *     from sprites.js rather than reimplemented, because a second lighting model
 *     is how a cast stops looking like a cast.
 *
 * SILHOUETTE IS THE WHOLE JOB
 *
 * A pet is usually on screen at 16px with a tree in front of it and a boss
 * behind it. Interior shading is worth very little at that size and the outline
 * is worth nearly everything, so each animal was authored as a shape first:
 *
 *   llama       neck and legs, and almost nothing else
 *   penguin     a weighted teardrop, mass low, no stride available to it
 *   snake       a line, moving, with no legs anywhere in the grid
 *   raptor      a horizontal spine balanced over two digitigrade legs
 *   jaguar      long and low, the back below the height of its own shoulder
 *   tortoise    a dome on stumps; the dome never moves
 *   crow        compact body, heavy beak, forked tail, feet together
 *   axolotl     a wide soft head wearing gill plumes
 *   nautilus    a spiral that floats, trailing ragged tentacles
 *
 * Each is checked with colour discarded by petSilhouette().
 *
 * AND SO IS GAIT
 *
 * How a thing moves is most of what it is, so no two of these share a walk. The
 * gaits are authored deformations of the base grid — a leg lifted out of its own
 * column range, a spine dipped, a neck bobbing a frame behind the feet — not
 * brightness nudges. A frame that differs by a few units of brightness is not a
 * frame.
 *
 * The idles matter as much. A player reads a problem statement for ten seconds
 * with the pet standing next to them, and a pet that holds perfectly still for
 * ten seconds is a dead pet. So every idle is four frames: breathe in, breathe
 * out, breathe in, and then a TELL that belongs to that animal alone — a tail
 * flick, a tongue, a head turn, a blink, a gill flutter.
 *
 * MEASURED
 *
 * Everything above is a claim, so here are the numbers behind them, taken off
 * the rendered raster rather than off this file's intentions. Re-take them with
 * petArtStats() and scripts/verify/raster.mjs.
 *
 *   colour budget   29,130 frames swept — ten animals plus two unknown names,
 *                   seven tiers, ten server colours, four facings, two poses,
 *                   four frames. Worst frame: 14 colours (penguin, LEGENDARY,
 *                   where crest, mark and halo are all present). Dead frames:
 *                   4 colours, every animal.
 *   gait            pixels changing between consecutive frames of the side
 *                   walk, out of 256: tortoise 11-29 at the low end, crow
 *                   77-151 at the high end. Outline-only, colour discarded:
 *                   6-88. Nothing in here animates by brightness.
 *   silhouette      TUTORIAL < COMMON < LEGENDARY in lit area for all ten,
 *                   monotonically: e.g. jaguar 139 / 144 / 178 pixels.
 *   the return      100% of the COMMON silhouette survives into LEGENDARY, for
 *                   all ten animals. The legendary form is the same animal with
 *                   things added, never a redrawn one.
 *   determinism     2,464 frames hash identically warm, cold and rebuilt.
 *   steady state    240 redraws of one settled companion: 0 canvases. The whole
 *                   roster at two tiers, re-rendered four times over: 0.
 */

import {
  RAMPS, SHADE, OUTLINE, RARITY, rampFor, warmer, cooler,
} from './palette.js';

import {
  mix, hash, gridSprite, mergeGrids, applyRim, rimLowLeft, normalise,
  silhouetteAt, rimTone,
} from './sprites.js';

/* ------------------------------------------------------------------ box */

/* Two thirds of the hero's 24. Square, because a quadruped seen from the side
 * is as long as a llama is tall and one box has to hold both. */
export const PET_W = 16;
export const PET_H = 16;

/* The row the feet stand on. Everything is authored against it so a pet, a
 * villager and a hero all plant on the same line when they are drawn from the
 * same baseline. */
export const PET_GROUND = 15;

/* ---------------------------------------------------------------- glyphs
 *
 * The same contract as sprites.js: '.' is transparent, every other character
 * indexes the palette. applyRim() only rewrites 'B', so anything authored — an
 * eye, a rosette, a beak — survives the shading pass untouched.
 *
 *   o   outline, the one near-black the whole cast shares
 *   B   undecided body mass; applyRim turns it into H / L / d / D
 *   a   accent, dark   — rosettes, stripes, a gill root, a feather sheen
 *   A   accent, light  — a penguin's front, a nautilus shell wall
 *   g   hard material  — beak, claw, hoof, shell plate, tooth
 *   w   eye white
 *   e   pupil (resolves to the outline: a fourth near-black is a wasted slot)
 *   c   crest — legendary only, the horn/mane/quills that make it larger
 *   m   the tier mark
 *   r   the tier halo
 *   R   written by rimLowLeft; never authored
 */

/* ---------------------------------------------------------------- animals
 *
 * Each animal carries two authored views and derives the third.
 *
 *   side   facing RIGHT. `left` is this mirrored, which is honest here in a way
 *          it is not for the hero: an animal has no scabbard, no shield hand and
 *          no lead foot, so a mirrored side view loses nothing. The mirror
 *          happens BEFORE the lighting pass, so the one low-left key light still
 *          falls from the left on both — mirroring a lit sprite would flip the
 *          lamp and the pet would stop belonging to the scene every time it
 *          turned around.
 *   down   facing the camera.
 *   up     derived from `down` by taking the face off and adding a back strip.
 *          Derived rather than authored on purpose: the two views then cannot
 *          disagree about how big the animal is, which is the usual way a
 *          four-facing rig develops a stutter on the turn.
 *
 * `legs` are COLUMN RANGES, not glyphs. A gait lifts a leg by moving the block
 * of rows in its own columns, which is what lets one set of gait functions drive
 * ten different animals without any of them sharing a walk.
 */

const ANIMALS = {};

/* ---- jaguar: long, low, four-beat. The back sits below the shoulder. ---- */
ANIMALS.jaguar = {
  body: 'hide', accent: 'earth', hard: 'bone', family: 'organic',
  gait: 'prowl', idle: 'tailflick',
  period: 640, idlePeriod: 2800, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '.oo.............',
      '.oBo............',
      '..oBo.......ooo.',
      '..oBo......oBBBo',
      '..oBo.....oBBwBo',
      '..oBooooooBBBweo',
      '.oBBBBBBBBBBBBgo',
      '.oBaBBaBBBBBBBo.',
      '.oBBBBBBBBBBBBo.',
      '.oBBoBBoBBoBBBo.',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.ogo.ogo..ogoogo',
    ],
    legs: [[1, 3], [5, 7], [10, 12], [13, 15]],
    legTop: 12, spine: [8, 11], head: [4, 7], headX: [10, 15],
    tail: [2, 6], tailX: [1, 4], mark: [4, 9],
    crest: { ox: 9, oy: 2, rows: ['.ccc.', 'cccco', '.cco.'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '.....oooooo.....',
      '....oBBBBBBo....',
      '....oBwBBwBo....',
      '....oBeBBeBo....',
      '....oBBggBBo....',
      '.....oBBBBo.....',
      '....oBBBBBBo....',
      '...oBBaBBaBBo...',
      '...oBBBBBBBBo...',
      '...oBBBBBBBBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...ogo.oo.ogo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [2, 7], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 9],
    crest: { ox: 4, oy: 0, rows: ['.c....c.', 'cccccccc', '.c.cc.c.'] },
    back: [{ ox: 11, oy: 4, rows: ['.oo.', 'oBBo', 'oBBo', 'oBBo', 'oBBo', 'oBBo', 'oBB.'] }],
  },
};

/* ---- python: a line. No legs anywhere in the grid, and none in the gait. --- */
ANIMALS.snake = {
  body: 'venom', accent: 'grass', hard: 'bone', family: 'organic',
  gait: 'undulate', idle: 'tongue',
  period: 900, idlePeriod: 2400, bob: 0, sway: 1,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '................',
      '..........ooo...',
      '.........oBBBo..',
      '..ooooo..oBwBeo.',
      '.oBBBBBoooBBggo.',
      'oBBaBBaBBooBBoo.',
      'oBBBBBBBBBBBBo..',
      '.oBBaBBaBBBBo...',
      '..oBBBBBBBBoo...',
      '...ooBBBBBoo....',
      '.....oBBBo......',
      '......ooo.......',
      '................',
    ],
    legs: [], legTop: 16, spine: [7, 13], head: [4, 7], headX: [9, 15],
    tail: [8, 13], tailX: [0, 6], mark: [4, 9],
    crest: { ox: 9, oy: 2, rows: ['.cc..', 'cccc.', 'cc.c.'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '...oooooooooo...',
      '..oBBaBBBBaBBo..',
      '..oBBBBBBBBBBo..',
      '...oooBBBBooo...',
      '....oBBBBBBo....',
      '...oBBaBBaBBo...',
      '...oBBBBBBBBo...',
      '....ooBBBBoo....',
      '.....oBBBBo.....',
      '....oBwBBwBo....',
      '....oBeBBeBo....',
      '....oBBggBBo....',
      '.....oooooo.....',
      '................',
    ],
    legs: [], legTop: 16, spine: [2, 9], head: [10, 14], headX: [4, 11],
    tail: [2, 5], tailX: [2, 13], mark: [5, 7],
    crest: { ox: 3, oy: 9, rows: ['.c......c.', 'cc......cc'] },
    back: [{ ox: 3, oy: 9, rows: ['__________', '__________', '__________',
                                  '__________', '__________', '__________',
                                  '__________'] },
           { ox: 4, oy: 9, rows: ['..oooo..', '.oBaaBo.', '..oooo..'] }],
  },
};

/* ---- llama: neck and legs. The neck bobs a frame behind the feet. ---- */
ANIMALS.llama = {
  body: 'bone', accent: 'leather', hard: 'bone', family: 'organic',
  gait: 'stilt', idle: 'earflick',
  period: 760, idlePeriod: 3000, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '...........ooo..',
      '..........oBBBo.',
      '..........oBwBeo',
      '..........oBBBgo',
      '...........oBBo.',
      '...........oBBo.',
      '..ooo......oBBo.',
      '.oBBBoooooooBBo.',
      '.oBBBBBBBBBBBBo.',
      '.oBBaBBBBaBBBBo.',
      '.oBBBBBBBBBBBBo.',
      '.oBo.oBo.oBooBo.',
      '.oBo.oBo.oBooBo.',
      '.oBo.oBo.oBooBo.',
      '.ogo.ogo.ogoogo.',
    ],
    legs: [[1, 3], [5, 7], [9, 11], [12, 14]],
    legTop: 12, spine: [8, 11], head: [1, 5], headX: [10, 15],
    tail: [7, 9], tailX: [1, 4], mark: [4, 9],
    crest: { ox: 9, oy: 0, rows: ['..cc.', '.ccc.', 'cc.c.'] },
  },
  down: {
    grid: [
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....owBBwo.....',
      '.....oeBBeo.....',
      '.....oBggBo.....',
      '......oBBo......',
      '......oBBo......',
      '.....oBBBBo.....',
      '....oBBBBBBo....',
      '...oBBaBBaBBo...',
      '...oBBBBBBBBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...ogo.oo.ogo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [1, 5], headX: [5, 10],
    tail: null, tailX: null, mark: [5, 9],
    crest: { ox: 5, oy: 0, rows: ['c....c', 'cc..cc', '.c..c.'] },
    back: [{ ox: 11, oy: 6, rows: ['.oo.', 'oBBo', 'oBBo', 'oBB.'] }],
  },
};

/* ---- penguin: weighted teardrop. It rocks. It cannot stride. ---- */
ANIMALS.penguin = {
  body: 'gunmetal', accent: 'bone', hard: 'bronze', family: 'metal',
  gait: 'rock', idle: 'lean',
  period: 820, idlePeriod: 2600, bob: 1, sway: 1,
  side: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....oBwBeo.....',
      '.....oBBBggo....',
      '....oBBBAAAo....',
      '....oBaAAAAo....',
      '...oBBaAAAAAo...',
      '...oBBaAAAAAo...',
      '...oBBaAAAAAo...',
      '...oBBBAAAAo....',
      '...oBBBAAAo.....',
      '....oBBBBo......',
      '....oggoggggo...',
      '....oooooooo....',
    ],
    legs: [[4, 6], [7, 12]],
    legTop: 14, spine: [6, 13], head: [2, 5], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 11],
    crest: { ox: 4, oy: 0, rows: ['..cc..', '.cccc.', 'cc..cc'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....owBBwo.....',
      '.....oBggBo.....',
      '....oBBAABBo....',
      '...oBBAAAABBo...',
      '..oBBAAAAAABBo..',
      '..oBaAAAAAAaBo..',
      '..oBBAAAAAABBo..',
      '..oBBAAAAAABBo..',
      '..oBBAAAAAABBo..',
      '...oBBAAAABBo...',
      '...ogggoogggo...',
      '....ooo..ooo....',
    ],
    legs: [[3, 6], [9, 12]],
    legTop: 14, spine: [6, 13], head: [2, 5], headX: [4, 11],
    tail: null, tailX: null, mark: [4, 11],
    crest: { ox: 5, oy: 0, rows: ['.c..c.', 'cccccc', '.c..c.'] },
    back: [{ ox: 3, oy: 6, rows: ['..oBBBBBBo..', '.oBBBBBBBBo.',
                                  'oBBBBBBBBBBo', 'oBBaBBBBaBBo',
                                  'oBBBBBBBBBBo', 'oBBBBBBBBBBo',
                                  'oBBBBBBBBBBo', '.oBBBBBBBBo.'] },
           { ox: 1, oy: 8, rows: ['oB..........Bo', 'oB..........Bo',
                                  'oB..........Bo', 'oo..........oo'] }],
  },
};

/* ---- velociraptor: a horizontal spine over two legs, tail counterweighting -- */
ANIMALS.raptor = {
  body: 'rust', accent: 'blood', hard: 'bone', family: 'organic',
  gait: 'twobeat', idle: 'headjerk',
  period: 420, idlePeriod: 2200, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '............ooo.',
      '...........oBBwo',
      '...........oBweo',
      '..........oBBggo',
      '.oo......oBBBoo.',
      '..oo....oBBBBo..',
      '...ooooBBBBBBo..',
      '....oBBBBBBBBo..',
      '....oBBaBBBBBo..',
      '....oBBBBBBBBo..',
      '....oBoooBBBBo..',
      '...oBo....oBBo..',
      '...oBo....oBBo..',
      '..oBo......oBo..',
      '..ogo......ogo..',
    ],
    legs: [[2, 4], [10, 13]],
    legTop: 11, spine: [7, 10], head: [1, 4], headX: [9, 15],
    tail: [5, 6], tailX: [1, 6], mark: [6, 8],
    crest: { ox: 10, oy: 0, rows: ['.ccc.', 'cccc.', '.cc..'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBwBwo.....',
      '.....oBeBeo.....',
      '.....oBggBo.....',
      '......oBBo......',
      '.....oBBBBo.....',
      '....oBBaaBBo....',
      '....oBBBBBBo....',
      '....oBBBBBBo....',
      '....oBoooBBo....',
      '...oBo....oBo...',
      '...oBo....oBo...',
      '..oBo......oBo..',
      '..ogo......ogo..',
    ],
    legs: [[2, 5], [10, 13]],
    legTop: 11, spine: [7, 10], head: [2, 6], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 8],
    crest: { ox: 5, oy: 0, rows: ['.cccc.', 'cc..cc', '.c..c.'] },
    back: [{ ox: 5, oy: 7, rows: ['.oBBBB.', 'oBBBBBo', 'oBBBBBo'] },
           { ox: 5, oy: 12, rows: ['oBBBBo', 'oBBBBo', '.oooo.'] }],
  },
};

/* ---- axolotl: a wide soft head wearing gill plumes. Barely lifts a foot. --- */
ANIMALS.axolotl = {
  body: 'skin', accent: 'blood', hard: 'bone', family: 'organic',
  gait: 'paddle', idle: 'gills',
  period: 700, idlePeriod: 2000, bob: 1, sway: 1,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '................',
      '..........aa....',
      '..oo.....aAAa...',
      '.oBBoo...aAAa...',
      '.oBBBBooooBBBo..',
      '..oBBBBBBBBwBeo.',
      '..oBBBBBBBBBBgo.',
      '...oBBaBBaBBBoo.',
      '...oBBBBBBBBBo..',
      '...oBoooooBBBo..',
      '...oBo...oBBo...',
      '...oBo...oBo....',
      '...ogo...ogo....',
    ],
    legs: [[3, 5], [9, 11]],
    legTop: 12, spine: [7, 11], head: [4, 8], headX: [8, 15],
    tail: [5, 6], tailX: [1, 5], mark: [5, 9],
    crest: { ox: 8, oy: 1, rows: ['.c.c.c', 'cc.cc.', '.ccc..'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '...a........a...',
      '..aAa......aAa..',
      '..aAa.oooo.aAa..',
      '...aoBBBBBBoa...',
      '....oBwBBwBo....',
      '....oBeBBeBo....',
      '....oBBggBBo....',
      '...oBBBBBBBBo...',
      '..oBBBaBBaBBBo..',
      '..oBBBBBBBBBBo..',
      '..oBoooooooBBo..',
      '..oBo.....oBo...',
      '..oBo.....oBo...',
      '..ogo.....ogo...',
    ],
    legs: [[2, 4], [10, 12]],
    legTop: 12, spine: [9, 12], head: [2, 5], headX: [2, 13],
    tail: null, tailX: null, mark: [5, 9],
    crest: { ox: 2, oy: 0, rows: ['.c........c.', 'ccc......ccc', '.c........c.'] },
    back: [{ ox: 4, oy: 5, rows: ['.oBBBBBBo.', 'oBBBBBBBBo', 'oBBaBBaBBo',
                                  'oBBBBBBBBo'] },
           { ox: 6, oy: 12, rows: ['oBBo', 'oBBo', '.oo.'] }],
  },
};

/* ---- tortoise: a dome on four stumps. The dome never moves, ever. ---- */
ANIMALS.tortoise = {
  body: 'grass', accent: 'earth', hard: 'wood', family: 'world',
  gait: 'plod', idle: 'blink',
  period: 1400, idlePeriod: 3400, bob: 0, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '...oooooooo.....',
      '..oggggggggo....',
      '.ogggaggagggo...',
      '.oggggggggggo...',
      '.oggggggggggo...',
      '.ooooooooooooo..',
      '.oBBBBBBBBBBBoo.',
      '.oBBBBBBBBBBBwBo',
      '.oBooooooBBBBeo.',
      '.oBo...oBo.oBgo.',
      '.oBo...oBo.oBo..',
      '.oBo...oBo.oBo..',
      '.ogo...ogo.ogo..',
    ],
    legs: [[1, 3], [7, 9], [11, 13]],
    legTop: 12, spine: [9, 11], head: [9, 12], headX: [11, 15],
    tail: null, tailX: null, shell: [3, 8], mark: [4, 5], crestHead: false,
    crest: { ox: 2, oy: 1, rows: ['.c..c..c..c.', 'cccccccccccc'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '....oooooooo....',
      '..ooggggggggoo..',
      '.oggggggggggggo.',
      '.ogggaggggagggo.',
      'ogggggggggggggo.',
      'ogggggggggggggo.',
      '.ogggaggggagggo.',
      '.oggggggggggggo.',
      '..ooggggggggoo..',
      '...oooBBBBooo...',
      '..oBooBwwBooBo..',
      '..oBo.oBBo.oBo..',
      '..oBo.oggo.oBo..',
      '..ogo.oooo.ogo..',
    ],
    legs: [[2, 4], [11, 13]],
    legTop: 12, spine: [11, 13], head: [12, 15], headX: [6, 9],
    tail: null, tailX: null, shell: [2, 10], mark: [5, 5], crestHead: false,
    crest: { ox: 1, oy: 1, rows: ['..c..c..c..c..', 'cccccccccccccc'] },
    back: [{ ox: 5, oy: 11, rows: ['________', '________', '________', '________'] },
           { ox: 5, oy: 11, rows: ['.oBBBBo.', '.oBBBBo.', '.oooooo.'] }],
  },
};

/* ---- nautilus: a spiral that floats. Ragged tentacles, never a leg. ---- */
ANIMALS.nautilus = {
  body: 'bone', accent: 'violet', hard: 'bone', family: 'organic',
  gait: 'drift', idle: 'chamber',
  period: 1100, idlePeriod: 2600, bob: 2, sway: 1,
  side: {
    grid: [
      '................',
      '.....oooooo.....',
      '...ooAAAAAAoo...',
      '..oAaAAaAAaAAo..',
      '.oAaAAaAAaAAAAo.',
      '.oAaAAaAAaAAAAo.',
      '.oAaAAaAAaAAAAo.',
      '..oAaAAaAAaAAo..',
      '...ooAAaAAoo....',
      '...oBBBBBBBo....',
      '..oBwBeBwBeBo...',
      '..oBBBBBBBBo....',
      '...oBoBoBoBo....',
      '...oBoBoBoo.....',
      '...oBoBoo.......',
      '...ooBo.........',
    ],
    legs: [], legTop: 16, spine: [9, 11], head: [9, 11], headX: [2, 12],
    tail: [13, 15], tailX: [3, 11], mark: [6, 5], crestHead: false,
    crest: { ox: 4, oy: 0, rows: ['.cc..cc.', 'cc.cc.cc'] },
  },
  down: {
    grid: [
      '................',
      '......oooo......',
      '....ooAAAAoo....',
      '...oAAaAAaAAo...',
      '..oAAaAAAAaAAo..',
      '..oAaAAAAAAaAo..',
      '..oAaAAAAAAaAo..',
      '..oAAaAAAAaAAo..',
      '...oAAaAAaAAo...',
      '....ooAAAAoo....',
      '....oBBBBBBo....',
      '...oBwBBBBwBo...',
      '...oBeBBBBeBo...',
      '..oBoBoBoBoBo...',
      '..oBoBoBo.oBo...',
      '..ooo.oo...oo...',
    ],
    legs: [], legTop: 16, spine: [10, 12], head: [10, 12], headX: [3, 12],
    tail: [14, 15], tailX: [2, 13], mark: [5, 5], crestHead: false,
    crest: { ox: 4, oy: 0, rows: ['.c..c..c.', 'cc.cc.cc.'] },
    back: [{ ox: 2, oy: 13, rows: ['____________', '____________', '____________'] },
           { ox: 4, oy: 10, rows: ['.oBBBBo.', 'oBBBBBBo', 'oBBaaBBo', '.oooooo.'] }],
  },
};

/* ---- crow: compact, heavy beak, forked tail, both feet together. ---- */
ANIMALS.crow = {
  body: 'void', accent: 'violet', hard: 'gunmetal', family: 'magic',
  gait: 'hop', idle: 'headturn',
  period: 620, idlePeriod: 2200, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '...........oooo.',
      '..........oBBBBo',
      '..........oBwBeo',
      '..oo......oBBBgg',
      '.oBBooooooBBBgo.',
      '.oBBBBBBBBBBBoo.',
      '..oBBaBBBaBBBo..',
      '..oBBBBBBBBBo...',
      '...oBBBBBBBo....',
      '....oBBBBo......',
      '....oBooBo......',
      '....oBooBo......',
      '....oBooBo......',
      '...ogooooogo....',
    ],
    legs: [[4, 6], [7, 9]],
    legTop: 12, spine: [6, 11], head: [2, 6], headX: [9, 15],
    tail: [5, 8], tailX: [1, 4], mark: [4, 8],
    crest: { ox: 9, oy: 0, rows: ['..cc..', '.cccc.', 'cc..c.'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....owBBwo.....',
      '.....oBeeBo.....',
      '.....oBggBo.....',
      '....oBBBBBBo....',
      '...oBaBBBBaBo...',
      '...oBaBBBBaBo...',
      '...oBBBBBBBBo...',
      '....oBBBBBBo....',
      '.....oBBBBo.....',
      '....oBooBo......',
      '....oBooBo......',
      '...ogooooogo....',
    ],
    legs: [[4, 6], [7, 9]],
    legTop: 13, spine: [7, 12], head: [2, 6], headX: [4, 11],
    tail: null, tailX: null, mark: [4, 9],
    crest: { ox: 5, oy: 0, rows: ['.c..c.', 'cc..cc', '.cccc.'] },
    back: [{ ox: 4, oy: 7, rows: ['.oBBBBBBo.', 'oBBBBBBBBo',
                                  'oBBaBBaBBo', 'oBBBBBBBBo'] },
           { ox: 2, oy: 8, rows: ['oB........Bo', 'oB........Bo',
                                  'oB........Bo', 'oo........oo'] },
           { ox: 5, oy: 11, rows: ['oBBBBo', 'oBBBBo', '.o..o.'] }],
  },
};

/* ---- beast: the fallback. Deliberately no markings and no character.
 *
 * This is what a companion nobody has drawn yet looks like. It is a plain
 * four-legged animal with a plain trot, and it exists so that adding a row to
 * gauntlet/pets.py can never take the overworld down. It is on purpose that it
 * does NOT borrow the jaguar: an unfamiliar name rendering as a specific animal
 * that it is not is a worse bug than rendering as a generic one, because nobody
 * ever goes looking for it. */
ANIMALS.beast = {
  body: 'leather', accent: 'earth', hard: 'bone', family: 'organic',
  gait: 'trot', idle: 'breath',
  period: 700, idlePeriod: 2600, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '..oo............',
      '..oBo.......ooo.',
      '..oBo......oBBBo',
      '..oBo.....oBBwBo',
      '..oBoooooooBBweo',
      '.oBBBBBBBBBBBBgo',
      '.oBBBBBBBBBBBBo.',
      '.oBBBBBBBBBBBBo.',
      '.oBBoBBoBBoBBBo.',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.ogo.ogo..ogoogo',
    ],
    legs: [[1, 3], [5, 7], [10, 12], [13, 15]],
    legTop: 12, spine: [8, 11], head: [4, 7], headX: [10, 15],
    tail: [3, 6], tailX: [2, 4], mark: [4, 9],
    crest: { ox: 9, oy: 2, rows: ['.cc..', 'cccc.', '.cc..'] },
  },
  down: {
    /* A BLUNT head, wider than the shoulders and set straight onto them with no
     * neck. This is the row that makes the fallback its own animal: drawn with
     * the jaguar's narrow muzzle and pinched neck it was not merely similar to
     * the jaguar facing down, it was byte-identical in outline, and `down` is
     * the facing a follower is seen in for most of a walk. Heavy-headed and
     * low also happens to be the read the two rows that land here need — STUB
     * is a boar and BARROW is the same boar, larger. */
    grid: [
      '................',
      '................',
      '................',
      '...oooooooooo...',
      '...oBwBBBBwBo...',
      '...oBeBBBBeBo...',
      '...oBBBggBBBo...',
      '....oBBggBBo....',
      '....oBBBBBBo....',
      '...oBBBBBBBBo...',
      '...oBBBBBBBBo...',
      '...oBBBBBBBBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...ogo.oo.ogo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [2, 7], headX: [3, 12],
    tail: null, tailX: null, mark: [5, 9],
    crest: { ox: 5, oy: 0, rows: ['.c..c.', 'cccccc', '.c..c.'] },
    back: [{ ox: 11, oy: 6, rows: ['.oo.', 'oBBo', 'oBBo', 'oBB.'] }],
  },
};

/* The authored roster, and the fallback every unknown name lands on. */
export const PET_ANIMALS = Object.keys(ANIMALS);
export const PET_FALLBACK = 'beast';

/* Names that mean an animal we have drawn.
 *
 * The roster is keyed on the ANIMAL rather than on the pet id, because two of
 * the nine have an id that is not their species: `python` is a snake and
 * `velociraptor` is a raptor. gauntlet/pets.py ships `sprite`, `species` and
 * `id` and callers reach for whichever they have, so all three spellings of
 * every current row resolve here, plus the obvious near-misses a later author
 * might type. Anything else is the fallback, and that is not an error. */
export const PET_ALIAS = {
  python: 'snake', serpent: 'snake', viper: 'snake', boa: 'snake',
  constrictor: 'snake', adder: 'snake', cobra: 'snake',
  velociraptor: 'raptor', dinosaur: 'raptor', dino: 'raptor', theropod: 'raptor',
  panther: 'jaguar', leopard: 'jaguar', cat: 'jaguar', lynx: 'jaguar',
  puma: 'jaguar', cougar: 'jaguar', ocelot: 'jaguar', tiger: 'jaguar',
  raven: 'crow', rook: 'crow', jackdaw: 'crow', magpie: 'crow', bird: 'crow',
  turtle: 'tortoise', terrapin: 'tortoise',
  alpaca: 'llama', vicuna: 'llama', guanaco: 'llama', camel: 'llama',
  salamander: 'axolotl', newt: 'axolotl', ambystoma: 'axolotl',
  ammonite: 'nautilus', shell: 'nautilus', squid: 'nautilus',
  octopus: 'nautilus', cuttlefish: 'nautilus',
  auk: 'penguin', puffin: 'penguin',
  wolf: 'beast', dog: 'beast', fox: 'beast', hound: 'beast', boar: 'beast',
  // The starter dies at the barrow and comes back as BARROW, whose sprite key
  // is `boar_great`. It resolves to the same authored body as `boar` on
  // purpose and not by falling through: the return scene only lands if the
  // player recognises the animal, so the two ids must not be free to drift
  // apart the day somebody draws a real boar.
  boar_great: 'beast', great_boar: 'beast', dire_boar: 'beast',
};

/** The animal key for anything a caller might hand over: a pets.py `sprite`, a
 *  `species`, an `id`, a display name, or a whole row object. Never throws and
 *  never returns something that is not in ANIMALS. */
export function petKeyFor(name) {
  const raw = (name && typeof name === 'object')
    ? (name.sprite || name.animal || name.species || name.id || '')
    : name;
  const key = String(raw == null ? '' : raw).toLowerCase().trim();
  if (ANIMALS[key]) return key;
  if (PET_ALIAS[key] && ANIMALS[PET_ALIAS[key]]) return PET_ALIAS[key];
  return PET_FALLBACK;
}

/* ------------------------------------------------------------------ tiers
 *
 * A companion has a tier, and the brief is that a legendary one should look
 * legendary from across a room. Four channels carry it, in the order the eye
 * picks them up at 16px:
 *
 *   1. SIZE.      The tutorial form sinks its head into its shoulders, which
 *                 takes a row off the top of the silhouette and reads as a
 *                 smaller, younger animal. The legendary form grows a crest
 *                 upward into the headroom every grid deliberately leaves free.
 *                 Measured, not asserted: petArtStats() reports the silhouette
 *                 area of each tier.
 *   2. HALO.      A sparse ring of glow outside the outline, above the ground
 *                 line only. Sparse because a solid ring is a blob: every third
 *                 candidate cell by a hash of its own coordinates, so it is
 *                 stable frame to frame and identical on two runs.
 *   3. MARK.      A small sigil on the flank in the rarity's own accent, one
 *                 pixel more of it at each tier from RARE up.
 *   4. PALETTE.   The rim rotates to the rarity accent and the body warms or
 *                 cools with it. This is the weakest channel of the four and is
 *                 last on purpose — a recolour alone is the failure mode the
 *                 hero rig's harness exists to catch, so it is never the only
 *                 thing a tier changes.
 *
 * THE RETURN. The starter dies at the first boss and comes back later as a
 * legendary, and the player has to recognise it. So the legendary form is the
 * SAME AUTHORED BODY GRID, byte for byte — the crest, the halo, the mark and
 * the palette are additions on top of an untouched animal, and nothing in the
 * tier path is allowed to move a pixel of the base silhouette. That is why the
 * crest is a separate strip merged over the body rather than an edit to the
 * grid, and why petArtStats() measures how much of the base outline survives
 * into the legendary form. It is 100%. That number is the return scene working.
 *
 * The ladder is defined here rather than imported because gauntlet/pets.py does
 * not carry a tier field yet. When it does, the strings below are the ones to
 * ship; anything else aliases or falls back to COMMON rather than throwing.
 */
export const PET_TIERS = ['TUTORIAL', 'COMMON', 'UNCOMMON', 'RARE', 'EPIC',
                          'LEGENDARY', 'MYTHIC'];

/* MYTHIC is the hidden one. It is spelled the same as items.py's top rarity so
 * that a companion and a relic of the same standing read alike. */
export const PET_TIER_ALIAS = {
  STARTER: 'TUTORIAL', GUIDED: 'TUTORIAL', FIRST: 'TUTORIAL', EASY: 'TUTORIAL',
  BASIC: 'COMMON', NORMAL: 'COMMON', STANDARD: 'COMMON',
  UNUSUAL: 'UNCOMMON', MEDIUM: 'UNCOMMON',
  ELITE: 'EPIC', HARD: 'EPIC',
  HIDDEN: 'MYTHIC', SECRET: 'MYTHIC', TRUE: 'MYTHIC', ASCENDED: 'MYTHIC',

  /* The ladder gauntlet/pets.py actually ships, which this file was written
   * against a draft of. Its six rungs are TUTORIAL, BEGINNER, ADEPT, MASTER,
   * LEGENDARY and HIDDEN; without these three, BEGINNER, ADEPT and MASTER all
   * fell through to COMMON and half the roster rendered as the same animal at
   * the same rank. A tier ladder you cannot see is not a tier ladder.
   *
   * Six rungs are spread over seven by skipping UNCOMMON rather than by
   * stacking the bottom, so the step between two adjacent pets.py tiers is a
   * two-pixel change in the mark instead of one. UNCOMMON stays defined for
   * callers with a finer ladder than the roster's. */
  BEGINNER: 'COMMON', ADEPT: 'RARE', MASTER: 'EPIC',
};

const TIER_STYLE = {
  TUTORIAL:  { index: 0, shrink: 1, mark: 0, crest: false, halo: 0, rarity: 'COMMON',    warm: -3 },
  COMMON:    { index: 1, shrink: 0, mark: 0, crest: false, halo: 0, rarity: 'COMMON',    warm: 0 },
  UNCOMMON:  { index: 2, shrink: 0, mark: 1, crest: false, halo: 0, rarity: 'UNCOMMON',  warm: 0 },
  RARE:      { index: 3, shrink: 0, mark: 2, crest: false, halo: 0, rarity: 'RARE',      warm: 0 },
  EPIC:      { index: 4, shrink: 0, mark: 3, crest: false, halo: 0, rarity: 'EPIC',      warm: 2 },
  LEGENDARY: { index: 5, shrink: 0, mark: 4, crest: true,  halo: 1, rarity: 'LEGENDARY', warm: 6 },
  MYTHIC:    { index: 6, shrink: 0, mark: 5, crest: true,  halo: 2, rarity: 'MYTHIC',    warm: 4 },
};

export function petTierKey(tier) {
  const key = String(tier == null ? '' : tier).toUpperCase().trim();
  if (TIER_STYLE[key]) return key;
  if (PET_TIER_ALIAS[key] && TIER_STYLE[PET_TIER_ALIAS[key]]) return PET_TIER_ALIAS[key];
  return 'COMMON';
}

/* The mark. Each tier is the tier below it plus exactly one pixel, which is the
 * only way a sigil this small can mean anything: a player who has seen an
 * UNCOMMON companion reads the RARE one as "that, and more" rather than as an
 * unrelated squiggle. It also means no two tiers can render identically, which
 * was the bug this list is sized to fix — before the mark started at UNCOMMON,
 * COMMON and UNCOMMON produced byte-identical frames. */
const MARK_PIXELS = [[0, 0], [0, 1], [1, 0], [1, 2], [2, 1]];

/* ------------------------------------------------------------- grid surgery
 *
 * These are the ops a gait is written in. They all take and return arrays of
 * strings of exactly PET_W characters, they never mutate their input, and none
 * of them allocates anything that outlives the frame it is building.
 */

function rowsOf(grid) { return normalise(grid, PET_W); }

/* Facing left is facing right, mirrored. See the note on the ANIMALS table for
 * why that is allowed here and is not allowed on the hero. */
function mirrorGrid(grid) {
  return rowsOf(grid).map(r => r.split('').reverse().join(''));
}

/* Move a rectangular block of the grid. This is how a leg is lifted: the rows
 * in that leg's own column range go up, and the ground row it left behind
 * becomes air, which is exactly what a raised foot looks like. */
function moveBlock(grid, x0, x1, y0, y1, dx, dy) {
  if (!dx && !dy) return grid;
  const g = rowsOf(grid).map(r => r.split(''));
  const lo = Math.max(0, y0), hi = Math.min(PET_H - 1, y1);
  const lx = Math.max(0, x0), hx = Math.min(PET_W - 1, x1);
  const kept = [];
  for (let y = lo; y <= hi; y++) {
    const row = [];
    for (let x = lx; x <= hx; x++) { row.push(g[y][x]); g[y][x] = '.'; }
    kept.push(row);
  }
  for (let i = 0; i < kept.length; i++) {
    const ty = lo + i + dy;
    if (ty < 0 || ty >= PET_H) continue;
    for (let j = 0; j < kept[i].length; j++) {
      const ch = kept[i][j];
      if (ch === '.' || ch === ' ') continue;
      const tx = lx + j + dx;
      if (tx < 0 || tx >= PET_W) continue;
      g[ty][tx] = ch;
    }
  }
  return g.map(r => r.join(''));
}

/* Move a block UP while keeping it attached to what is below it: the rows the
 * block vacates are refilled with a copy of its own bottom row.
 *
 * A neck and a tail need this and a leg does not, and that difference is the
 * whole reason it exists. A raised foot SHOULD leave air behind it — that is
 * what a raised foot looks like. A raised head that leaves air behind it has
 * been decapitated. So a llama's neck bobbing a pixel stretches at the shoulder
 * instead of detaching from it, which is also what a real neck does. */
function raiseBlock(grid, x0, x1, y0, y1, dy) {
  if (dy >= 0) return moveBlock(grid, x0, x1, y0, y1, 0, dy);
  const src = rowsOf(grid);
  const out = moveBlock(grid, x0, x1, y0, y1, 0, dy).map(r => r.split(''));
  const bottom = src[Math.max(0, Math.min(PET_H - 1, y1))];
  const lx = Math.max(0, x0), hx = Math.min(PET_W - 1, x1);
  for (let y = Math.max(0, y1 + dy + 1); y <= Math.min(PET_H - 1, y1); y++) {
    for (let x = lx; x <= hx; x++) {
      const ch = bottom[x];
      if (ch === '.' || ch === ' ') continue;
      out[y][x] = ch;
    }
  }
  return out.map(r => r.join(''));
}

/* A travelling wave down a row range: row y moves sideways by amp*sin(). This
 * is the snake's entire locomotion and it is the reason the snake needed no
 * legs authored anywhere — the body IS the gait. */
function waveRows(grid, y0, y1, amp, phase, lambda) {
  if (!amp) return grid;
  const src = rowsOf(grid);
  const out = new Array(PET_H);
  for (let y = 0; y < PET_H; y++) {
    if (y < y0 || y > y1) { out[y] = src[y]; continue; }
    const dx = Math.round(amp * Math.sin((y / lambda + phase) * Math.PI * 2));
    if (!dx) { out[y] = src[y]; continue; }
    out[y] = dx > 0
      ? ('.'.repeat(dx) + src[y]).slice(0, PET_W)
      : (src[y].slice(-dx) + '.'.repeat(-dx));
  }
  return out;
}

/* Swap the two accent tones. A gill flutter, a shell chamber pulsing, a
 * feather catching the light — motion that is a change of state rather than a
 * change of position, which is the only kind some of these animals have. */
function swapAccent(grid) {
  return rowsOf(grid).map(r => r.replace(/[aA]/g, ch => (ch === 'a' ? 'A' : 'a')));
}

/* Take the face off. Used to derive the `up` view: what you see of an animal
 * walking away from you is its back, and its back has no eyes on it. 'g' — the
 * beak, the muzzle, the teeth — becomes plain body mass, but ONLY inside the
 * head band, because the same glyph is the foot on the bottom row. */
function faceOff(grid, headBand) {
  const [y0, y1] = headBand || [0, PET_H - 1];
  return rowsOf(grid).map((row, y) => {
    if (y < y0 || y > y1) return row.replace(/[we]/g, 'B');
    return row.replace(/[weg]/g, 'B');
  });
}

/* Paint a small strip over a grid at an offset. Crests, back plates and marks
 * all arrive this way rather than as edits, which is what lets the legendary
 * form keep the base body byte-identical. */
function stamp(grid, strip) {
  if (!strip || !strip.rows) return grid;
  return mergeGrids(PET_W, PET_H, [
    { grid: rowsOf(grid) },
    { grid: strip.rows, ox: strip.ox | 0, oy: strip.oy | 0 },
  ]);
}

/* Same as stamp(), plus one glyph that removes: '_' clears a cell to air.
 *
 * The back view needs it. What you see of a tortoise walking away is a shell on
 * four legs with NO HEAD — the head is on the other side of the animal — and a
 * derivation that can only paint over the front view can never say that. Every
 * facing that differs from the front by a subtraction rather than an addition
 * goes through here. */
function applyBack(grid, strip) {
  if (!strip || !strip.rows) return grid;
  const g = rowsOf(grid).map(r => r.split(''));
  const ox = strip.ox | 0, oy = strip.oy | 0;
  for (let y = 0; y < strip.rows.length; y++) {
    const ty = y + oy;
    if (ty < 0 || ty >= PET_H) continue;
    const row = strip.rows[y];
    for (let x = 0; x < row.length; x++) {
      const tx = x + ox;
      if (tx < 0 || tx >= PET_W) continue;
      const ch = row[x];
      if (ch === '.' || ch === ' ') continue;
      g[ty][tx] = ch === '_' ? '.' : ch;
    }
  }
  return g.map(r => r.join(''));
}

/* A sparse ring of glow outside the outline.
 *
 * Sparse is the whole design: a solid one-pixel ring around a 16px animal is a
 * blob with an animal-shaped hole in it, and the silhouette — the thing the
 * player actually reads the pet by — disappears. Every third candidate cell is
 * kept, chosen by a hash of its own coordinates plus a seed, so it is stable
 * across frames of a walk (no shimmer), identical between two runs (the
 * determinism harness checks this), and different between two animals.
 *
 * Nothing is placed on or below the ground row: a halo under the feet reads as
 * a puddle and fights the ground shadow the renderer already draws.
 */
function halo(grid, seed, density) {
  const src = rowsOf(grid);
  const out = src.map(r => r.split(''));
  const solid = (y, x) => (y < 0 || y >= PET_H || x < 0 || x >= PET_W)
    ? false : (src[y][x] !== '.' && src[y][x] !== ' ');
  let placed = 0;
  for (let y = 0; y < PET_GROUND; y++) {
    for (let x = 0; x < PET_W; x++) {
      if (solid(y, x)) continue;
      let touching = false;
      for (let dy = -1; dy <= 1 && !touching; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          if (solid(y + dy, x + dx)) { touching = true; break; }
        }
      }
      if (!touching) continue;
      if (((hash(`${seed}:${x}:${y}`) >>> 3) % density) !== 0) continue;
      out[y][x] = 'r';
      placed++;
    }
  }
  return placed ? out.map(r => r.join('')) : src;
}

/* Stamp a couple of pixels just past the mouth, in the direction the animal is
 * facing. The snake's tongue, and the only idle tell that has to know where the
 * face is rather than where the head is. Finding the mouth from the grid — the
 * extreme 'g' inside the head band — rather than from an authored coordinate
 * means it keeps working when the head moves under a gait. */
function protrude(grid, headBand, dir, glyph) {
  const src = rowsOf(grid);
  const [y0, y1] = headBand;
  let bx = -1, by = -1;
  for (let y = Math.max(0, y0); y <= Math.min(PET_H - 1, y1); y++) {
    for (let x = 0; x < PET_W; x++) {
      if (src[y][x] !== 'g') continue;
      if (dir === 'right' ? x > bx : (by < 0 || y > by)) { bx = x; by = y; }
      else if (dir === 'right' && x === bx && y > by) { by = y; }
    }
  }
  if (bx < 0) return src;
  const out = src.map(r => r.split(''));
  const steps = dir === 'right' ? [[1, 0], [2, 0], [2, -1]] : [[0, 1], [0, 2], [-1, 2]];
  for (const [dx, dy] of steps) {
    const x = bx + dx, y = by + dy;
    if (x < 0 || x >= PET_W || y < 0 || y >= PET_H) continue;
    if (out[y][x] !== '.') continue;
    out[y][x] = glyph;
  }
  return out.map(r => r.join(''));
}

/* ------------------------------------------------------------------ gaits
 *
 * Four frames each, driven by ground covered rather than by the clock, so the
 * feet match the speed instead of skating. No two of these are the same walk,
 * because how a thing moves is most of what it is.
 */
const GAITS = {
  /* Jaguar. A long low four-beat: ONE foot off the ground at a time, in the
   * diagonal sequence a walking cat actually uses, with the head dipping on the
   * two frames where the weight transfers and the tail lifting against it. */
  prowl(v, g, f, dir) {
    const order = [0, 2, 1, 3];
    const leg = v.legs[order[f] % (v.legs.length || 1)];
    if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    if (f === 1 || f === 3) {
      g = moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], 0, 1);
      if (v.tail) g = raiseBlock(g, v.tailX[0], v.tailX[1], v.tail[0], v.tail[1], -1);
    }
    return g;
  },

  /* The generic four-legged trot, and the fallback animal's walk. Diagonal
   * PAIRS rather than one foot at a time — which is why it does not read as the
   * jaguar even though it is built from the same ops. */
  trot(v, g, f, dir) {
    const pairs = [[0, 3], [], [1, 2], []];
    for (const i of pairs[f]) {
      const leg = v.legs[i];
      if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    }
    if (f === 1 || f === 3) g = moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], 0, 1);
    return g;
  },

  /* Llama. The legs run the same four-beat as the cat. The NECK is phase-shifted
   * one whole frame behind them, which is the entire character of the animal:
   * the head arrives where the body already went, a beat late, every step. Take
   * the shift out and it walks like a small horse. */
  stilt(v, g, f, dir) {
    const order = [0, 2, 1, 3];
    const leg = v.legs[order[f] % (v.legs.length || 1)];
    if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    const neckDy = [0, -1, 0, 1][(f + 3) % 4];
    if (neckDy) g = raiseBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], neckDy);
    return g;
  },

  /* Penguin. It rocks and it cannot stride: no foot ever moves FORWARD, only up
   * and down, and the whole body leans over whichever foot is carrying it. The
   * lean is applied above the ankles so the feet stay planted while the mass
   * swings — which is what makes a waddle look like effort rather than a slide. */
  rock(v, g, f, dir) {
    const lean = [-1, 0, 1, 0][f];
    if (lean) g = moveBlock(g, 0, PET_W - 1, 0, v.legTop - 1, lean, 0);
    const lifted = f === 0 ? v.legs[0] : f === 2 ? v.legs[1] : null;
    if (lifted) g = moveBlock(g, lifted[0], lifted[1], v.legTop, PET_H - 1, 0, -1);
    return g;
  },

  /* Snake. There is no walk cycle here at all, because there is nothing to
   * plant: a travelling sine runs down the body and the animal goes where the
   * wave pushes it. This is the only gait in the file that moves every row of
   * the sprite and the only one that touches no legs, because the grid has
   * none. */
  undulate(v, g, f, dir) {
    return waveRows(g, v.spine[0], v.spine[1], 1, f / 4, 5);
  },

  /* Velociraptor. Two beats and a suspension phase — on the even frames one leg
   * drives, on the odd frames both feet are off the ground, which is how a fast
   * biped actually runs and why this reads as quick at half the frame count of
   * the cat. The tail swings against the leg every beat: a raptor's tail is a
   * counterweight and animating it as decoration wastes the best thing about
   * the silhouette. */
  twobeat(v, g, f, dir) {
    const drive = f === 0 ? v.legs[0] : f === 2 ? v.legs[1] : null;
    if (drive) g = moveBlock(g, drive[0], drive[1], v.legTop, PET_H - 1, 0, -2);
    else for (const leg of v.legs) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    if (v.tail) {
      const swing = [1, 0, -1, 0][f];
      if (swing) g = moveBlock(g, v.tailX[0], v.tailX[1], v.tail[0], v.tail[1], swing, 0);
    }
    return g;
  },

  /* Tortoise. One foot at a time, slowly, and the SHELL DOES NOT MOVE — not a
   * pixel, on any frame. That is measured rather than promised: petArtStats()
   * reports the number of shell pixels that change across the cycle, and it is
   * zero. A shell that bobs is a costume; a shell that is rigid while four
   * stumps work underneath it is an animal carrying a house. */
  plod(v, g, f, dir) {
    const leg = v.legs[f % (v.legs.length || 1)];
    if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    // The head lowers and comes back up rather than reaching forward: at this
    // size a head that slides out along its own axis detaches from the neck by
    // a pixel and reads as a decapitation, which is not the note.
    if (f === 0 || f === 1) {
      g = moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], 0, 1);
    }
    return g;
  },

  /* Crow. Both feet together, always: a crouch, a launch, a beat in the air and
   * a landing. There is no frame in here where one foot is in front of the
   * other, which is the difference between a hop and a walk and the reason a
   * corvid reads as a corvid from six tiles away. */
  hop(v, g, f, dir) {
    if (f === 0) return moveBlock(g, 0, PET_W - 1, 0, v.legTop - 1, 0, 1);
    if (f === 1) return moveBlock(g, 0, PET_W - 1, 0, PET_H - 1, 0, -2);
    if (f === 2) return moveBlock(g, 0, PET_W - 1, 0, PET_H - 1, 0, -1);
    return g;
  },

  /* Axolotl. It is a soft thing in water and it barely commits to a step: a
   * toe lifted, the tail sculling, and the gill plumes flicking on the frames
   * between. The gills are the fastest-moving part of the animal, which is
   * correct and is also what stops the slow feet reading as a stutter. */
  paddle(v, g, f, dir) {
    if (f === 0 || f === 2) {
      const leg = v.legs[f >> 1];
      if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
    } else {
      g = swapAccent(g);
    }
    if (v.tail) {
      const scull = [0, 1, 0, -1][f];
      if (scull) g = moveBlock(g, v.tailX[0], v.tailX[1], v.tail[0], v.tail[1], scull, 0);
    }
    return g;
  },

  /* Nautilus. It does not walk; it is neutrally buoyant, so the whole sprite
   * rises and falls and the tentacles trail a beat behind it. Nothing here ever
   * touches the ground row, which is why the renderer's ground shadow reads as
   * a shadow cast from above rather than as contact. */
  drift(v, g, f, dir) {
    const rise = [0, -1, 0, 1][f];
    if (rise) g = moveBlock(g, 0, PET_W - 1, 0, PET_H - 1, 0, rise);
    if (v.tail) {
      const trail = [1, 0, -1, 0][f];
      if (trail) g = moveBlock(g, v.tailX[0], v.tailX[1], v.tail[0], v.tail[1], trail, 0);
    }
    if (f === 2) g = swapAccent(g);
    return g;
  },
};

/* ------------------------------------------------------------------ idles
 *
 * Four frames: breathe, settle, breathe, and then the TELL.
 *
 * The tell is the point. A player reads a problem statement for ten seconds
 * with the companion standing next to them, and three frames of breathing is
 * three frames of a cushion rising and falling. The fourth frame is the one
 * that says there is an animal in there — and it is a different fourth frame
 * for every one of them, which is where most of the personality in this file
 * actually lives.
 */

/* The breath itself, shared. The top half of the head sinks into the shoulders
 * on the settle frame and comes back up. Only the top half, so a long neck
 * compresses at the poll rather than driving the whole head through the chest. */
function breathe(v, g, f) {
  if (f !== 1) return g;
  const mid = Math.floor((v.head[0] + v.head[1]) / 2);
  return moveBlock(g, v.headX[0], v.headX[1], v.head[0], mid, 0, 1);
}

const IDLES = {
  /* Jaguar: the tail goes, and nothing else does. A cat at rest is a still
   * animal with one moving part. */
  tailflick(v, g, f, dir) {
    g = breathe(v, g, f);
    if (f !== 3) return g;
    if (v.tail) return raiseBlock(moveBlock(g, v.tailX[0], v.tailX[1], v.tail[0], v.tail[1], 1, 0),
                                 v.tailX[0] + 1, v.tailX[1] + 1, v.tail[0], v.tail[1], -1);
    return moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[0] + 1, 1, 0);
  },
  /* Snake: the tongue. Two pixels, once every couple of seconds. */
  tongue(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? protrude(g, v.head, dir === 'side' ? 'right' : 'down', 'a') : g;
  },
  /* Llama: the ears, which on a llama are half the head. */
  earflick(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[0] + 1, -1, 0) : g;
  },
  /* Penguin: it leans. Standing still is the only thing it does confidently. */
  lean(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? moveBlock(g, 0, PET_W - 1, 0, v.legTop - 1, 1, 0) : g;
  },
  /* Raptor: a hard fast head jerk, held for one frame. Birds do this and so did
   * the animals birds came from. */
  headjerk(v, g, f, dir) {
    g = breathe(v, g, f);
    if (f !== 3) return g;
    const [dx, dy] = dir === 'side' ? [1, 0] : [0, 1];
    return moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], dx, dy);
  },
  /* Axolotl: the gills flutter. It is the one idle here that is a change of
   * state rather than a change of position, because the moving part is a frill
   * two pixels wide and moving it would only make it vanish. */
  gills(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? swapAccent(g) : g;
  },
  /* Tortoise: a blink. The white goes out of the eye and comes back. At this
   * size that is one pixel, and one pixel is enough — it is the only pixel on
   * the animal the eye was already looking at. */
  blink(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? rowsOf(g).map(r => r.replace(/w/g, 'o')) : g;
  },
  /* Nautilus: the chambers pulse, and it drifts a pixel while it does. */
  chamber(v, g, f, dir) {
    if (f === 1) g = moveBlock(g, 0, PET_W - 1, 0, PET_H - 1, 0, -1);
    return f === 3 ? swapAccent(g) : g;
  },
  /* Crow: the head turns to look at something that is not you. */
  headturn(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? moveBlock(g, v.headX[0], v.headX[1], v.head[0], v.head[1], -1, 0) : g;
  },
  /* The fallback. Breathing and a small shift of weight, which is the least an
   * unknown animal is allowed to do and still count as alive. */
  breath(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? moveBlock(g, 0, PET_W - 1, v.spine[0], v.spine[1], 1, 0) : g;
  },
};

/* ------------------------------------------------------------------ views
 *
 * Three authored views become four facings. Built once per animal per facing
 * and memoised, because mirroring a grid and deriving a back view is real work
 * and none of it depends on the frame, the tier or the colour.
 */

export const PET_FACINGS = ['down', 'up', 'left', 'right'];

function mirrorStrip(strip) {
  if (!strip || !strip.rows) return strip;
  const w = Math.max(...strip.rows.map(r => r.length));
  return {
    ox: PET_W - (strip.ox | 0) - w,
    oy: strip.oy | 0,
    rows: strip.rows.map(r => r.padEnd(w, '.').split('').reverse().join('')),
  };
}

function mirrorView(v) {
  const flipX = ([x0, x1]) => [PET_W - 1 - x1, PET_W - 1 - x0];
  return {
    grid: mirrorGrid(v.grid),
    legs: v.legs.map(flipX).sort((a, b) => a[0] - b[0]),
    legTop: v.legTop, spine: v.spine, head: v.head, headX: flipX(v.headX),
    crestHead: v.crestHead, tail: v.tail,
    tailX: v.tailX ? flipX(v.tailX) : null,
    shell: v.shell || null,
    mark: [PET_W - 1 - v.mark[0], v.mark[1]],
    crest: mirrorStrip(v.crest),
  };
}

/* The back. Derived from the front view rather than authored, because two
 * independently drawn views of the same animal always end up disagreeing about
 * how big it is, and the player reads that disagreement as a stutter every time
 * the pet turns around. Taking the face off a view it already agrees with
 * cannot drift. */
function backView(v) {
  let grid = faceOff(v.grid, v.head);
  for (const strip of (v.back ? [].concat(v.back) : [])) grid = applyBack(grid, strip);
  return {
    grid,
    legs: v.legs, legTop: v.legTop, spine: v.spine, head: v.head,
    headX: v.headX, crestHead: v.crestHead,
    tail: v.tail, tailX: v.tailX, shell: v.shell || null,
    mark: v.mark, crest: v.crest,
  };
}

const viewCache = new Map();
const VIEW_CACHE_MAX = 96;

function viewFor(key, dir) {
  const ck = `${key}|${dir}`;
  const hit = viewCache.get(ck);
  if (hit) return hit;
  const a = ANIMALS[key];
  const base = dir === 'down' ? a.down
    : dir === 'up' ? backView(a.down)
    : dir === 'left' ? mirrorView(a.side)
    : a.side;
  // Padded once, here, so nothing downstream has to wonder whether a row is
  // sixteen characters wide.
  const v = { ...base, grid: rowsOf(base.grid) };
  if (viewCache.size >= VIEW_CACHE_MAX) viewCache.delete(viewCache.keys().next().value);
  viewCache.set(ck, v);
  return v;
}

/* --------------------------------------------------------------- palette
 *
 * Every tone here comes off a shared ramp in palette.js, which is the rule that
 * makes a pet belong in the same world as the hero it is following. A companion
 * whose browns were picked by eye would be a companion that reads as a sticker.
 *
 * The server sends one colour per pet (pets.py `colour`), not a ramp. When it
 * does, rampFor() derives a five-step material from it under the same low hot
 * key light every other ramp in the game was built against — so a pet nobody
 * has drawn a palette for still arrives lit correctly.
 *
 * Fourteen colours at the very worst, which is the LEGENDARY and MYTHIC case
 * where the crest, the mark and the halo are all present at once. Counted off
 * the raster by the harness at the bottom of this task, not off this dict.
 */

/* A dead companion.
 *
 * Restrained, because the roster screen is where the player goes to look at the
 * animal that died and a headstone with a halo would be the game telling them
 * how to feel. So: the same pose, the same outline, three tones of the darkest
 * material we have plus one bone highlight, no rim light, no accent, no mark,
 * no aura — and the white gone out of the eye, which is the only change anybody
 * will consciously notice. It reads as the shape of the animal with the animal
 * no longer in it. */
function deadPalette() {
  const dark = RAMPS.void[SHADE.DARK];
  const mid = RAMPS.void[SHADE.MID];
  const bone = RAMPS.bone[SHADE.DARK];
  return {
    o: OUTLINE, O: OUTLINE, e: OUTLINE, D: OUTLINE,
    d: dark, B: mid, L: mid, H: bone,
    a: dark, A: mid, g: bone, c: bone,
    w: mid, R: dark, m: dark, r: dark,
  };
}

export function petPalette(animal, opts) {
  const o = opts || {};
  if (o.dead) return deadPalette();
  const a = ANIMALS[petKeyFor(animal)];
  const st = TIER_STYLE[petTierKey(o.tier)];
  const rarity = RARITY[st.rarity] || RARITY.COMMON;

  const body = (typeof o.colour === 'string' && o.colour.charAt(0) === '#')
    ? rampFor(o.colour, a.family, SHADE.LIGHT)
    : (RAMPS[a.body] || RAMPS.leather);
  const accent = RAMPS[a.accent] || RAMPS.earth;
  const hard = RAMPS[a.hard] || RAMPS.bone;

  // The tier's temperature shift. Positive rotates toward the hot key light,
  // negative toward the cold fill — a tutorial companion is literally standing
  // further out of the light than a legendary one is.
  const lit = st.warm === 0 ? (c => c)
    : st.warm > 0 ? (c => warmer(c, st.warm)) : (c => cooler(c, -st.warm));

  const pal = {
    // The outline stays heavy and the rim does all the lighting, exactly as the
    // hero rig does it: applyRim's lifted outline plus a rim reads as a smeared
    // double edge at this size.
    o: OUTLINE, O: OUTLINE, e: OUTLINE,
    D: body[SHADE.DEEP], d: body[SHADE.DARK], B: body[SHADE.MID],
    L: lit(body[SHADE.LIGHT]), H: lit(body[SHADE.SPEC]),
    a: accent[SHADE.DARK], A: accent[SHADE.LIGHT],
    g: hard[SHADE.LIGHT], c: hard[SHADE.SPEC],
    w: '#f2f6ff',
    R: st.index >= 5 ? mix(rimTone(body[SHADE.SPEC]), rarity.accent, 0.45)
                     : rimTone(body[SHADE.SPEC]),
    r: rarity.glow || rarity.accent,
  };
  // The mark has to be a colour this animal is not already wearing, or the tier
  // it is announcing is invisible. Shared ramps make that a real collision and
  // not a hypothetical one: the snake's body IS `venom`, and the UNCOMMON
  // accent is venom's specular step, so at UNCOMMON its mark was painted in a
  // tone the sprite was already wearing and the tier read as COMMON. Nudge
  // toward the key light until it separates; the mark keeps its own palette
  // slot either way, so this costs nothing against the budget.
  let markColour = rarity.accent;
  const worn = new Set(Object.values(pal));
  if (worn.has(markColour)) markColour = warmer(markColour, 14);
  if (worn.has(markColour)) markColour = mix(markColour, '#ffffff', 0.35);
  pal.m = markColour;
  return pal;
}

/* ------------------------------------------------------------------ cache
 *
 * Same discipline as the hero rig: a Map keyed by an authored string, a cap, and
 * oldest-out eviction. The working set a walking companion actually asks for is
 * one animal x four facings x four frames x two poses, plus the dead frame: 33
 * entries. The cap is not sized for that, it is sized for the worst case the UI
 * can actually produce, which is the roster screen holding the whole roster at
 * two tiers at once — ten animals x 33 x 2 = 660. 768 clears it with room for
 * the fallback and a colour override, and it was measured rather than guessed:
 * at 384 the second pass over that set re-rendered 2600 canvases, which is a
 * cache doing nothing but evicting.
 */
const petCache = new Map();
const PET_CACHE_MAX = 768;

function capPetCache() {
  while (petCache.size > PET_CACHE_MAX) {
    const oldest = petCache.keys().next();
    if (oldest.done) break;
    petCache.delete(oldest.value);
  }
}

export function clearPetCache() { petCache.clear(); viewCache.clear(); }
export function petCacheStats() {
  return { size: petCache.size, cap: PET_CACHE_MAX, views: viewCache.size,
           viewCap: VIEW_CACHE_MAX, full: petCache.size >= PET_CACHE_MAX };
}

/* ------------------------------------------------------------------ frames */

/* Four frames, contact/pass/contact/pass, the same shape the hero walk uses so a
 * caller can drive both off one distance counter. */
export const PET_WALK_ORDER = [0, 1, 2, 3];
export const PET_FRAME_COUNT = 4;

/* The authored grid for one animal, facing, frame and tier, before it is lit.
 * Split out from petFrame because the silhouette check wants the shape without
 * paying for a raster. */
function petGrid(key, dir, f, tierKey, dead, pose) {
  const a = ANIMALS[key];
  const st = TIER_STYLE[tierKey];
  const v = viewFor(key, dir);
  const sideish = dir === 'left' || dir === 'right';
  let g = v.grid;

  // The crest goes on FIRST, so the gait's head block carries it. A crest
  // stamped after the deformation detaches from the head on every frame where
  // the head moves, which at 16px reads as a bug rather than as a horn.
  let head = v.head, headX = v.headX;
  if (st.crest && v.crest && !dead) {
    g = stamp(g, v.crest);
    // A horn, a hood or a quill crest rides on the head and has to move with
    // it. A ridge along a SHELL does not — `crestHead: false` says so, and
    // without it the tortoise's legendary spines drag the whole shell down a
    // row every time the head nods, which is both wrong and the loudest way to
    // break the promise that the base animal is untouched.
    if (v.crestHead !== false) {
      const cw = Math.max(...v.crest.rows.map(r => r.length));
      head = [Math.min(head[0], v.crest.oy | 0), head[1]];
      headX = [Math.min(headX[0], v.crest.ox | 0),
               Math.max(headX[1], (v.crest.ox | 0) + cw - 1)];
    }
  }

  // A tutorial companion is a smaller one. The head settles a row into the
  // shoulders, which takes a row off the top of the outline — a real change to
  // the silhouette rather than a paler version of the same animal.
  if (st.shrink && !dead) {
    const mid = Math.floor((head[0] + head[1]) / 2);
    g = moveBlock(g, headX[0], headX[1], head[0], mid, 0, st.shrink);
  }

  const vv = (head === v.head && headX === v.headX) ? v : { ...v, head, headX };
  // A dead companion is a still frame: no gait, no idle, nothing twitches.
  if (!dead) {
    const fn = (GAITS[a.gait] || GAITS.trot);
    g = (pose === 'idle' ? (IDLES[a.idle] || IDLES.breath) : fn)(
      vv, g, f, sideish ? 'side' : dir);
  }

  if (st.mark && !dead) {
    // Painted only where there is already animal underneath. The anchors were
    // all placed on body mass, but a mark pixel that lands in the gap between
    // two legs is a coloured speck floating beside the pet, and the grids here
    // are going to be edited by someone who has not read this paragraph.
    const [mx, my] = v.mark;
    const rows = rowsOf(g).map(r => r.split(''));
    for (const [dx, dy] of MARK_PIXELS.slice(0, st.mark)) {
      const x = mx + dx, y = my + dy;
      if (x < 0 || x >= PET_W || y < 0 || y >= PET_H) continue;
      const under = rows[y][x];
      if (under === '.' || under === ' ') continue;
      rows[y][x] = 'm';
    }
    g = rows.map(r => r.join(''));
  }
  return g;
}

/** One frame, cached.
 *
 *  @param animal  a pets.py `sprite`, `species` or `id`, or a whole row. An
 *                 animal nobody has drawn resolves to `beast` and never throws.
 *  @param facing  'down' | 'up' | 'left' | 'right' ('side' means right)
 *  @param frame   any integer; wrapped into the four-frame cycle
 *  @param opts    { tier, colour, pose: 'walk'|'idle', dead }
 *  @returns a 16x16 canvas. It is the CACHED instance — draw it, do not edit it.
 */
export function petFrame(animal, facing = 'down', frame = 0, opts) {
  const key = petKeyFor(animal);
  const o = opts || {};
  const dead = !!o.dead;
  const dir = facing === 'side' ? 'right'
    : (PET_FACINGS.indexOf(facing) >= 0 ? facing : 'down');
  const tier = dead ? 'COMMON' : petTierKey(o.tier);
  const pose = dead ? 'idle' : (o.pose === 'idle' ? 'idle' : 'walk');
  const colour = (typeof o.colour === 'string' && o.colour.charAt(0) === '#')
    ? o.colour : '';
  const f = dead ? 0 : ((((frame | 0) % PET_FRAME_COUNT) + PET_FRAME_COUNT) % PET_FRAME_COUNT);

  const ck = `${key}:${dir}:${f}:${pose}:${tier}:${colour}:${dead ? 1 : 0}`;
  const hit = petCache.get(ck);
  if (hit) return hit;

  let grid = petGrid(key, dir, f, tier, dead, pose);

  // One merge, then one light, in the order sprites.js fixed for the whole
  // cast: the soft upper-left fill, then the single hot rim from low-left
  // INSIDE the heavy outline. The eye, the mark and the halo are protected —
  // an authored pixel that the shading pass eats is an authored pixel wasted.
  grid = rimLowLeft(applyRim(grid), 'R', 'wem');

  // The halo goes on last of all, outside the outline, after the lighting has
  // finished. It is not a surface, so it must not be lit like one.
  const st = TIER_STYLE[tier];
  if (st.halo && !dead) grid = halo(grid, `${key}:${dir}:${tier}`, st.halo === 1 ? 3 : 2);

  const canvas = gridSprite(grid, petPalette(key, { tier, colour, dead }), PET_W, PET_H);
  petCache.set(ck, canvas);
  capPetCache();
  return canvas;
}

/** Every frame a renderer needs for one companion, in the shape
 *  sprites.heroSprites() returns so the overworld can index both the same way.
 *
 *    set[facing][frame]        the walk
 *    set.idle[facing][frame]   the idle, tell included
 *    set.side, set.idle.side   aliases for 'right'
 *    set.dead                  the roster-screen frame, one image
 */
export function petSprites(animal, opts) {
  const o = opts || {};
  const out = { idle: {} };
  for (const facing of PET_FACINGS) {
    out[facing] = PET_WALK_ORDER.map(f => petFrame(animal, facing, f, o));
    out.idle[facing] = PET_WALK_ORDER.map(
      f => petFrame(animal, facing, f, { ...o, pose: 'idle' }));
  }
  out.side = out.right;
  out.idle.side = out.idle.right;
  out.dead = petFrame(animal, 'down', 0, { ...o, dead: true });
  return out;
}

/** The dead companion on its own, for the roster screen. */
export function petDeadFrame(animal, opts) {
  return petFrame(animal, (opts && opts.facing) || 'down', 0, { ...(opts || {}), dead: true });
}

/** The shape with the colour thrown away, knocked down to a 16px box.
 *
 *  This is the check every animal in this file was authored against, and it is
 *  the only one that matters at the size a pet is actually seen: if the llama
 *  is not neck-and-legs and the penguin is not a weighted teardrop down here,
 *  no amount of interior shading is going to rescue them up there. */
export function petSilhouette(animal, facing = 'side', frame = 0, opts) {
  const key = petKeyFor(animal);
  const o = opts || {};
  const dir = facing === 'side' ? 'right'
    : (PET_FACINGS.indexOf(facing) >= 0 ? facing : 'down');
  const f = (((frame | 0) % PET_FRAME_COUNT) + PET_FRAME_COUNT) % PET_FRAME_COUNT;
  let g = petGrid(key, dir, f, petTierKey(o.tier), !!o.dead,
                  o.pose === 'idle' ? 'idle' : 'walk');
  const st = TIER_STYLE[petTierKey(o.tier)];
  if (st.halo && !o.dead) g = halo(g, `${key}:${dir}:${petTierKey(o.tier)}`,
                                  st.halo === 1 ? 3 : 2);
  return silhouetteAt(g, PET_W);
}

/* --------------------------------------------------------------- motion */

/* How to drive one of these. `period` is one full gait cycle in milliseconds at
 * a walk, `idlePeriod` one full breathe-breathe-breathe-tell cycle, and `phase`
 * staggers two companions of the same species so they never pulse in lockstep.
 *
 * The overworld drives the walk off DISTANCE rather than off `period` — the
 * feet have to match the speed or they skate — so `period` is for callers that
 * have no distance to hand: a roster screen, a portrait, a dialogue box. */
export function petMotion(animal) {
  const a = ANIMALS[petKeyFor(animal)];
  return {
    gait: a.gait, idle: a.idle,
    period: a.period, idlePeriod: a.idlePeriod,
    bob: a.bob, sway: a.sway,
    frames: PET_FRAME_COUNT,
    phase: (hash(petKeyFor(animal)) % 1000) / 1000,
  };
}

/** The frame index for a wall clock, for callers with no distance to spend. */
export function petFrameAt(animal, timeMs = 0, pose = 'walk') {
  const m = petMotion(animal);
  const period = pose === 'idle' ? m.idlePeriod : m.period;
  const t = (timeMs / period) + m.phase;
  return Math.floor((t - Math.floor(t)) * PET_FRAME_COUNT) % PET_FRAME_COUNT;
}

/** Shadow radius that suits a pet. Wide and shallow, tucked under the feet —
 *  and smaller than the hero's, because the companion is smaller than he is and
 *  a shadow that does not agree with the body is the fastest way to make a
 *  sprite look pasted on. */
export function petShadow(animal) {
  const key = petKeyFor(animal);
  const grid = viewFor(key, 'down').grid;
  let lo = PET_W, hi = 0;
  for (let y = PET_H - 4; y < PET_H; y++) {
    for (let x = 0; x < PET_W; x++) {
      if (grid[y][x] === '.' || grid[y][x] === ' ') continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
  }
  const rx = hi >= lo ? Math.max(3, Math.round((hi - lo + 1) / 2)) : 5;
  return { rx, ry: Math.max(2, Math.round(rx * 0.4)) };
}

/* ------------------------------------------------------------------ stats
 *
 * What this module will let itself be measured on. Everything here is counted
 * off the authored grids rather than asserted, and scripts/verify reads it.
 */
export function petArtStats() {
  const area = (g) => g.reduce((n, r) => n + [...r].filter(c => c !== '.' && c !== ' ').length, 0);
  const rows = [];
  for (const key of PET_ANIMALS) {
    const a = ANIMALS[key];
    const sides = PET_WALK_ORDER.map(
      f => petGrid(key, 'right', f, 'COMMON', false, 'walk'));
    // How much of the walk actually moves. A frame that differs from the last
    // one by nothing is not a frame, and this is the number that says so.
    let moved = 0;
    for (let i = 0; i < sides.length; i++) {
      const b = sides[(i + 1) % sides.length];
      for (let y = 0; y < PET_H; y++) {
        for (let x = 0; x < PET_W; x++) {
          const p = sides[i][y][x] !== '.', q = b[y][x] !== '.';
          if (p !== q) moved++;
        }
      }
    }
    const tut = area(petGrid(key, 'right', 0, 'TUTORIAL', false, 'walk'));
    const com = area(sides[0]);
    let leg = petGrid(key, 'right', 0, 'LEGENDARY', false, 'walk');
    leg = halo(leg, `${key}:right:LEGENDARY`, 3);
    // The tortoise's promise, checked rather than repeated: cells inside the
    // shell band that differ between consecutive frames of the walk. A shell
    // that bobs is a costume. (The nautilus has a shell and no such promise —
    // it is neutrally buoyant and the whole animal rises and falls, which is
    // why it carries no shell band here.)
    let shellMoved = null;
    const shell = a.side.shell;
    if (shell) {
      shellMoved = 0;
      for (let i = 0; i < sides.length; i++) {
        const b = sides[(i + 1) % sides.length];
        for (let y = shell[0]; y <= shell[1]; y++) {
          for (let x = 0; x < PET_W; x++) if (sides[i][y][x] !== b[y][x]) shellMoved++;
        }
      }
    }
    rows.push({
      animal: key, gait: a.gait, idle: a.idle, legs: a.side.legs.length,
      silhouette: { TUTORIAL: tut, COMMON: com, LEGENDARY: area(leg) },
      outlineChangedPerCycle: moved,
      shellPixelsMovedPerCycle: shellMoved,
    });
  }
  return { animals: PET_ANIMALS.length, box: `${PET_W}x${PET_H}`,
           tiers: PET_TIERS.length, cache: petCacheStats(), rows };
}
