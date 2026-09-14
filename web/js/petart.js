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
 *   petRegaliaFor(idOrRow)                -> a worn object, resolved
 *   PET_ANIMALS / PET_REGALIA             -> what is authored
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
 *  2. One pixel grid. 16x16, integer scale, the same grain as the 16x24 field
 *     hero and the 16x16 terrain. That box was re-examined when the battle
 *     raster moved to 256x224 and it did not move, for a measured reason: the
 *     companion never appears on the battle stage, the FIELD hero is still
 *     16x24, and the overworld bottom-aligns a pet on a 16px tile. Beside that
 *     hero's 23 rows of ink the twelve carry 11 to 16, which is roughly half
 *     his height — an animal at a man's knee, which is where a companion goes.
 *  3. No Math.random and no Date.now on a draw path. Every variation in here is
 *     a hash of the inputs, so two runs of the same frame are the same bytes.
 *  4. No per-frame allocation in a hot loop. Frames are cached under a cap and
 *     evicted oldest-first, exactly as the hero rig does it.
 *  5. Merge, then light, once. mergeGrids -> liteAll -> applyRim -> rimLowLeft,
 *     borrowed from sprites.js rather than reimplemented, because a second
 *     lighting model is how a cast stops looking like a cast. liteAll() is not
 *     one: it is applyRim run a second time, on a second material, from the
 *     same lamp in the same direction.
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
 *   boar        a shoulder hump above the line of the back, and no neck at all
 *   octopus     a smooth bell over a ragged fan of arms, and no hard part on it
 *
 * Each is checked with colour discarded by petSilhouette().
 *
 * THE LAST TWO ARE NEW AND THEY ARE THE TWO THAT MATTERED MOST
 *
 * STUB is the animal the player walks the whole tutorial beside; it dies at the
 * first boss and comes back as BARROW, which is the same pig at LEGENDARY. The
 * MIMIC is the hidden twelfth. Between them that is the most-seen companion in
 * the game and the rarest one, and all three were being drawn by something
 * else: both boars landed on `beast`, the fallback whose own comment says it is
 * "deliberately no markings and no character", and the mimic aliased to
 * `nautilus`, which is the one cephalopod in the sea that is mostly shell. The
 * roster ships twelve companions and it now has twelve shapes.
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
 * VERIFYING THE ART
 *
 * Retake palette, silhouette, gait, fainted and worn-object measurements with
 * petArtStats(), scripts/verify/petroster.mjs and companion.mjs. The focused
 * petpolish.mjs sweeps all twelve body plans, seven tiers, four facings, both
 * poses and every worn object through the real raster. Its optional contact
 * sheets show native size beside an integer enlargement. Counts protect the
 * rendering contracts; the sheets and the game decide whether the art reads.
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
 *   d   authored occlusion: cheek, folded wing, belly and limb overlap. These
 *       anatomical shadows mirror with the animal; directional highlights do not.
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
  gait: 'prowl', idle: 'tailflick', fallen: 'fold',
  period: 640, idlePeriod: 2800, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '.oo.............',
      '.oBo.......o....',
      '..oBo.....oBooo.',
      '..oBo.....oBaBBo',
      '..oBo.....oBwBeo',
      '..oBooooooBBBBgo',
      '.oBBBBBBBBBBBBo.',
      '.oBaBBaBBdaBBBo.',
      '.oBBaBBBadBBdBo.',
      '.oBBBddBddBBBBo.',
      '.oBBoBBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.ogo.ogo..ogoogo',
    ],
    legs: [[1, 3], [5, 7], [10, 12], [13, 15]],
    legTop: 12, spine: [8, 11], head: [4, 7], headX: [10, 15],
    tail: [2, 6], tailX: [1, 4], mark: [4, 9],
    on: { throat: [11, 7], brow: [13, 5], back: [6, 8], leg: [11, 13] },
    crest: { ox: 9, oy: 2, rows: ['.ccc.', 'cccco', '.cco.'] },
  },
  down: {
    grid: [
      '................',
      '....oo....oo....',
      '....oBooooBo....',
      '....oBaBBaBo....',
      '...oBBwBBwBBo...',
      '...oBBeBBeBBo...',
      '....oBaggBBo....',
      '.....oBddBo.....',
      '....oBBBBBBo....',
      '...oBBaBBaBBo...',
      '...oBBdBBdBBo...',
      '...oBBBddBBBo...',
      '...oBBo..oBBo...',
      '...oBo....oBo...',
      '...oBo....oBo...',
      '...oggo..oggo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [1, 7], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 9],
    on: { throat: [7, 7], brow: [7, 3], back: [7, 10], leg: [4, 13] },
    crest: { ox: 4, oy: 0, rows: ['.c....c.', 'cccccccc', '.c.cc.c.'] },
    back: [{ ox: 11, oy: 4, rows: ['.oo.', 'oBBo', 'oBBo', 'oBBo', 'oBBo', 'oBBo', 'oBB.'] }],
  },
};

/* ---- python: a line. No legs anywhere in the grid, and none in the gait. --- */
ANIMALS.snake = {
  body: 'venom', accent: 'grass', hard: 'bone', family: 'organic',
  gait: 'undulate', idle: 'tongue', fallen: 'slack',
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
      '.oBBaBBoooBBggo.',
      'oBBaBBBddooBBoo.',
      'oBBdoooBBBBBBo..',
      '.oBBo..oBBBBo...',
      '..oBBooooBBoo...',
      '...ooBBBBBoo....',
      '.....oBBBo......',
      '......ooo.......',
      '................',
    ],
    legs: [], legTop: 16, spine: [7, 13], head: [4, 7], headX: [9, 15],
    tail: [8, 13], tailX: [0, 6], mark: [4, 9],
    on: { throat: [11, 8], brow: [11, 5], back: [4, 7], leg: null },
    crest: { ox: 9, oy: 2, rows: ['.cc..', 'cccc.', 'cc.c.'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '...oooooooooo...',
      '..oBBaBBBBaBBo..',
      '..oBBdooodBBBo..',
      '...oooBBBdooo...',
      '....oBBdBBBo....',
      '...oBBaBBaBBo...',
      '...oBBBddBBBo...',
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
    on: { throat: [7, 10], brow: [7, 10], back: [7, 4], leg: null },
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
  gait: 'stilt', idle: 'earflick', fallen: 'fold',
  period: 760, idlePeriod: 3000, bob: 1, sway: 0,
  side: {
    grid: [
      '...........o.o..',
      '...........oBo..',
      '..........oBaBo.',
      '..........oBwBeo',
      '..........oBBago',
      '...........oBBo.',
      '...........oBBo.',
      '..ooo......oBBo.',
      '.oBBBoooooooBBo.',
      '.oBBBBBBBBBBBBo.',
      '.oBaBBaBBaBBBBo.',
      '..oBBddBddBBBo..',
      '.oBo.oBo.oBooBo.',
      '.oBo.oBo.oBooBo.',
      '.oBo.oBo.oBooBo.',
      '.ogo.ogo.ogoogo.',
    ],
    legs: [[1, 3], [5, 7], [9, 11], [12, 14]],
    legTop: 12, spine: [8, 11], head: [0, 5], headX: [10, 15],
    tail: [7, 9], tailX: [1, 4], mark: [4, 9],
    on: { throat: [12, 6], brow: [12, 2], back: [6, 9], leg: [13, 13] },
    crest: { ox: 9, oy: 0, rows: ['..cc.', '.ccc.', 'cc.c.'] },
  },
  down: {
    grid: [
      '.....o....o.....',
      '.....oB..Bo.....',
      '.....oBBBBo.....',
      '.....owBBwo.....',
      '.....oeBBeo.....',
      '.....oBaaBo.....',
      '......oBBo......',
      '......oBBo......',
      '.....oBBBBo.....',
      '....oBBBBBBo....',
      '...oBBaBBaBBo...',
      '...oBBBddBBBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...ogo.oo.ogo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [0, 5], headX: [5, 10],
    tail: null, tailX: null, mark: [5, 9],
    on: { throat: [7, 7], brow: [7, 2], back: [7, 10], leg: [4, 13] },
    crest: { ox: 5, oy: 0, rows: ['c....c', 'cc..cc', '.c..c.'] },
    back: [{ ox: 11, oy: 6, rows: ['.oo.', 'oBBo', 'oBBo', 'oBB.'] }],
  },
};

/* ---- penguin: weighted teardrop. It rocks. It cannot stride. ---- */
ANIMALS.penguin = {
  body: 'gunmetal', accent: 'bone', hard: 'bronze', family: 'metal',
  gait: 'rock', idle: 'lean', fallen: 'topple',
  period: 820, idlePeriod: 2600, bob: 1, sway: 1,
  side: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....oBwBeo.....',
      '.....oBAAggo....',
      '....oBBAAAAo....',
      '....oBdAAAAo....',
      '...oBBdAAAAAo...',
      '..oBBBdAAAAAo...',
      '..oBBodAAAAAo...',
      '...oodBAAAAo....',
      '...oBBBAAAo.....',
      '....oBBdBo......',
      '....oggoggggo...',
      '....oooooooo....',
    ],
    legs: [[4, 6], [7, 12]],
    legTop: 14, spine: [6, 13], head: [2, 5], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 11],
    on: { throat: [7, 6], brow: [7, 3], back: [5, 8], leg: [5, 14] },
    crest: { ox: 4, oy: 0, rows: ['..cc..', '.cccc.', 'cc..cc'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '......oooo......',
      '.....oBBBBo.....',
      '.....owBBwo.....',
      '.....oAggAo.....',
      '....oBAAAABo....',
      '...oBBAAAABBo...',
      '..oBdAAAAAAdBo..',
      '..oBdAAAAAAdBo..',
      '..oBdAAAAAAdBo..',
      '..ooBAAAAAABoo..',
      '...oBBAAAABBo...',
      '...oBBAAAABBo...',
      '...ogggoogggo...',
      '....ooo..ooo....',
    ],
    legs: [[3, 6], [9, 12]],
    legTop: 14, spine: [6, 13], head: [2, 5], headX: [4, 11],
    tail: null, tailX: null, mark: [4, 11],
    on: { throat: [7, 6], brow: [7, 3], back: [7, 7], leg: [5, 14] },
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
  gait: 'twobeat', idle: 'headjerk', fallen: 'fold',
  period: 420, idlePeriod: 2200, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '............ooo.',
      '...........oBBwo',
      '...........oBweo',
      '..........oBBggo',
      '.oo......oBBBoo.',
      '.oBoo...oBaBBo..',
      '..oBBooBBBBBBo..',
      '...oBBBBBdaBBo..',
      '....oBBBdBBBo...',
      '....oBBdaBBBo...',
      '....oBoooBBBo...',
      '...oBo....oBBo..',
      '...oBo....oBBo..',
      '..oBBo.....oBo..',
      '..oggo.....oggo.',
    ],
    legs: [[2, 4], [10, 13]],
    legTop: 11, spine: [7, 10], head: [1, 4], headX: [9, 15],
    tail: [5, 6], tailX: [1, 6], mark: [6, 8],
    on: { throat: [11, 5], brow: [12, 2], back: [8, 7], leg: [11, 12] },
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
      '....oBaBBaBo....',
      '...oBBdBBdBBo...',
      '...ooBdBBdBoo...',
      '....oBBooBBo....',
      '...oBo....oBo...',
      '...oBo....oBo...',
      '..oBBo....oBBo..',
      '..oggo....oggo..',
    ],
    legs: [[2, 5], [10, 13]],
    legTop: 11, spine: [7, 10], head: [2, 6], headX: [4, 11],
    tail: null, tailX: null, mark: [5, 8],
    on: { throat: [7, 6], brow: [7, 3], back: [7, 9], leg: [4, 12] },
    crest: { ox: 5, oy: 0, rows: ['.cccc.', 'cc..cc', '.c..c.'] },
    back: [{ ox: 5, oy: 7, rows: ['.oBBBB.', 'oBBBBBo', 'oBBBBBo'] },
           { ox: 5, oy: 12, rows: ['oBBBBo', 'oBBBBo', '.oooo.'] }],
  },
};

/* ---- axolotl: a wide soft head wearing gill plumes. Barely lifts a foot. --- */
ANIMALS.axolotl = {
  body: 'skin', accent: 'blood', hard: 'bone', family: 'organic',
  gait: 'paddle', idle: 'gills', fallen: 'fold',
  period: 700, idlePeriod: 2000, bob: 1, sway: 1,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '.........a..a...',
      '..........Aa....',
      '..oo....aAAa....',
      '.oBBoo...aAAa...',
      '.oBBBBooooBBBo..',
      '..oBBBBBBBBwBeo.',
      '..oBBBddBBBBBgo.',
      '...oBBaBBaBBBoo.',
      '...oBBBBddBBBo..',
      '...oBoooooBBBo..',
      '...oBo...oBBo...',
      '..oBBo...oBBo...',
      '..oggo...oggo...',
    ],
    legs: [[3, 5], [9, 11]],
    legTop: 12, spine: [7, 11], head: [3, 8], headX: [8, 15],
    tail: [5, 6], tailX: [1, 5], mark: [5, 9],
    on: { throat: [9, 9], brow: [11, 7], back: [6, 10], leg: [10, 13] },
    crest: { ox: 8, oy: 1, rows: ['.c.c.c', 'cc.cc.', '.ccc..'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '..a.a......a.a..',
      '..aAa......aAa..',
      '.aAAa.oooo.aAAa.',
      '...aoBBBBBBoa...',
      '....oBwBBwBo....',
      '....oBeBBeBo....',
      '....oBBggBBo....',
      '...oBBBBBBBBo...',
      '..oBBBaBBaBBBo..',
      '..oBBBddddBBBo..',
      '..oBoooooooBBo..',
      '..oBo.....oBo...',
      '.oBBo.....oBBo..',
      '.oggo.....oggo..',
    ],
    legs: [[2, 4], [10, 12]],
    legTop: 12, spine: [9, 12], head: [2, 5], headX: [1, 14],
    tail: null, tailX: null, mark: [5, 9],
    on: { throat: [7, 9], brow: [7, 5], back: [7, 11], leg: [3, 13] },
    crest: { ox: 2, oy: 0, rows: ['.c........c.', 'ccc......ccc', '.c........c.'] },
    back: [{ ox: 4, oy: 5, rows: ['.oBBBBBBo.', 'oBBBBBBBBo', 'oBBaBBaBBo',
                                  'oBBBBBBBBo'] },
           { ox: 6, oy: 12, rows: ['oBBo', 'oBBo', '.oo.'] }],
  },
};

/* ---- tortoise: a dome on four stumps. The dome never moves, ever. ---- */
ANIMALS.tortoise = {
  body: 'grass', accent: 'earth', hard: 'wood', family: 'world',
  gait: 'plod', idle: 'blink', fallen: 'capsize',
  period: 1400, idlePeriod: 3400, bob: 0, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '...oooooooo.....',
      '..oggggkgggo....',
      '.oggggkgggggo...',
      '.ogggkggggggko..',
      '.ogkkgggkkkkgo..',
      '.ogggkgggggggo..',
      '.ogggggggggggo..',
      '.oooooooooooooo.',
      '.oBBBBBBBBBBBwBo',
      '.oBBddBBBdBBBeo.',
      '.oBBooBBoBBooBgo',
      '.oBo..oBo.oBooBo',
      '.oggo.ogg.oggogg',
    ],
    legs: [[1, 3], [6, 8], [10, 12], [13, 15]],
    legTop: 14, spine: [11, 13], head: [11, 13], headX: [12, 15],
    tail: null, tailX: null, shell: [3, 10], mark: [4, 5], crestHead: false,
    on: { throat: [11, 11], brow: [12, 9], back: [6, 4], leg: [12, 13] },
    crest: { ox: 2, oy: 1, rows: ['.c..c..c..c.', 'cccccccccccc'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '....oooooooo....',
      '..ooggggggggoo..',
      '.oggggkgkgggggo.',
      '.ogggkgggkggggo.',
      'ogggkgggggkgggo.',
      'ogggkgggggkgggo.',
      '.ogggkkkkkggggo.',
      '.ogggkggggkgggo.',
      '..ooggggggggoo..',
      '...oooBBBBooo...',
      '..oBooBwwBooBo..',
      '..oBo.oBBo.oBo..',
      '..oBo.oggo.oBo..',
      '..oggooooooggo..',
    ],
    legs: [[2, 4], [11, 13]],
    legTop: 12, spine: [11, 13], head: [12, 15], headX: [6, 9],
    tail: null, tailX: null, shell: [2, 10], mark: [5, 5], crestHead: false,
    on: { throat: [7, 11], brow: [7, 12], back: [7, 6], leg: [3, 13] },
    crest: { ox: 1, oy: 1, rows: ['..c..c..c..c..', 'cccccccccccccc'] },
    back: [{ ox: 5, oy: 11, rows: ['________', '________', '________', '________'] },
           { ox: 5, oy: 11, rows: ['.oBBBBo.', '.oBBBBo.', '.oooooo.'] }],
  },
};

/* ---- nautilus: a spiral that floats. Ragged tentacles, never a leg. ---- */
ANIMALS.nautilus = {
  body: 'bone', accent: 'violet', hard: 'bone', family: 'organic',
  gait: 'drift', idle: 'chamber', fallen: 'sink',
  period: 1100, idlePeriod: 2600, bob: 2, sway: 1,
  side: {
    grid: [
      '................',
      '.....oooooo.....',
      '...ooAAAAAAoo...',
      '..oAAAAaaaAAAo..',
      '.oAAAaaAAAaAAAo.',
      '.oAAaAAaaAAaAAo.',
      '.oAAaAAAaAAaAAo.',
      '..oAAaaaAAAaAo..',
      '...ooAAAAAoo....',
      '...oBBBBBBBo....',
      '..oBBBBBwBeBo...',
      '..oBBdBBBBBo....',
      '...oBoBoBoBo....',
      '...oBoBoBoo.....',
      '...oBoBoo.......',
      '...ooBo.........',
    ],
    legs: [], legTop: 16, spine: [9, 11], head: [9, 11], headX: [2, 12],
    tail: [13, 15], tailX: [3, 11], mark: [6, 5], crestHead: false,
    // The throat is the LOWER lip of the mantle, not the middle of it. Anchored
    // at the middle, a band ran along a row that already had the shell above it
    // and the body below it and repainted nineteen pixels for nought of
    // outline: the Twice-Ringing Pin was on the animal and could not be found.
    on: { throat: [7, 11], brow: [7, 2], back: [7, 4], leg: [4, 13] },
    crest: { ox: 4, oy: 0, rows: ['.cc..cc.', 'cc.cc.cc'] },
  },
  down: {
    grid: [
      '................',
      '......oooo......',
      '....ooAAAAoo....',
      '...oAAAAaaaao...',
      '..oAAAaaAAAaAo..',
      '..oAAaAAaaAAAo..',
      '..oAaAAAaAaAAo..',
      '..oAaAAAAaaAAo..',
      '...oAaaaaAAAo...',
      '....ooAAAAoo....',
      '....oBBBBBBo....',
      '...oBwBBBBwBo...',
      '...oBeBddBeBo...',
      '..oBoBoBoBoBo...',
      '..oBoBoBo.oBo...',
      '..ooo.oo...oo...',
    ],
    legs: [], legTop: 16, spine: [10, 12], head: [10, 12], headX: [3, 12],
    tail: [14, 15], tailX: [2, 13], mark: [5, 5], crestHead: false,
    on: { throat: [7, 12], brow: [7, 2], back: [7, 5], leg: [3, 14] },
    crest: { ox: 4, oy: 0, rows: ['.c..c..c.', 'cc.cc.cc.'] },
    back: [{ ox: 2, oy: 13, rows: ['____________', '____________', '____________'] },
           { ox: 4, oy: 10, rows: ['.oBBBBo.', 'oBBBBBBo', 'oBBaaBBo', '.oooooo.'] }],
  },
};

/* ---- crow: compact, heavy beak, forked tail, both feet together. ---- */
ANIMALS.crow = {
  body: 'void', accent: 'violet', hard: 'gunmetal', family: 'magic',
  gait: 'hop', idle: 'headturn', fallen: 'topple',
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
      '.oBBBBBaBBBBBoo.',
      '..oBBBaaBBBdBo..',
      '..oBaBaBBBdBo...',
      '...oBaaaBdBo....',
      '....oBBBBo......',
      '....oBooBo......',
      '....oBooBo......',
      '....oBooBo......',
      '...ogooooogo....',
    ],
    legs: [[4, 6], [7, 9]],
    legTop: 12, spine: [6, 11], head: [2, 6], headX: [9, 15],
    tail: [5, 8], tailX: [1, 4], mark: [4, 8],
    on: { throat: [11, 6], brow: [12, 3], back: [5, 7], leg: [5, 13] },
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
      '...oBadBBdaBo...',
      '...oBBaBBaBBo...',
      '....oBBddBBo....',
      '.....oBBBBo.....',
      '....oBooBo......',
      '....oBooBo......',
      '...ogooooogo....',
    ],
    legs: [[4, 6], [7, 9]],
    legTop: 13, spine: [7, 12], head: [2, 6], headX: [4, 11],
    tail: null, tailX: null, mark: [4, 9],
    on: { throat: [7, 7], brow: [7, 3], back: [7, 10], leg: [5, 14] },
    crest: { ox: 5, oy: 0, rows: ['.c..c.', 'cc..cc', '.cccc.'] },
    back: [{ ox: 4, oy: 7, rows: ['.oBBBBBBo.', 'oBBBBBBBBo',
                                  'oBBaBBaBBo', 'oBBBBBBBBo'] },
           { ox: 2, oy: 8, rows: ['oB........Bo', 'oB........Bo',
                                  'oB........Bo', 'oo........oo'] },
           { ox: 5, oy: 11, rows: ['oBBBBo', 'oBBBBo', '.o..o.'] }],
  },
};

/* ---- boar: all head and shoulder. The hump is higher than the rump. ----
 *
 * This one is drawn rather than borrowed because of who wears it. STUB is the
 * animal the player walks the entire tutorial beside, and BARROW is the same
 * animal returned at LEGENDARY after the fall at the first boss — between them
 * they are on screen for more of the game than any other companion. Both were
 * landing on `beast`, the fallback whose own comment says it is "deliberately
 * no markings and no character": the most-seen companion in the game was being
 * drawn by the shape that exists to mean nobody has drawn this yet.
 *
 * A boar is not a dog with a different palette, and the three things that say
 * so at 16px are all in the outline: the SHOULDER HUMP standing above the line
 * of the back, the head set straight on with no neck between them, and a tusk
 * on the front of the face pointing up out of the jaw. */
ANIMALS.boar = {
  body: 'leather', accent: 'earth', hard: 'bone', family: 'organic',
  gait: 'shove', idle: 'root', fallen: 'fold',
  period: 660, idlePeriod: 2400, bob: 1, sway: 0,
  side: {
    grid: [
      '................',
      '................',
      '................',
      '.......o.oo.....',
      '..oo..oBaBBo....',
      '..oBoooBBBBBooo.',
      '.oBBBBBBBaBBBBBo',
      '.oBaBBBBdaBBBBBo',
      '.oBBaBBdBBBBwBgo',
      '.oBBdaBdBBBBeBgo',
      '.oBBBddBBBBBgggo',
      '.oBBBBBBBBBBoooo',
      '.oBBoBBoBBoBo...',
      '.oBo.oBo.oBo....',
      '.oBo.oBo.oBo....',
      '.oggoogg.oggo...',
    ],
    // Three rows of leg under twelve rows of animal. A boar is a wedge carried
    // on short legs, and the first draft gave it four rows of daylight
    // underneath, which turned the same outline into a deer.
    legs: [[1, 3], [5, 7], [9, 11]],
    legTop: 13, spine: [6, 11], head: [6, 10], headX: [11, 15],
    tail: [4, 6], tailX: [2, 4], mark: [4, 7], crestHead: false,
    // The bristle ridge runs along the BACK, not on the skull, so it is not
    // part of the head block — the same `crestHead: false` the tortoise's shell
    // spines need and for the same reason. Without it the legendary boar's head
    // band grew to swallow the whole ridge, the gait's nod then moved eleven
    // columns of animal instead of five, and seven pixels of the COMMON outline
    // did not survive into LEGENDARY. On this animal that is not a rounding
    // error: STUB dies at the barrow and comes back as BARROW, and the whole
    // scene is the player recognising the same pig.
    on: { throat: [11, 7], brow: [12, 6], back: [9, 5], leg: [10, 13] },
    crest: { ox: 6, oy: 2, rows: ['.c.c.c', 'cc.ccc'] },
  },
  down: {
    grid: [
      '................',
      '................',
      '...oo......oo...',
      '...oBooooooBo...',
      '..ooBaBBBBaBoo..',
      '.oBBwBBBBBBwBBo.',
      '.oBBeBBaaBBeBBo.',
      'ogBBBBaggaBBBBgo',
      '.oBBdBBggBBdBBo.',
      '..oBBddBBddBBo..',
      '...oBBBBBBBBo...',
      '...oBBaBBaBBo...',
      '...oBBo..oBBo...',
      '...oBo....oBo...',
      '...oBo....oBo...',
      '...oggo..oggo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [9, 11], head: [2, 8], headX: [1, 14],
    tail: null, tailX: null, mark: [5, 10], crestHead: false,
    on: { throat: [7, 9], brow: [7, 4], back: [7, 11], leg: [4, 13] },
    crest: { ox: 5, oy: 1, rows: ['.c..c.', 'cc.ccc'] },
    back: [{ ox: 3, oy: 4, rows: ['.oBBBBBBBBo.', 'oBBBBBBBBBBo',
                                  'oBBaBBBBaBBo', 'oBBBBBBBBBBo',
                                  '.oBBBBBBBBo.'] }],
  },
};

/* ---- octopus: a soft bell wearing eight arms. No shell anywhere. ----
 *
 * MIMIC, the hidden companion, was resolving through PET_ALIAS to `nautilus`,
 * and a nautilus is the one cephalopod in the sea that is mostly SHELL. The
 * hidden animal was therefore arriving as the exact opposite of what it is: a
 * rigid spiral where the whole character of the thing is that it has no hard
 * parts and can be any shape it likes.
 *
 * What separates the two at 16px is one decision about the outline. The
 * nautilus is a closed convex disc with a small fringe under it. This is a
 * smooth bell on top and a RAGGED FAN underneath — the arms reach past the
 * width of the body on both sides and they end at different rows, so the
 * bottom half of the silhouette is broken where the nautilus's is solid. */
ANIMALS.octopus = {
  body: 'violet', accent: 'blood', hard: 'bone', family: 'magic',
  gait: 'creep', idle: 'impression', fallen: 'sink',
  period: 980, idlePeriod: 2200, bob: 1, sway: 1,
  side: {
    grid: [
      '................',
      '.....oooo.......',
      '...ooBBBBoo.....',
      '..oBBBBBBBBo....',
      '.oBBBaaBBBBBo...',
      '.oBBBaBBBBBBBo..',
      '.oBBBBBBBwwBBo..',
      '.oBBBBBBBweBBo..',
      '..oBBddBBBBBo...',
      '.oBoBoBoBoBoBo..',
      'oBo.oBoBoBo.oBo.',
      'oo..oBa.oBo..oBo',
      '....oBo..oBo..oo',
      '...oBa...oBo....',
      '...oBo....oo....',
      '...oo...........',
    ],
    legs: [], legTop: 16, spine: [2, 8], head: [4, 8], headX: [1, 13],
    tail: [9, 15], tailX: [0, 15], mark: [4, 4],
    on: { throat: [6, 8], brow: [6, 3], back: [6, 5], leg: [5, 11] },
    crest: { ox: 4, oy: 0, rows: ['.c.cc.c.', 'cc.cc.cc'] },
  },
  down: {
    grid: [
      '................',
      '......oooo......',
      '....ooBBBBoo....',
      '...oBBBBBBBBo...',
      '..oBBBaaBBBBBo..',
      '..oBBBaBBBBBBo..',
      '..oBwBBBBBBwBo..',
      '..oBeBBBBBBeBo..',
      '...oBBddddBBo...',
      '..oBoBoBoBoBo...',
      '.oBo.oBoBo.oBo..',
      'oBa..oBo.oBo.oBo',
      'oo...oBa.oBo..oo',
      '....oBo...oBa...',
      '....oo.....oo...',
      '................',
    ],
    legs: [], legTop: 16, spine: [2, 8], head: [4, 8], headX: [2, 13],
    tail: [9, 14], tailX: [0, 15], mark: [4, 4],
    on: { throat: [7, 8], brow: [7, 3], back: [7, 5], leg: [5, 12] },
    crest: { ox: 4, oy: 0, rows: ['.c..c..c.', 'cc.cc.cc.'] },
    back: [{ ox: 3, oy: 6, rows: ['.oBBBBBBBBo.', 'oBBBaBBaBBBo'] }],
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
  gait: 'trot', idle: 'breath', fallen: 'fold',
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
      '.oBBBBBBBdBBBBo.',
      '.oBBddBBdBBdBBo.',
      '.oBBoBBoBBoBBBo.',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.oBo.oBo..oBooBo',
      '.ogo.ogo..ogoogo',
    ],
    legs: [[1, 3], [5, 7], [10, 12], [13, 15]],
    legTop: 12, spine: [8, 11], head: [4, 7], headX: [10, 15],
    tail: [3, 6], tailX: [2, 4], mark: [4, 9],
    on: { throat: [11, 7], brow: [13, 5], back: [6, 8], leg: [11, 13] },
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
      '....oBBddBBo....',
      '...oBBBBBBBBo...',
      '...oBBdBBdBBo...',
      '...oBBBddBBBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...oBo.oo.oBo...',
      '...ogo.oo.ogo...',
    ],
    legs: [[3, 5], [10, 12], [7, 8]],
    legTop: 12, spine: [8, 11], head: [2, 7], headX: [3, 12],
    tail: null, tailX: null, mark: [5, 9],
    on: { throat: [7, 8], brow: [7, 4], back: [7, 10], leg: [4, 13] },
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
  ammonite: 'nautilus', shell: 'nautilus',
  squid: 'octopus', cuttlefish: 'octopus', cephalopod: 'octopus',
  mimic: 'octopus', kraken: 'octopus',
  auk: 'penguin', puffin: 'penguin',
  wolf: 'beast', dog: 'beast', fox: 'beast', hound: 'beast',
  pig: 'boar', hog: 'boar', sow: 'boar', swine: 'boar', warthog: 'boar',
  stub: 'boar', barrow: 'boar',
  // The starter dies at the barrow and comes back as BARROW, whose sprite key
  // is `boar_great`. It resolves to the same authored body as `boar` on
  // purpose and not by falling through: the return scene only lands if the
  // player recognises the animal, so the two ids must not be free to drift
  // apart. They are ONE authored animal at two rungs of the tier ladder, which
  // is what the scene is: the same pig, come back larger.
  boar_great: 'boar', great_boar: 'boar', dire_boar: 'boar',
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
 * player actually reads the pet by — disappears. It got sparser again once
 * regalia existed to compete with: at every second candidate cell the MYTHIC
 * aura was a fifth to a quarter of every painted pixel on the frame — on the
 * mimic it read as an animal covered in sparks rather than one lit from inside,
 * and the Borrowed Eye it was wearing disappeared into it. Every third and
 * every fourth candidate cell now. Chosen by a hash of its own coordinates plus
 * a seed, so it is stable
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

  /* Boar. All the drive is at the BACK. The hind legs work as a pair and throw
   * the hump up on the push frame while the head goes down, so the animal moves
   * the way a wedge moves: nose low, weight behind it. The head dip is a whole
   * two rows because there is no neck here to absorb it — a boar nods with its
   * shoulders, which is the exact opposite of the llama and the reason these
   * two never read alike even though both are quadrupeds with a four-row body. */
  shove(v, g, f, dir) {
    const hind = [v.legs[0], v.legs[1]];
    if (f === 0 || f === 2) {
      for (const leg of hind) if (leg) g = moveBlock(g, leg[0], leg[1], v.legTop, PET_H - 1, 0, -1);
      // Only the TOP half of the head band dips, which is the same rule
      // breathe() works to. It matters more here than anywhere else in the file
      // because a boar has no neck: its head band is most of the sprite facing
      // forward, so nodding the whole block slid fourteen columns of animal
      // down a row and painted over the throat — taking the collar, the bell
      // and every other piece of regalia tied there with it.
      const mid = Math.floor((v.head[0] + v.head[1]) / 2);
      g = moveBlock(g, v.headX[0], v.headX[1], v.head[0], mid, 0, 1);
    } else {
      const fore = v.legs[2];
      if (fore) g = moveBlock(g, fore[0], fore[1], v.legTop, PET_H - 1, 0, -1);
      // the hump lifts as the front end unloads: the top two rows of the back
      // only, so the belly line stays where the legs left it
      g = raiseBlock(g, v.on && v.on.back ? v.on.back[0] - 3 : 4,
                     (v.on && v.on.back ? v.on.back[0] : 7) + 3,
                     v.spine[0] - 2, v.spine[0], -1);
    }
    return g;
  },

  /* Octopus. It does not swim here, it WALKS on two arms — which is a real
   * thing a mimic octopus does and is the single most recognisable fact about
   * the animal. So two of the arms take turns being legs while the other six
   * ripple half a beat behind, and the bell rocks over whichever arm has the
   * weight. Nothing in this gait is symmetrical on any frame, because an
   * octopus that moves symmetrically reads as a jellyfish. */
  creep(v, g, f, dir) {
    const step = [[-1, 0], [0, -1], [1, 0], [0, 1]][f];
    // the two walking arms: the outer columns of the fan, moved against each
    // other so one is always planted
    g = moveBlock(g, 0, 4, v.tail[0], PET_H - 1, step[0], 0);
    g = moveBlock(g, PET_W - 5, PET_W - 1, v.tail[0], PET_H - 1, -step[0], 0);
    // the bell leans over the planted side, above the arm roots only
    if (step[1]) g = moveBlock(g, 0, PET_W - 1, 0, v.tail[0] - 1, 0, step[1]);
    if (f === 3) g = swapAccent(g);
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
  /* Boar: it roots. The head goes DOWN into the ground and stays there for the
   * tell frame, which is the only idle in the file where the animal stops
   * looking at the world entirely. A pig at rest is a pig with its face in the
   * dirt and it is not thinking about you. */
  root(v, g, f, dir) {
    g = breathe(v, g, f);
    if (f !== 3) return g;
    const mid = Math.floor((v.head[0] + v.head[1]) / 2);
    g = moveBlock(g, v.headX[0], v.headX[1], v.head[0], mid, 0, 1);
    return raiseBlock(g, v.on && v.on.back ? v.on.back[0] - 2 : 5,
                      (v.on && v.on.back ? v.on.back[0] : 8) + 2,
                      v.spine[0] - 1, v.spine[0] + 1, -1);
  },
  /* Octopus: it does an impression. The accents invert and the arms shift a
   * pixel out of line with each other — the animal has changed what it looks
   * like rather than moved, which is the whole joke of the hidden companion and
   * the only idle here whose tell is a texture and a stagger at once. */
  impression(v, g, f, dir) {
    if (f === 1) g = moveBlock(g, 0, PET_W - 1, 0, v.tail[0] - 1, 0, -1);
    if (f !== 3) return g;
    g = swapAccent(g);
    g = moveBlock(g, 0, 4, v.tail[0], PET_H - 1, 1, 0);
    return moveBlock(g, PET_W - 5, PET_W - 1, v.tail[0], PET_H - 1, -1, 0);
  },
  /* The fallback. Breathing and a small shift of weight, which is the least an
   * unknown animal is allowed to do and still count as alive. */
  breath(v, g, f, dir) {
    g = breathe(v, g, f);
    return f === 3 ? moveBlock(g, 0, PET_W - 1, v.spine[0], v.spine[1], 1, 0) : g;
  },
};

/* ------------------------------------------------------------------ fallen
 *
 * A companion takes AoE damage and goes down, and the player has to be able to
 * tell WHICH of those two things just happened from across a busy overworld,
 * at 16 pixels, without stopping to look.
 *
 * Before this pass the fainted frame was the standing frame in a darker
 * palette. Measured against the standing pose it differed by THREE pixels of
 * silhouette on the jaguar and three on the axolotl, out of a hundred and ten
 * — the animal was upright, all four feet planted, head level, in mourning
 * colours. That is a recolour, and a recolour is the exact failure every
 * harness in this project exists to refuse: a piece of armour that only
 * repaints the sprite has not been implemented, and neither has a faint.
 *
 * So a fainted companion is a POSE. Five of them, one per body plan, and every
 * one takes the outline from TALL to LOW AND WIDE, which is the thing the eye
 * resolves before it has resolved a single interior pixel. The numbers are in
 * petArtStats().fallen: ink height, and the share of the standing silhouette
 * that moves.
 *
 * What they deliberately do NOT do is redraw the animal. Every pose below is
 * the authored grid with blocks moved — the same ops the gaits are written in —
 * so a fallen jaguar is still spotted, a fallen tortoise is still carrying its
 * shell, and the roster screen is showing the player the animal they lost
 * rather than a generic corpse. That is the same promise the tier ladder makes
 * at the other end of the file, for the same reason.
 */

function inkRows(grid) {
  let top = -1, bot = -1;
  for (let y = 0; y < PET_H; y++) {
    const any = grid[y].indexOf('.') !== grid[y].length
      && [...grid[y]].some(c => c !== '.' && c !== ' ');
    if (!any) continue;
    if (top < 0) top = y;
    bot = y;
  }
  return [top, bot];
}

function inkCols(grid) {
  let lo = PET_W, hi = -1;
  for (let y = 0; y < PET_H; y++) {
    for (let x = 0; x < PET_W; x++) {
      const c = grid[y][x];
      if (c === '.' || c === ' ') continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
  }
  return [lo, hi];
}

/* The eyes. One glyph, and it is the only change on this page a player will
 * consciously name afterwards — the rest of the pose is what tells them before
 * they have noticed they have been told. */
function shut(grid) {
  return rowsOf(grid).map(r => r.replace(/w/g, 'o').replace(/e/g, 'o'));
}

/* Lift a block out of the grid and hand it back on its own, with the hole it
 * left behind. A fallen pose has to take the legs OFF the bottom of the animal
 * and put them somewhere else entirely, and that is two operations, not one. */
function lift(grid, x0, x1, y0, y1) {
  const src = rowsOf(grid);
  const rest = src.map(r => r.split(''));
  const part = [];
  for (let y = 0; y < PET_H; y++) part.push(new Array(PET_W).fill('.'));
  for (let y = Math.max(0, y0); y <= Math.min(PET_H - 1, y1); y++) {
    for (let x = Math.max(0, x0); x <= Math.min(PET_W - 1, x1); x++) {
      const ch = src[y][x];
      if (ch === '.' || ch === ' ') continue;
      part[y][x] = ch;
      rest[y][x] = '.';
    }
  }
  return [rest.map(r => r.join('')), part.map(r => r.join(''))];
}

/* Lay two grids over one another. Later wins, '.' never erases. */
function over(a, b) {
  const A = rowsOf(a), B = rowsOf(b);
  const out = A.map(r => r.split(''));
  for (let y = 0; y < PET_H; y++) {
    for (let x = 0; x < PET_W; x++) {
      const ch = B[y][x];
      if (ch !== '.' && ch !== ' ') out[y][x] = ch;
    }
  }
  return out.map(r => r.join(''));
}

/* Settle a grid until its lowest ink is on `row`. */
function restOn(grid, row) {
  const [, bot] = inkRows(rowsOf(grid));
  if (bot < 0) return rowsOf(grid);
  const dy = row - bot;
  return dy ? moveBlock(grid, 0, PET_W - 1, 0, PET_H - 1, 0, dy) : rowsOf(grid);
}

/* How many rows of leg are left sticking out of a fainted quadruped. Measured
 * rather than picked: at four the outline is as tall as the standing animal and
 * the pose stops reading from a distance; at two the legs vanish into the body
 * and it reads as a rock. */
const FALLEN_LEG = 3;

const FALLEN = {
  /* Four legs, off them.
   *
   * The first version of this dropped the animal and then dropped the head into
   * it, and what came out was a five-row dark bar: a shape on the ground, but
   * not an animal on the ground. The fix is the legs. They are not cleared and
   * they are not stubbed in afterwards — they are LIFTED off the bottom of the
   * sprite and put back on TOP of it, which is where the legs of a thing lying
   * on its side actually are. That is the read: a low body, a head laid out
   * flat at the front of it, and four feet in the air.
   */
  fold(v, g, dir) {
    const src = rowsOf(g);
    // 1. the feet come off the floor, kept whole — each leg in its OWN column
    //    range, never in one rectangle spanning all of them. The raptor is why:
    //    its two legs sit at the ends of the grid and the bounding box between
    //    them is most of the belly, so lifting the box tore the animal in half
    //    and what landed was four disconnected pieces.
    let body = src, feet = null;
    for (const leg of (v.legs || [])) {
      const [rest, part] = lift(body, leg[0], leg[1], v.legTop, PET_H - 1);
      body = rest;
      feet = feet ? over(feet, part) : part;
    }
    // 2. the body comes down onto the floor, one row of contact left under it
    const [, wasBot] = inkRows(body);
    if (wasBot < 0) return shut(src);
    const drop = (PET_GROUND - 1) - wasBot;
    if (drop) body = moveBlock(body, 0, PET_W - 1, 0, PET_H - 1, 0, drop);
    const [bodyTop] = inkRows(body);
    // 3. the head is the only part that was being held up by anything, so it is
    //    the part that falls furthest: flat at the front, level with the spine.
    const hy0 = Math.max(0, v.head[0] + drop), hy1 = Math.min(PET_H - 1, v.head[1] + drop);
    const headFall = (PET_GROUND - 1) - hy1;
    if (headFall > 0) body = moveBlock(body, v.headX[0], v.headX[1], hy0, hy1, 0, headFall);
    // 4. and the tail stops being a flag
    if (v.tail) {
      const ty1 = Math.min(PET_H - 1, v.tail[1] + drop);
      const tf = (PET_GROUND - 1) - ty1;
      if (tf > 0) body = moveBlock(body, v.tailX[0], v.tailX[1],
                                   Math.max(0, v.tail[0] + drop), ty1, 0, tf);
    }
    // 5. the feet go back on, above the body, pointing at the sky — and only
    //    the thigh end of them. A whole leg stood on end is as tall as the leg
    //    was, which puts the fainted outline back at the height of the standing
    //    one and throws away the low-and-wide read the other four rows bought.
    //    Three rows of shin is a leg in the air; twelve is a fence.
    if (feet) {
      const [, footBot] = inkRows(feet);
      const up = (bodyTop + 1) - footBot;
      if (up) feet = moveBlock(feet, 0, PET_W - 1, 0, PET_H - 1, 0, up);
      const cut = Math.max(0, (bodyTop + 1) - FALLEN_LEG);
      feet = rowsOf(feet).map((r, y) => (y < cut ? '.'.repeat(PET_W) : r));
      body = over(body, feet);
    }
    return shut(body);
  },

  /* A biped goes over sideways rather than down: the mass is already stacked
   * over the feet, so what fails is balance and not the legs. The top of the
   * body leans three pixels — far enough that the centre of it is outside the
   * feet, which is the geometry a viewer reads as falling rather than as
   * leaning — and then the whole thing lands. */
  topple(v, g, dir) {
    let out = rowsOf(g);
    for (let y = 0; y < v.legTop; y++) {
      const lean = 1 + Math.round(2 * (v.legTop - 1 - y) / Math.max(1, v.legTop - 1));
      out = moveBlock(out, 0, PET_W - 1, y, y, -lean, 0);
    }
    out = out.map((r, y) => (y >= v.legTop ? '.'.repeat(PET_W) : r));
    let [, bot] = inkRows(out);
    if (bot < 0) return shut(rowsOf(g));
    const drop = PET_GROUND - bot;
    if (drop > 0) out = moveBlock(out, 0, PET_W - 1, 0, PET_H - 1, 0, drop);
    // the feet, out from under, on the side it did not fall towards
    const g2 = rowsOf(out).map(r => r.split(''));
    const [, hi] = inkCols(rowsOf(out));
    for (let i = 1; i <= 3; i++) {
      const x = hi + i;
      if (x >= PET_W) break;
      g2[PET_GROUND - 1][x] = i === 3 ? 'g' : 'B';
      g2[PET_GROUND][x] = 'o';
      if (g2[PET_GROUND - 2][x] === '.') g2[PET_GROUND - 2][x] = 'o';
    }
    return shut(g2.map(r => r.join('')));
  },

  /* A snake does not collapse, it goes slack.
   *
   * It is the hardest of the five, because a coiled snake was already the
   * lowest thing in the roster and height cannot carry the difference. What
   * carries it is that the COIL COMES APART: a snake holds that shape with
   * muscle, so a snake that has stopped holding it is a loose line lying in the
   * dirt with its head off the end. The loops are pulled down into one another
   * and the head is laid out past the body, which turns a compact round thing
   * into a long flat one without moving it an inch lower.
   */
  slack(v, g, dir) {
    const src = rowsOf(g);
    const [top, bot] = inkRows(src);
    if (bot < 0) return shut(src);
    // the head off the coil first, so it is not dragged down with it
    let [body, head] = lift(src, v.headX[0], v.headX[1], v.head[0], v.head[1]);
    // the loops fall into each other: every row above the middle of the coil
    // comes down by two, which is the coil unwinding rather than sinking
    const mid = Math.floor((top + bot) / 2);
    for (let y = mid; y >= top; y--) body = moveBlock(body, 0, PET_W - 1, y, y, 0, 2);
    body = restOn(body, PET_GROUND);
    // and the head lies out past the end of it, flat on the floor
    const [hlo, hhi] = inkCols(head);
    const [blo, bhi] = inkCols(body);
    if (hhi >= hlo) {
      const push = hlo >= (blo + bhi) / 2 ? (bhi + 1) - hlo : (blo - 1) - hhi;
      head = moveBlock(head, 0, PET_W - 1, 0, PET_H - 1, push, 0);
      head = restOn(head, PET_GROUND);
    }
    return shut(over(body, head));
  },

  /* Neutrally buoyant, and then not.
   *
   * A thing that was floating does not topple, it settles — so the bell comes
   * down and DEFLATES, and the arms that were hanging under it go out flat on
   * both sides. Two changes rather than one, because the standing silhouette
   * was already a low round mass and a round mass that has only moved down is a
   * round mass. Squashed and spread, it is the widest and shortest of the five
   * poses, which is exactly what the other four are not.
   */
  sink(v, g, dir) {
    const src = rowsOf(g);
    const arms = v.tail ? v.tail[0] : Math.min(PET_H - 1, v.spine[1] + 1);
    let [bell, fan] = lift(src, 0, PET_W - 1, arms, PET_H - 1);
    // the bell loses a third of its height: the top rows come down into it
    const [top] = inkRows(bell);
    if (top >= 0) {
      const squash = Math.max(1, Math.round((arms - top) / 3));
      for (let y = top + squash; y >= top; y--) {
        bell = moveBlock(bell, 0, PET_W - 1, y, y, 0, squash);
      }
    }
    // the arms go out, hard, and lie in the two rows the bell is standing on
    const half = Math.floor(PET_W / 2);
    fan = moveBlock(fan, 0, half - 1, 0, PET_H - 1, -3, 0);
    fan = moveBlock(fan, half, PET_W - 1, 0, PET_H - 1, 3, 0);
    const [fTop, fBot] = inkRows(fan);
    if (fBot >= 0) {
      for (let y = fTop; y < fBot; y++) fan = moveBlock(fan, 0, PET_W - 1, y, y, 0, fBot - y);
    }
    fan = restOn(fan, PET_GROUND);
    bell = restOn(bell, PET_GROUND - 1);
    return shut(over(fan, bell));
  },

  /* The tortoise is the only one of the twelve whose faint needed no invention,
   * because there is exactly one thing that has ever happened to a tortoise
   * that everybody already reads instantly. It is on its back. The grid is
   * flipped top to bottom, which puts the shell on the floor and four stumps in
   * the air, and nothing else in the file produces a shape like it. */
  capsize(v, g, dir) {
    const src = rowsOf(g);
    const flipped = [];
    for (let y = 0; y < PET_H; y++) flipped.push(src[PET_H - 1 - y]);
    // a flip leaves the animal hanging from the ceiling: settle it back down
    const [, bot] = inkRows(flipped);
    let out = flipped;
    if (bot >= 0) {
      const drop = PET_GROUND - bot;
      if (drop > 0) out = moveBlock(out, 0, PET_W - 1, 0, PET_H - 1, 0, drop);
    }
    return shut(out);
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

/* A collar is on the throat whichever way the animal is pointing, so the
 * anchors mirror with the grid. They are single cells rather than ranges, which
 * is why this is four lines instead of reusing flipX. */
function mirrorAnchors(on) {
  if (!on) return on;
  const out = {};
  for (const k of Object.keys(on)) {
    out[k] = on[k] ? [PET_W - 1 - on[k][0], on[k][1]] : null;
  }
  return out;
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
    on: mirrorAnchors(v.on),
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
    // What you can see of a worn object from BEHIND. A collar at the throat is
    // on the far side of the animal and a lens over its eye is not there at
    // all, so the face anchors are dropped rather than drawn on the back of the
    // skull; `back` and `leg` survive, which is why a harness, a barding and a
    // leg ring are the pieces that still read when the pet is walking away.
    on: v.on ? { back: v.on.back, leg: v.on.leg, brow: v.on.brow,
                 throat: null, hidden: true } : null,
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

/* ----------------------------------------------------------- second material
 *
 * applyRim() only knows one glyph. It turns 'B' into four steps and leaves
 * every other mass exactly as authored, which was fine while the non-body
 * masses were markings — a rosette, a beak, two pixels of claw. It stopped
 * being fine the moment it was measured: a tortoise is a dome of 'g' with two
 * specks on it, a penguin is a slab of 'A', and a nautilus is a shell of 'A'.
 * Those three animals were rendering their largest surface in ONE FLAT COLOUR,
 * which is why the tortoise read as a brown rounded rectangle with legs.
 *
 * The fix is not a second lighting model — rule 5 forbids that, and correctly:
 * a cast stops looking like a cast the moment two things in it are lit from two
 * places. It is the SAME function, run again on a different material. The mass
 * is promoted to 'B', everything else in the sprite becomes an edge, applyRim
 * runs, and its four answers are translated back into that material's own
 * steps. One lamp, one direction, two surfaces.
 */
function liteMass(grid, mass, steps) {
  const src = rowsOf(grid);
  // Only a real SURFACE gets the second pass. A llama's muzzle and its four
  // hooves are five cells of 'g' between them, and shading five cells costs a
  // whole palette slot to say something nobody can see: swept over every
  // animal, tier, colour, facing, frame and worn object, that one slot was the
  // difference between a worst case of fifteen colours and one of fourteen.
  // Sixteen cells is where a mass starts having an inside, and it is a measured
  // number rather than a taste: across the twenty-two authored views the areas
  // are 2, 3, 4, 5, 6, 8 ... 29, 40, 51, 52, 90. There is nothing between eight
  // and twenty-nine, so the threshold is sitting in a real gap and only the
  // tortoise's shell, the penguin's front and the nautilus's wall are on the
  // far side of it — which are exactly the three surfaces that were flat.
  let area = 0;
  for (const row of src) for (const ch of row) if (ch === mass) area++;
  if (area < LIT_MASS_MIN) return src;
  const masked = src.map(r => r.split('').map(ch => (
    ch === mass ? 'B' : (ch === '.' || ch === ' ') ? '.' : 'o')).join(''));
  const lit = applyRim(masked);
  const out = src.map(r => r.split(''));
  for (let y = 0; y < PET_H; y++) {
    for (let x = 0; x < PET_W; x++) {
      if (src[y][x] !== mass) continue;
      const ch = lit[y][x];
      const t = ch === 'H' ? steps[0] : ch === 'L' ? steps[1]
              : ch === 'd' ? steps[2] : ch === 'D' ? steps[3] : null;
      if (t) out[y][x] = t;
    }
  }
  return out.map(r => r.join(''));
}

/* Which masses get the second pass, in the order they are painted.
 *
 *   'g'  shell, beak, tusk, hoof, claw — the hard material. It costs one
 *        palette slot ('k') and buys form on the single largest surface three
 *        of the twelve animals own.
 *   'A'  the light accent: a penguin's front, a nautilus's shell wall. This one
 *        is free, because its shadow step resolves to 'a', which the sprite is
 *        already wearing.
 */
const LIT_MASS_MIN = 16;
const LIT_MASSES = [['g', ['c', 'g', 'k', 'k']], ['A', ['A', 'A', 'a', 'a']]];

function liteAll(grid) {
  let g = grid;
  for (const [mass, steps] of LIT_MASSES) g = liteMass(g, mass, steps);
  return g;
}

/* ------------------------------------------------------------------ regalia
 *
 * gauntlet/regalia.py ships twenty-four objects, two per companion, and
 * gauntlet/quests.py ships seven more that go on whichever animal is in the
 * field. Thirty-one in all, and until this pass not one of them existed as a
 * pixel: a player could earn the Jade Collar and the jaguar walking in front of
 * them was the same jaguar it had been the day before.
 *
 * That is the same failure the hero rig keeps a whole harness pointed at — a
 * piece of armour that does not change the sprite has not been implemented —
 * so this is held to the same measurement. petArtStats().regalia reports, for
 * every one of the thirty-one, the pixels it repaints and the pixels of OUTLINE
 * it adds, per facing, counted off the grid.
 *
 * PYTHON ALREADY DECIDED THIS AND THIS FILE DOES NOT GET A SECOND OPINION
 *
 * Every row in regalia.py carries an `icon`, a `colour` and a sentence saying
 * where it is worn:
 *
 *    jade_collar     "One band, worn loose, and it does not rattle."
 *    mystic_scarf    "Wound twice and trailing, which on a penguin is most of
 *                     the animal."
 *    trough_lens     "Strapped over one eye. The other eye is doing nothing."
 *    rooks_tally     "Carried in the beak, set down to speak, picked up again."
 *    closed_half_ring "Through the ear that is still there."
 *
 * So the table below is those sentences resolved to an ANCHOR and nothing more.
 * The shape comes from `icon`, the colour comes off the row at runtime, and a
 * piece nobody has listed here still draws — as a band at the throat, which is
 * where most tack goes — rather than silently not existing.
 *
 * The seven from quests.py are the exception and are marked: that module ships
 * no `icon` and no `colour`, so both are authored here, and if it grows them
 * they are the ones to delete.
 *
 * WHY EVERY PIECE HAS TO LEAVE THE OUTLINE
 *
 * At sixteen pixels an object painted entirely INSIDE the animal is three cells
 * of a different hue on a body already wearing five, and it is gone the instant
 * the pet walks in front of a bush. So every band here hangs something below
 * it, every pendant sits proud of the belly line, and the scarf trails. The
 * number that matters is not how many pixels a piece paints. It is how many
 * pixels of SILHOUETTE it adds, and that is the one the harness fails on.
 */

/* Where on the animal. Six names, four of them authored per view in the
 * ANIMALS table as `on:`, two of them found in the grid because the grid
 * already marks them: the eye is the 'w', the mouth is the outermost 'g'
 * inside the head band. Found rather than authored so they keep working when
 * the gait has moved the head, which is the same reason protrude() finds the
 * snake's mouth instead of being told where it is. */
function anchorAt(v, name) {
  const on = v.on || {};
  // An anchor that lands on air is not an anchor. The snake is the case that
  // found it: its back view SUBTRACTS the head, so the throat coordinate its
  // front view was authored against points at empty space once the face has
  // been taken off, and the Kept Skin was being tied round three pixels of
  // nothing an inch below the animal. A piece with nowhere to hang is a piece
  // you cannot see from that side, which is the truth and is fine.
  const solid = (a) => !!a && SOLID(rowsOf(v.grid), a[1], a[0]);
  const ok = (a) => (solid(a) ? a : null);
  if (name === 'eye' || name === 'mouth') {
    if (on.hidden) return null;              // it is on the far side of the animal
    const found = findIn(v.grid, v.head, name === 'eye' ? 'w' : 'g');
    if (found) return found;
    return ok(on.brow) || ok(on.throat);
  }
  if (name === 'leg') return ok(on.leg) || ok(on.back) || ok(on.throat);
  if (name === 'back') return ok(on.back) || ok(on.throat);
  if (name === 'brow') return ok(on.brow) || ok(on.throat);
  return ok(on.throat) || ok(on.brow);
}

function findIn(grid, band, glyph) {
  const src = rowsOf(grid);
  const y0 = Math.max(0, band ? band[0] : 0);
  const y1 = Math.min(PET_H - 1, band ? band[1] : PET_H - 1);
  let best = null;
  for (let y = y0; y <= y1; y++) {
    for (let x = 0; x < PET_W; x++) {
      if (src[y][x] !== glyph) continue;
      if (!best || x > best[0]) best = [x, y];
    }
  }
  return best;
}

/* ---- the primitives every piece is built out of ----
 *
 * The first version of this was a table of fixed pixel strips stamped at the
 * anchor, and it measured at twelve pixels repainted and ZERO pixels of
 * silhouette added: a jade collar that was three cells of green inside a
 * jaguar, gone the moment the animal stood in front of a bush. So none of the
 * shapes below are authored at a fixed size. Each one MEASURES the animal at
 * the anchor and then deliberately leaves it — a band runs one pixel past the
 * limb at both ends, a pendant hangs off the underside, a plate sits proud of
 * the back — because the only regalia a player can see at sixteen pixels is
 * regalia that is part of the outline.
 */
/* How wide a band gets, and how far a pendant drops before it gives up looking
 * for air. Both are caps rather than sizes: the shapes measure the animal
 * first and these stop the measurement running away on a body that has no gap
 * in it anywhere below the throat. */
const BAND_MAX = 6;
const HANG_MAX = 2;
const PAST_MAX = 2;

const SOLID = (src, y, x) => y >= 0 && y < PET_H && x >= 0 && x < PET_W
  && src[y][x] !== '.' && src[y][x] !== ' ';

function runH(src, x, y) {
  let a = x, b = x;
  while (SOLID(src, y, a - 1)) a--;
  while (SOLID(src, y, b + 1)) b++;
  return [a, b];
}
function runV(src, x, y) {
  let a = y, b = y;
  while (SOLID(src, a - 1, x)) a--;
  while (SOLID(src, b + 1, x)) b++;
  return [a, b];
}

function put(g, x, y, ch) {
  if (x < 0 || x >= PET_W || y < 0 || y >= PET_H) return;
  g[y][x] = ch;
}

/* Draw the outline back around whatever was just stamped.
 *
 * Every band already caps its own two ends, but a pendant, a plate or a lens
 * sits in the middle of a body and has nothing separating it from that body but
 * hue. The Keybrass Bell is the case that proves it: brass on a cream llama at
 * sixteen pixels, and the bell was nine pixels of a colour four steps from the
 * one underneath it. A hard edge is what the hardware would have given it and
 * it is what makes a worn object read on twelve differently-coloured animals
 * instead of on the five it happens to contrast with. */
function edge(g, cells) {
  for (const [x, y] of cells) {
    for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || nx >= PET_W || ny < 0 || ny >= PET_H) continue;
      const ch = g[ny][nx];
      if (ch === 'j' || ch === 'w' || ch === 'o' || ch === 'O') continue;
      if (cells.some(c => c[0] === nx && c[1] === ny)) continue;
      g[ny][nx] = 'o';
    }
  }
}

/* A band around whatever limb the anchor is on, one pixel past it at each end.
 *
 * Which way it runs is measured, not authored, and that is what lets one
 * function put a collar on a jaguar's horizontal neck seen from the side AND on
 * the same jaguar's vertical neck seen from the front. A band lies ACROSS the
 * short axis of the body at the point it is tied, so it spans the shorter of
 * the two runs through the anchor. Author it as a fixed horizontal strip and it
 * lies along the neck instead of around it on half the facings in the file. */
function strip(g, src, x, y, thick, glyph, gap) {
  const [hx0, hx1] = runH(src, x, y), [vy0, vy1] = runV(src, x, y);
  const across = (hx1 - hx0) <= (vy1 - vy0);
  let lo = across ? hx0 : vy0, hi = across ? hx1 : vy1;
  // A band is capped, and the cap is the difference between a collar and a
  // racing stripe. The run through a jaguar's throat in side view is the whole
  // animal from the ears to the floor, twelve pixels of it, and a band that
  // honest ran top to bottom of the cat: it read as paint rather than as
  // something tied on. Six is the widest a thing tied round a neck gets at this
  // size, centred on where it was tied.
  const anchor = across ? x : y;
  if (hi - lo + 1 > BAND_MAX) {
    lo = Math.max(lo, anchor - (BAND_MAX >> 1));
    hi = Math.min(hi, lo + BAND_MAX - 1);
    lo = Math.max(across ? hx0 : vy0, hi - BAND_MAX + 1);
  }
  for (let t = 0; t < (thick || 1); t++) {
    for (let i = lo - 1; i <= hi + 1; i++) {
      const edge = (i === lo - 1 || i === hi + 1);
      if (gap && !edge && ((i - lo) & 1)) continue;
      const ch = edge ? 'o' : glyph;
      if (across) put(g, i, y + t, ch); else put(g, x + t, i, ch);
    }
  }
  // Where the band ended and which way it ran, for the one piece that has to
  // trail off the end of itself. `across` matters: `lo` is an x when the band
  // lies horizontally and a y when it stands vertically, and a scarf that reads
  // it as an x either way hangs its tail off the side of the wrong animal the
  // first time somebody puts it on a llama.
  return { lo: lo - 1, hi: hi + 1, across };
}

/* Straight down from the anchor until the animal ends, then keep going. What
 * hangs off a collar is the part of it anybody can see from six tiles away. */
function hang(g, src, x, y, rows, outline) {
  const placed = [];
  let by = y;
  // At most two rows down before it hangs anyway. Walking to the first air cell
  // is right on a jaguar's chest and wrong on a llama's neck, where the animal
  // is solid from the throat all the way through the body and down a leg: the
  // bell was being hung at row sixteen, off the bottom of the grid, and the
  // Keybrass Bell — the loud one, by its own description — repainted three
  // pixels. A bell that has to sit on the chest to be seen sits on the chest.
  while (by < y + HANG_MAX && SOLID(src, by + 1, x)) by++;
  for (let r = 0; r < rows.length; r++) {
    const row = rows[r];
    for (let c = 0; c < row.length; c++) {
      const ch = row[c];
      if (ch === '.') continue;
      const px = x + c - ((row.length - 1) >> 1), py = by + 1 + r;
      put(g, px, py, ch);
      if (ch === 'j') placed.push([px, py]);
    }
  }
  if (outline !== false) edge(g, placed);
}

/* Straight up from the anchor until the animal ends, then sit ON it. A plate, a
 * rule, a gong, a lamp: things bolted to a back or a shell, which have to raise
 * the top line of the silhouette or they are just a pattern. */
function proud(g, src, x, y, rows) {
  const placed = [];
  let ty = y;
  while (SOLID(src, ty - 1, x)) ty--;
  for (let r = 0; r < rows.length; r++) {
    const row = rows[r];
    for (let c = 0; c < row.length; c++) {
      const ch = row[c];
      if (ch === '.') continue;
      if (ch === 'j') placed.push([x + c - ((row.length - 1) >> 1), ty - rows.length + 1 + r]);
      // The bottom row lands ON the surface, not one above it. A plate bolted to
      // a shell with a pixel of daylight under it is a plate floating over a
      // shell, and at x14 that gap is the first thing the eye finds.
      put(g, x + c - ((row.length - 1) >> 1), ty - rows.length + 1 + r, ch);
    }
  }
  edge(g, placed);
}

/* Out past the front of the face, in the direction the animal is pointing. */
function past(g, src, x, y, dir, rows) {
  const step = (dir === 'down' || dir === 'up') ? [0, 1] : [1, 0];
  let px = x, py = y, n = 0;
  // Capped for the same reason hang() is. Facing the camera, "past the mouth"
  // points straight down through the whole bird, so an uncapped walk set the
  // crow's tally down below row fifteen and drew nothing at all.
  while (n++ < PAST_MAX && SOLID(src, py + step[1], px + step[0])) {
    px += step[0]; py += step[1];
  }
  const placed = [];
  for (let r = 0; r < rows.length; r++) {
    for (let c = 0; c < rows[r].length; c++) {
      const ch = rows[r][c];
      if (ch === '.') continue;
      const ax = px + step[0] + c - 1, ay = py + step[1] + r - 1;
      put(g, ax, ay, ch);
      if (ch === 'j') placed.push([ax, ay]);
    }
  }
  edge(g, placed);
}

/* Every icon regalia.py ships, resolved to one of the four primitives above.
 * `nail`, `chip`, `tooth`, `pin`, `whistle` and `reed` all land on `pendant`
 * on purpose: they are six names for a thing on a cord, and drawing six
 * distinguishable three-pixel objects would be six lies about how much
 * resolution there is here. What separates them on screen is the colour, and
 * the colour is Python's. */
const REGALIA_SHAPES = {
  band:    (g, s, x, y) => { strip(g, s, x, y, 1, 'j'); },
  skin:    (g, s, x, y) => { strip(g, s, x, y, 2, 'j'); },
  cord:    (g, s, x, y) => { strip(g, s, x, y, 1, 'j', true);
                             hang(g, s, x, y, ['j', 'o']); },
  collar:  (g, s, x, y) => { strip(g, s, x, y, 1, 'j');
                             hang(g, s, x, y, ['j', 'o']); },
  bell:    (g, s, x, y) => { strip(g, s, x, y, 1, 'j');
                             hang(g, s, x, y, ['.j.', 'jjj', '.o.']); },
  pendant: (g, s, x, y) => { strip(g, s, x, y, 1, 'j');
                             hang(g, s, x, y, ['j.j', 'o.o']); },
  // Wound twice and trailing, and on a penguin that is most of the animal. The
  // only piece in the set whose tail is longer than the body part it is tied to.
  scarf:   (g, s, x, y) => {
             const band = strip(g, s, x, y, 2, 'j');
             hang(g, s, x, y, ['jj.', 'jo.', 'o..']);
             const tail = [];
             for (let i = 1; i <= 3; i++) {
               const tx = band.across ? band.lo - i : x - i;
               const ty = band.across ? y + 1 + i : band.hi + i;
               put(g, tx, ty, i === 3 ? 'o' : 'j');
               if (i < 3) tail.push([tx, ty]);
             }
             edge(g, tail);
           },
  lens:    (g, s, x, y) => {
             const ring = [];
             for (const [dx, dy] of [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0],
                                     [-1, 1], [0, 1], [1, 1]]) {
               put(g, x + dx, y + dy, 'j'); ring.push([x + dx, y + dy]);
             }
             put(g, x, y, 'w');
             edge(g, ring.concat([[x, y]]));
           },
  ring:    (g, s, x, y) => { strip(g, s, x, y, 1, 'j', true); },
  cap:     (g, s, x, y) => { strip(g, s, x, y, 1, 'j');
                             hang(g, s, x, y, ['jjj', 'o.o']); },
  nub:     (g, s, x, y) => { proud(g, s, x, y, ['.j.', 'jjj']); },
  rule:    (g, s, x, y) => { proud(g, s, x, y, ['jjjjj', 'ooooo']); },
  disc:    (g, s, x, y) => { proud(g, s, x, y, ['.jj.', 'jjjj', '.jj.']); },
  plates:  (g, s, x, y) => { proud(g, s, x, y, ['.jjj.', 'jjjjj', 'o.o.o']); },
  harness: (g, s, x, y) => { proud(g, s, x, y, ['.w.', 'ojo', 'jjj']);
                             strip(g, s, x, y, 1, 'j', true); },
  muzzle:  (g, s, x, y, d) => { past(g, s, x, y, d, ['ojo', 'jjj', 'ojo']); },
  // Carried, not worn. These three go PAST the mouth in the direction the
  // animal is pointing rather than up from it: proud() walks to the top of
  // whatever column it is given, so a tally anchored at a beak was being set
  // down neatly on top of the crow's skull.
  held:    (g, s, x, y, d) => { past(g, s, x, y, d, ['jj', 'jj', 'oo']); },
  helddisc:(g, s, x, y, d) => { past(g, s, x, y, d, ['ojjo', 'jjjj', 'ojjo']); },
};

/* id -> where it goes and what it looks like. `icon` overrides regalia.py's own
 * only where its twenty names collapse onto one shape: `nail`, `chip`, `tooth`,
 * `pin`, `whistle` and `reed` are all a thing on a cord, and drawing six
 * different three-pixel objects would be six lies about how much resolution
 * there is. What separates them on screen is the colour, which is Python's. */
export const PET_REGALIA = {
  /* -- the boar, STUB -- */
  porch_nail:       { at: 'throat', icon: 'pendant' },
  doorbell_cord:    { at: 'leg',    icon: 'cord' },
  /* -- the snake, IDIOM -- */
  kept_skin:        { at: 'throat', icon: 'skin' },
  doorstep_dish:    { at: 'mouth',  icon: 'helddisc' },
  /* -- the llama -- */
  plateau_blinder:  { at: 'brow',   icon: 'band' },
  keybrass_bell:    { at: 'throat', icon: 'bell' },
  /* -- the axolotl -- */
  trough_lens:      { at: 'eye',    icon: 'lens' },
  second_whistle:   { at: 'throat', icon: 'pendant' },
  /* -- the jaguar -- */
  three_path_cord:  { at: 'leg',    icon: 'cord' },
  jade_collar:      { at: 'throat', icon: 'collar' },
  /* -- the raptor, SICKLE -- */
  spur_cap:         { at: 'leg',    icon: 'cap' },
  duplicate_tooth:  { at: 'throat', icon: 'pendant' },
  /* -- the penguin -- */
  lamp_glass:       { at: 'throat', icon: 'lens' },
  mystic_scarf:     { at: 'throat', icon: 'scarf' },
  /* -- the nautilus -- */
  inner_shell:      { at: 'back',   icon: 'nub' },
  twice_ringing_pin:{ at: 'throat', icon: 'pendant' },
  /* -- the crow -- */
  road_ring:        { at: 'leg',    icon: 'ring' },
  rooks_tally:      { at: 'mouth',  icon: 'held' },
  /* -- the tortoise -- */
  stair_rule:       { at: 'back',   icon: 'rule' },
  shell_gong:       { at: 'back',   icon: 'disc' },
  /* -- BARROW, the boar that came back -- */
  lit_tile_chip:    { at: 'brow',   icon: 'nub' },
  closed_half_ring: { at: 'brow',   icon: 'ring' },
  /* -- the mimic octopus -- */
  borrowed_eye:     { at: 'leg',    icon: 'lens' },
  borrowed_reed:    { at: 'leg',    icon: 'cap' },

  /* -- quests.py's seven, which fit any companion. These are the only rows
   *    here carrying a colour, because quests.REGALIA ships none; delete the
   *    hex the day it grows one. -- */
  field_collar:     { at: 'throat', icon: 'collar',  colour: '#8a6a4a' },
  keyed_bell:       { at: 'throat', icon: 'bell',    colour: '#c9a05a' },
  sealed_muzzle:    { at: 'mouth',  icon: 'muzzle',  colour: '#8fa8c8' },
  lantern_harness:  { at: 'back',   icon: 'harness', colour: '#f2c65a' },
  lattice_tack:     { at: 'back',   icon: 'plates',  colour: '#7e8f6a' },
  counted_barding:  { at: 'back',   icon: 'plates',  colour: '#c9a05a' },
  unlabelled_collar:{ at: 'throat', icon: 'collar',  colour: '#6a6470' },
};

export const PET_REGALIA_IDS = Object.keys(PET_REGALIA);

/** What a caller may hand over as `regalia`: an id, a whole regalia row from
 *  Python, or nothing. Never throws; an id nobody has placed becomes a band at
 *  the throat in its own colour, which is a wrong guess that is still visible
 *  and is therefore still better than a silent no-op. */
export function petRegaliaFor(worn) {
  if (!worn) return null;
  const id = (typeof worn === 'object')
    ? String(worn.id || worn.regalia_id || '') : String(worn);
  const key = id.toLowerCase().trim();
  if (!key) return null;
  const placed = PET_REGALIA[key] || { at: 'throat', icon: 'band' };
  const colour = (typeof worn === 'object' && typeof worn.colour === 'string'
                  && worn.colour.charAt(0) === '#') ? worn.colour
               : (placed.colour || '');
  return { id: key, at: placed.at, icon: placed.icon, colour };
}

/* Put it on. Stamped BEFORE the gait and before the tutorial head-shrink, for
 * the same reason the crest is: a collar merged after the deformation is a
 * collar that detaches from the throat on every frame the head moves, and at
 * this size that does not read as a loose collar, it reads as a bug. */
function wear(grid, v, piece, dir) {
  if (!piece) return grid;
  const hidden = !!(v.on && v.on.hidden);
  // From behind, a collar is the back of a collar: the band goes all the way
  // round a neck and is still there, but the bell, the tooth and the tag hanging
  // off the front of it are on the other side of the animal. So a throat piece
  // walking away from you is a plain band, and a lens or a bit in the mouth is
  // nothing at all — which anchorAt() has already refused by this point.
  const icon = (hidden && piece.at === 'throat') ? 'band' : piece.icon;
  const draw = REGALIA_SHAPES[icon] || REGALIA_SHAPES.band;
  const at = anchorAt(v, piece.at);
  if (!at) return grid;
  const src = rowsOf(grid);
  const g = src.map(r => r.split(''));
  draw(g, src, at[0], at[1], dir);
  return g.map(r => r.join(''));
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
 * how to feel. So: three tones of the darkest material we have plus one bone
 * highlight, no rim light, no accent, no mark, no aura, and the white gone out
 * of the eye.
 *
 * THE POSE CHANGES. This said "the same pose, the same outline" and stopped
 * being true when the FALLEN poses were authored — fold, topple, capsize,
 * slack, sink, one per animal — and it is the sentence a reader checks to find
 * out what fainted means, so it was the wrong sentence to leave stale. Measured
 * by petArtStats() as the share of the standing outline that moves, side view:
 *
 *   boar      fold      36%   <- the least
 *   jaguar    fold      67%
 *   nautilus  sink      73%
 *   snake     slack     80%
 *   octopus   sink     104%   <- more outline moves than the animal had
 *
 * So the silhouette is doing the work and the palette is only confirming it,
 * which is the right way round: a fainted companion that was merely a darker
 * companion is the bug the faint measurement in petArtStats() exists to catch,
 * and it WAS the bug for the whole of this file's first life — three pixels on
 * the jaguar, three on the axolotl. What this palette contributes is that the
 * changed pose reads as the shape of the animal with the animal no longer in
 * it, rather than as a second animal lying down. */
function deadPalette() {
  const deep = RAMPS.void[SHADE.DEEP];
  const dark = RAMPS.void[SHADE.DARK];
  const mid = RAMPS.void[SHADE.MID];
  const bone = RAMPS.bone[SHADE.DARK];
  return {
    o: OUTLINE, O: OUTLINE, e: OUTLINE,
    // Three steps of body and a bone highlight. The first version folded the
    // deepest step into the outline, which at this size meant the whole
    // underside of a fallen animal merged with its own silhouette and the pose
    // lost its form exactly where the pose is doing the work.
    D: deep, d: dark, B: mid, L: mid, H: bone,
    a: dark, A: mid, g: bone, k: dark, c: bone,
    j: bone, w: mid, R: dark, m: dark, r: dark,
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
    // Three steps of the hard material, not one. 'g' was the whole of it until
    // liteMass() started shading shells and beaks, and a dome painted in a
    // single flat tone is a dome the light never reached.
    g: hard[SHADE.LIGHT], c: hard[SHADE.SPEC], k: hard[SHADE.MID],
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
  // The worn object's own colour, straight off the Python row. It is the only
  // entry in here that is not derived from a shared ramp, and that is the
  // point: a jade collar is jade because regalia.py says so, and an object the
  // player went and got should not be quietly restyled to match the animal.
  const piece = o.regalia ? petRegaliaFor(o.regalia) : null;
  if (piece && piece.colour) pal.j = piece.colour;
  else if (piece) pal.j = rarity.accent;

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
 * one animal x four facings x four frames x two poses, plus the fainted frame:
 * 33 entries. The cap is not sized for that, it is sized for the worst case the
 * UI can actually produce, which is the roster screen holding the whole roster
 * at once — and that worst case grew twice in this pass. It was ten animals x
 * 33 x 2 tiers = 660, and 768 covered it. It is now TWELVE animals, and every
 * one of them can be shown bare beside itself wearing its regalia, which is
 * 12 x 33 x 2 = 792 — thirty entries over the old cap, which is the worst place
 * to be: the set no longer fits, so every pass evicts the entries the next pass
 * is about to ask for. Measured, not guessed: at 768 two further passes over
 * that set re-rendered 1560 canvases. At 1024 they re-render none, and 1024
 * sixteen-by-sixteen frames is a megabyte.
 */
const petCache = new Map();
const PET_CACHE_MAX = 1024;

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
function petGrid(key, dir, f, tierKey, dead, pose, worn) {
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

  const vv = (head === v.head && headX === v.headX) ? v : { ...v, head, headX };

  // The worn object goes on here: after the crest, before the shrink and before
  // the gait, so it travels with whichever block of the animal it is attached
  // to. A fainted animal is not wearing anything the player needs to read — the
  // pose is the whole message, and a scarf stamped at a throat that is about to
  // be moved onto the floor ends up hanging in the air behind the body.
  if (worn && !dead) g = wear(g, vv, worn, sideish ? 'side' : dir);

  // A tutorial companion is a smaller one. The head settles a row into the
  // shoulders, which takes a row off the top of the outline — a real change to
  // the silhouette rather than a paler version of the same animal.
  if (st.shrink && !dead) {
    const mid = Math.floor((head[0] + head[1]) / 2);
    g = moveBlock(g, headX[0], headX[1], head[0], mid, 0, st.shrink);
  }
  // A fainted companion is a still frame and a DIFFERENT POSE: no gait, no
  // idle, nothing twitches, and nothing is standing up either.
  if (dead) {
    g = (FALLEN[a.fallen] || FALLEN.fold)(vv, g, sideish ? 'side' : dir);
  } else {
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
  const worn = dead ? null : petRegaliaFor(o.regalia);
  const f = dead ? 0 : ((((frame | 0) % PET_FRAME_COUNT) + PET_FRAME_COUNT) % PET_FRAME_COUNT);

  const ck = `${key}:${dir}:${f}:${pose}:${tier}:${colour}:${dead ? 1 : 0}`
           + `:${worn ? worn.id + worn.colour : ''}`;
  const hit = petCache.get(ck);
  if (hit) return hit;

  let grid = petGrid(key, dir, f, tier, dead, pose, worn);

  // One merge, then one light, in the order sprites.js fixed for the whole
  // cast: the soft upper-left fill, then the single hot rim from low-left
  // INSIDE the heavy outline. The eye, the mark and the halo are protected —
  // an authored pixel that the shading pass eats is an authored pixel wasted.
  // The hard material is lit first, by the same function and the same lamp, so
  // that a shell has form before the body it is sitting on is shaded around it.
  grid = rimLowLeft(applyRim(liteAll(grid)), 'R', 'wemj');

  // The halo goes on last of all, outside the outline, after the lighting has
  // finished. It is not a surface, so it must not be lit like one.
  const st = TIER_STYLE[tier];
  if (st.halo && !dead) grid = halo(grid, `${key}:${dir}:${tier}`, st.halo === 1 ? 4 : 3);

  /* THE PALETTE ONLY HEARS ABOUT THE PIECE IF THE PIECE IS ACTUALLY ON THE
   * GRID. `j` is the regalia channel and REGALIA_SHAPES are its only writers,
   * so this asks the finished grid whether wear() stamped a single cell.
   *
   * It matters because petPalette() sets pal.j from the piece and then builds
   * the mark-collision set out of Object.values(pal) — which meant a piece that
   * drew NOTHING still nudged pal.m and still repainted pixels. Measured:
   * petFrame('crow','up',0,{tier:'MASTER',regalia:'rooks_tally'}) differed from
   * bare by 3 pixels with no tally anywhere on the sprite, and a typo'd id
   * scored 11 on every facing. Any harness asking "did this piece change
   * anything" got yes for a piece nobody can see, which is the one question
   * that check exists to answer. Now a diff of zero means zero, and the
   * collision nudge still runs whenever there is something to collide with. */
  const jStamped = grid.some(row => row.indexOf('j') >= 0);
  const canvas = gridSprite(
    grid, petPalette(key, { tier, colour, dead, regalia: jStamped ? worn : null }),
    PET_W, PET_H);
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
                  o.pose === 'idle' ? 'idle' : 'walk',
                  o.dead ? null : petRegaliaFor(o.regalia));
  const st = TIER_STYLE[petTierKey(o.tier)];
  if (st.halo && !o.dead) g = halo(g, `${key}:${dir}:${petTierKey(o.tier)}`,
                                  st.halo === 1 ? 4 : 3);
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
    // The faint, measured against the thing it has to be told apart from.
    // Coverage only: the palette is allowed no part in this, because a fainted
    // companion that is merely a darker companion is the bug this number
    // exists to catch, and it was the bug for the whole of this file's first
    // life — three pixels on the jaguar, three on the axolotl.
    const stand = petGrid(key, 'right', 0, 'COMMON', false, 'walk', null);
    const down = petGrid(key, 'right', 0, 'COMMON', true, 'idle', null);
    let poseMoved = 0, standInk = 0;
    for (let y = 0; y < PET_H; y++) {
      for (let x = 0; x < PET_W; x++) {
        const p = stand[y][x] !== '.', q = down[y][x] !== '.';
        if (p) standInk++;
        if (p !== q) poseMoved++;
      }
    }
    const rowsWith = (g) => {
      let top = -1, bot = -1;
      for (let y = 0; y < PET_H; y++) {
        if (![...g[y]].some(c => c !== '.' && c !== ' ')) continue;
        if (top < 0) top = y; bot = y;
      }
      return top < 0 ? 0 : bot - top + 1;
    };
    rows.push({
      animal: key, gait: a.gait, idle: a.idle, fallen: a.fallen,
      legs: a.side.legs.length,
      silhouette: { TUTORIAL: tut, COMMON: com, LEGENDARY: area(leg) },
      outlineChangedPerCycle: moved,
      shellPixelsMovedPerCycle: shellMoved,
      fainted: {
        outlineChangedFromStanding: poseMoved,
        shareOfTheStandingOutline: standInk
          ? +(poseMoved / standInk).toFixed(2) : null,
        inkRowsStanding: rowsWith(stand), inkRowsFainted: rowsWith(down),
      },
    });
  }

  /* Every worn object, against the animal without it. Two numbers per piece and
   * the second is the one that matters: pixels REPAINTED says the code ran,
   * pixels of OUTLINE ADDED says a player can see it from six tiles away with a
   * bush in the way. A piece scoring zero on the second on every facing is a
   * piece that has been implemented and cannot be found. */
  const regalia = [];
  for (const id of PET_REGALIA_IDS) {
    const piece = petRegaliaFor(id);
    let paint = 0, outline = 0;
    const per = {};
    for (const facing of PET_FACINGS) {
      const bare = petGrid('jaguar', facing, 0, 'COMMON', false, 'walk', null);
      const worn = petGrid('jaguar', facing, 0, 'COMMON', false, 'walk', piece);
      let p = 0, o = 0;
      for (let y = 0; y < PET_H; y++) {
        for (let x = 0; x < PET_W; x++) {
          if (bare[y][x] !== worn[y][x]) p++;
          if ((bare[y][x] !== '.') !== (worn[y][x] !== '.')) o++;
        }
      }
      per[facing] = [p, o];
      paint = Math.max(paint, p); outline = Math.max(outline, o);
    }
    regalia.push({ id, at: piece.at, icon: piece.icon,
                   worstPixelsRepainted: paint, worstOutlineAdded: outline, per });
  }

  return { animals: PET_ANIMALS.length, box: `${PET_W}x${PET_H}`,
           tiers: PET_TIERS.length, cache: petCacheStats(),
           regaliaPieces: regalia.length,
           regaliaThatChangeNothing: regalia.filter(r => !r.worstPixelsRepainted)
             .map(r => r.id),
           regaliaThatAddNoOutline: regalia.filter(r => !r.worstOutlineAdded)
             .map(r => r.id),
           regalia, rows };
}
