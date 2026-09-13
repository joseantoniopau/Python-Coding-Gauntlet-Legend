/* The overworld, rendered on the autotiling terrain engine.
 *
 * The previous version drew independent 16x16 blocks with no edge transitions,
 * which is what made the world read as a checkerboard. Terrain now comes from
 * tiles.js, which resolves each cell against its eight neighbours, so grass
 * meets water with a real shoreline and cliffs have faces rather than seams.
 *
 * Sprites come from sprites.js: a 16x24 hero with four authored facings and a
 * true four-frame walk, and 24x24 enemies with their own idle motion. Both are
 * larger than the tile grid, so everything is drawn with a centring offset and
 * y-sorted against the scenery rather than blitted at the tile origin.
 *
 * The companion walks the same world on the same sort. It is drawn, never
 * simulated: see "the companion" below for why that is the whole of the
 * promise that it will not get in your way.
 *
 * The apex hunter is the same bargain taken further. apex.js owns the chase,
 * the five escape guarantees and the telegraph art; this file owns exactly
 * three things about it — where it sits in the y-sort, when the world tells it
 * the player moved, and the rule that nothing it draws may ever cover the
 * player, a marker or the way out. When nothing is hunting, `this.hunt` is null
 * and every one of those paths is a single null check.
 *
 * The Null King is that bargain a third time, and the strictest of the three.
 * kingui.js owns his art, his panel, his placement and his clock; this file
 * owns where he sits in the same y-sort, the clamp that keeps him behind
 * everything he touches, and the order his panel is painted in relative to the
 * way out. He is NOT in the simulation: solid(), checkTile() and interact() do
 * not know he exists, so he is incapable of blocking a step, eating a keypress
 * or delaying a submission. When he has nothing to say, `this.king` is null and
 * every one of those paths is a single null check too.
 *
 * THE UNMAKING is the same bargain a fourth time and the last of them.
 * unmakingfx.js owns the spell — the beats, the substitutions, the arcs on the
 * silhouette, the light from the wrong direction — and this file owns the four
 * places it touches a frame: the hero's image is swapped for the plate, the
 * arcs are painted at the same coordinates the sprite was drawn at, the
 * companion's alpha is multiplied by what the spell says it is, and the screen
 * layer goes on in screen space BEFORE the way out. It is mounted exactly the
 * way that module's own integration note asks for it and in no other way.
 *
 * It does not block either, and it blocks less than he does: there is no key it
 * waits for, it cannot be dismissed because there is nothing to dismiss, the
 * player keeps walking the whole way through it, and `update()` reaches it
 * after the movement branch has already run. When nothing is being taken,
 * `this.unmaking` is null and every one of those paths is a single null check.
 */
import * as tiles from './tiles.js';
import * as sprites from './sprites.js';
import * as bosses from './bosses.js';
import * as pixel from './pixel.js';
import * as apexmod from './apex.js';
import * as kingui from './kingui.js';
import * as unmakingfx from './unmakingfx.js';
import * as monsterart from './monsterart.js';
/* For the sky, and for nothing else. battlescene.js holds the registry the
 * battle stage reads back out, so publishing the region here is what makes
 * walking into a fight continuous: same region, same moment, same weather. */
import * as stagelayer from './battlescene.js';
import { audio } from './audio.js';

const T = tiles.TILE_SIZE;
const MAP_W = 48;
const MAP_H = 34;

/* ------------------------------------------------------- FF6's pixel scale
 *
 * Final Fantasy VI's field is 256x224 world pixels at TILE 16 — SIXTEEN tiles
 * across and FOURTEEN down — and that number, not the canvas size, is what
 * decides how big a person feels standing in a place. T is already FF6's own
 * terrain tile; what was wrong was the multiplier in front of it.
 *
 * THE SCALE IS DRIVEN OFF HEIGHT, and it is worth saying why, because the
 * obvious rule is worse. This game's field canvas is between 1.26:1 and 1.54:1;
 * FF6's screen is 8:7, which is 1.14:1. There is no integer scale that lands on
 * 16x14 in BOTH axes on a widescreen canvas, so a rule has to say which axis it
 * is honouring:
 *
 *   fit the WIDTH to 256  -> at 1920x1080 the canvas is 1590 wide, so s = 7,
 *                            and the player sees 9.2 rows. Less than two thirds
 *                            of FF6's vertical field. The frame closes over
 *                            your head.
 *   fit the HEIGHT to 224 -> the rows stay at FF6's fourteen at every window
 *                            size this game opens at, and the extra monitor
 *                            width buys extra COLUMNS, which is exactly what a
 *                            widescreen version of a 4:3 game should spend it
 *                            on.
 *
 * So: s = round(viewH / 224). Round, not floor and not ceil — floor is what was
 * there and it is what let the view drift to twenty-three tiles across, and ceil
 * over-zooms a canvas that is a hair short. Rounding keeps the visible rows
 * inside 12.9..15.7 across every size measured, against FF6's 14.
 *
 * MIN_COLS is the guard for the shape this rule cannot see: a window that is
 * tall and narrow would take a scale off its height that its width cannot pay
 * for, and the player would be looking down a corridor. It never binds at any
 * size this game actually opens at — it allows 4, 5, 6 and 8 where the height
 * rule asks for 3, 4, 4 and 5 — it is there for the dragged window.
 *
 * SCALE_MIN IS 2 AND THAT IS NOT A RETREAT. Two is the scale a 1280x800 window
 * was shipping at and it is the thing being fixed — but it is fixed by the
 * height rule, which asks for 3 there, not by a floor. A floor of 3 would win
 * against MIN_COLS on a 480-wide frame and hand back ten columns, quietly
 * breaking the one promise the guard exists to make; measured, before it was
 * lowered. The floor is a backstop for a window dragged to nothing, it is not
 * the mechanism, and scripts/verify/field.mjs holds every real window to 3 or
 * better so it can never become the mechanism by accident.
 *
 * SCALE_MAX is 12 for the same reason it is not 8: a cap low enough to bite is
 * a cap that reintroduces the bug on a bigger monitor. At 8 a 5120x2880 canvas
 * goes back to forty tiles across. Twelve carries FF6 framing to a 2688-pixel
 * canvas, and a 192-pixel tile costs nothing to draw — the source images are
 * 16x16 either way, and the scaling is the GPU's nearest-neighbour blit. */
const FF6_FIELD_H = 224;     // FF6's field height in world pixels — 14 tiles
const FF6_FIELD_W = 256;     // and its width — 16 tiles. Reported, not fitted.
const MIN_COLS = 12;         // never fewer than this many tiles across
const SCALE_MIN = 2;
const SCALE_MAX = 12;

/* One function so the harness can ask the same question the renderer answers,
 * without a canvas and without a window. */
export function fieldScale(viewW, viewH) {
  /* A NaN here is a black screen, not a wrong zoom: it reaches ctx.scale() and
   * every subsequent coordinate in the frame is NaN. The old expression had the
   * same hazard and got away with it because only resize() could reach it; this
   * one is exported, so it is guarded rather than trusted. A canvas that has not
   * been laid out yet reports width 0, and 0 is the commonest way in. */
  if (!(viewW > 0) || !(viewH > 0)) return SCALE_MIN;
  const byHeight = Math.round(viewH / FF6_FIELD_H);
  const byWidth = Math.floor(viewW / (MIN_COLS * T));
  return Math.max(SCALE_MIN, Math.min(SCALE_MAX, Math.min(byHeight, byWidth)));
}

/** What that scale shows, in tiles. For the report and for the harness. */
export function fieldView(viewW, viewH) {
  const s = fieldScale(viewW, viewH);
  return { scale: s, cols: viewW / (T * s), rows: viewH / (T * s),
           ff6Cols: FF6_FIELD_W / T, ff6Rows: FF6_FIELD_H / T,
           heroPx: sprites.HERO_H * s };
}

export const TILES = tiles.TERRAIN;

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

/* ---------------------------------------------------------- the companion
 *
 * A pet follows by RETRACING, not by pathfinding. The player's recent pixel
 * positions go into a ring buffer and the companion is placed a fixed number of
 * PIXELS OF WALKED GROUND behind the newest sample. That one decision buys most
 * of the behaviour for free: the ground behind you is ground you were allowed to
 * stand on, so the companion never clips a wall, never needs a route, never
 * wedges itself on a cliff corner, and rounds corners the way you rounded them
 * rather than cutting across the rock. It also cannot get stuck, because it is
 * not solving anything.
 *
 * The lag is a distance rather than a count of frames, so a slow machine and a
 * fast one put the animal in the same place.
 *
 * It has no collision of its own. Nothing in solid() or checkTile() knows it
 * exists, so it is incapable of blocking a step or eating an interaction — the
 * strongest form of "must not be annoying" is not being in the simulation at
 * all.
 */
const TRAIL_SAMPLES = 96;      // ring buffer depth; ~96px of ground at 1px steps
const TRAIL_MIN_STEP = 1;      // px the player must cover before a new sample
const COMPANION_LAG = 18;      // px of walked ground between you and it
const COMPANION_MAX_SPEED = 190;  // px/s; the player walks at 112
const COMPANION_STRIDE = 7;    // px of ground per gait frame
const COMPANION_MOVING = 6;    // px/s below which it is standing, not walking
const SETTLE_AFTER = 0.30;     // s of you standing still before it comes alongside
const SETTLE_PX = 13;          // how far to the side it settles; under one tile
const TELEPORT_PX = T * 2.5;   // a jump this big was not walked

const FACE_VEC = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
                   side: [1, 0] };

/* Preallocated, because this is read every frame and a fresh array per frame in
 * a draw path is exactly what scripts/verify measures. */
class Trail {
  constructor(cap) {
    this.cap = cap;
    this.xs = new Float32Array(cap);
    this.ys = new Float32Array(cap);
    this.count = 0;
    this.head = 0;            // next write slot
    this.lastX = 0; this.lastY = 0;
  }

  reset(x, y) {
    this.count = 0; this.head = 0;
    this.lastX = x; this.lastY = y;
    this._write(x, y);
  }

  _write(x, y) {
    this.xs[this.head] = x; this.ys[this.head] = y;
    this.head = (this.head + 1) % this.cap;
    if (this.count < this.cap) this.count++;
  }

  /* Samples are spaced by DISTANCE, not by frame. Standing still adds nothing,
   * so an idle player does not flush the walked ground out of the buffer. */
  push(x, y) {
    const dx = x - this.lastX, dy = y - this.lastY;
    if (dx * dx + dy * dy < TRAIL_MIN_STEP * TRAIL_MIN_STEP) return false;
    this.lastX = x; this.lastY = y;
    this._write(x, y);
    return true;
  }

  x(i) { return this.xs[(this.head - 1 - i + this.cap * 2) % this.cap]; }
  y(i) { return this.ys[(this.head - 1 - i + this.cap * 2) % this.cap]; }

  /* Walk backwards along the path accumulating arc length until `dist` of it
   * has gone by, then interpolate inside the segment we landed in. The loop
   * exits as soon as the budget is spent, so it touches about COMPANION_LAG
   * samples and not the whole buffer. `exhausted` means the player has not
   * walked far enough yet for there to be a point that far back. */
  back(dist, out) {
    out.x = this.x(0); out.y = this.y(0); out.exhausted = true;
    if (this.count < 2) return out;
    let acc = 0;
    for (let i = 1; i < this.count; i++) {
      const ax = this.x(i - 1), ay = this.y(i - 1);
      const bx = this.x(i), by = this.y(i);
      const seg = Math.sqrt((bx - ax) * (bx - ax) + (by - ay) * (by - ay));
      if (acc + seg >= dist) {
        const t = seg > 0 ? (dist - acc) / seg : 0;
        out.x = ax + (bx - ax) * t;
        out.y = ay + (by - ay) * t;
        out.exhausted = false;
        return out;
      }
      acc += seg;
      out.x = bx; out.y = by;
    }
    return out;
  }
}

/* ------------------------------------------------------------- the art
 *
 * petart.js is another agent's file and may not exist yet. A static import of a
 * missing module takes the whole of overworld.js down with it and the world
 * screen stops rendering, which is the one outcome this feature is not allowed
 * to have. So both sources are loaded lazily and both failures are quiet: no
 * petart, no partyui, or a signature that has moved since this was written, and
 * the companion simply is not drawn.
 *
 * The contract asked for is petSprites(animal, opts) -> {down,up,left,right,
 * idle,...}, the same shape sprites.heroSprites returns and the same shape
 * _gatherObjects already knows how to index.
 */
let PET_ART_MODULE = null;
let PARTY_UI_MODULE = null;

function petArtModule() {
  if (!PET_ART_MODULE) {
    PET_ART_MODULE = import('./petart.js')
      .then(m => (m && typeof m.petSprites === 'function' ? m : null))
      .catch(() => null);
  }
  return PET_ART_MODULE;
}

function partyUiModule() {
  if (!PARTY_UI_MODULE) {
    PARTY_UI_MODULE = import('./partyui.js')
      .then(m => (m && typeof m.petSprite === 'function' ? m : null))
      .catch(() => null);
  }
  return PARTY_UI_MODULE;
}

/* Until petart.js lands, the companion screen's own 20x16 card sprite walks the
 * overworld. It has one pose and a breath rather than four facings and a gait,
 * so this deliberately does not fake a turn by flipping it: a mirrored animal
 * is a different animal, and inventing facings here would be doing petart.js's
 * job badly in the wrong file. It reads as a small animal keeping up. */
async function fallbackArt(animal, colour) {
  const pui = await partyUiModule();
  if (!pui) return null;
  let a = null, b = null;
  try {
    a = pui.petSprite(animal, colour, 0);
    b = pui.petSprite(animal, colour, 1);
  } catch (e) { return null; }
  if (!a || !a.width || !b || !b.width) return null;
  const walk = [a, b, a, b];
  const breathe = [a, b];
  const set = { idle: {}, cast: {} };
  for (const f of ['down', 'up', 'left', 'right']) {
    set[f] = walk;
    set.idle[f] = breathe;
  }
  set.side = set.right;
  set.idle.side = set.idle.right;
  return set;
}

/* An unknown animal must never throw. pets.py is being rewritten underneath
 * this, so a roster entry whose species nobody has drawn yet has to degrade to
 * *something* rather than take the region down. */
async function companionArt(animal, colour, tier, regalia) {
  const art = await petArtModule();
  if (art) {
    try {
      /* THE WORN PIECE GOES THROUGH. petart.js has a whole regalia system —
       * PET_REGALIA, petRegaliaFor(), wear(), REGALIA_SHAPES, thirty-one
       * pieces — and this was its only call site in the app, passing
       * {colour, tier} and nothing else, so no companion in the field has ever
       * worn anything a player earned.
       *
       * It is given the ROW, {id, colour}, not the bare id. petRegaliaFor()
       * reads `worn.colour` when it is handed an object and falls back to the
       * rarity accent when it is not, so passing the string would make a jade
       * collar whatever colour the animal's rank happened to be — which is the
       * one thing regalia.py's authored colours exist to prevent. */
      const set = art.petSprites(animal, { colour, tier, regalia });
      if (set && set.down && set.down.length) {
        // petart.js knows how wide each animal's feet are, and a shadow guessed
        // off a bounding box makes a long animal look pasted onto the ground.
        // Reported alongside the set rather than written into it: that object
        // belongs to the other module.
        let shadow = null;
        if (typeof art.petShadow === 'function') {
          try { shadow = art.petShadow(animal); } catch (e) { shadow = null; }
        }
        return { set, shadow };
      }
    } catch (e) { /* mid-rewrite signature, or an animal it has no shape for */ }
  }
  const set = await fallbackArt(animal, colour);
  return set ? { set, shadow: null } : null;
}

/* The roster keys its art on the ANIMAL, not on the pet id: two of the nine
 * have an id that is not the animal (python/IDIOM is a snake, velociraptor/
 * SICKLE is a raptor), so `sprite` is the field that names the creature. */
function animalOf(row) {
  if (!row) return '';
  const raw = row.sprite || row.animal || row.species || row.id || '';
  return String(raw).toLowerCase().trim();
}

/* The rank the animal walks at. pets.py DOES carry a tier — TUTORIAL, BEGINNER,
 * ADEPT, MASTER, LEGENDARY, HIDDEN, one per catalogue row — and petart.js draws
 * a different animal for each of them: a crest, a halo, a mark on the flank, a
 * warmer rim. Not forwarding it was the whole ladder rendering as COMMON, which
 * is the one thing the return scene cannot survive: the starter dies at the
 * barrow and comes back LEGENDARY, and if the sprite is unchanged the player is
 * simply handed their old pet back. petart.js resolves an unknown spelling to
 * COMMON itself, so passing whatever the row says is safe. */
function tierOf(row) {
  if (!row) return '';
  const raw = row.tier || row.rarity || row.rank || '';
  return String(raw).toUpperCase().trim();
}

/* Found, chosen, and still alive. The third clause is the one that matters:
 * a companion dies at the first boss and comes back later, and a dead animal
 * trotting along behind you would undo that scene entirely. The field it will
 * be spelled with does not exist yet, so every plausible spelling is refused
 * rather than one guessed at. */
function walkable(row) {
  if (!row || typeof row !== 'object') return false;
  if (row.found === false) return false;
  if (!row.active) return false;
  /* `fainted` IS the field, and it was the one spelling not being tested.
   * pets.py's to_dict emits none of `dead`, `lost` or `gone` — the flag for a
   * knocked-out companion is `fainted` (pets.py:3319, "Down, and therefore
   * silent"). So a fainted companion went on trotting behind the player in its
   * standing sprite, which is the one state the whole fainted rig exists to
   * show. `fallen` is kept because pets.py does emit it, and the three
   * speculative spellings are kept because they cost nothing and a roster being
   * rewritten underneath this may yet pick one. */
  if (row.fainted) return false;
  if (row.dead || row.lost || row.fallen || row.gone) return false;
  if (row.alive === false) return false;
  return true;
}

/* The piece this companion has on, as the OBJECT petRegaliaFor() wants —
 * {id, colour} — or null. engine.py merges both rosters onto the row:
 * regalia.py's twenty-four carry an authored colour, quests.py's seven do not
 * and are left to petart's rarity fallback. */
function regaliaOf(row) {
  if (!row || typeof row !== 'object') return null;
  const id = typeof row.regalia === 'string' ? row.regalia.trim() : '';
  if (!id) return null;
  const colour = (typeof row.regalia_colour === 'string'
                  && row.regalia_colour.charAt(0) === '#') ? row.regalia_colour : '';
  return { id, colour };
}

/* ---------------------------------------------------------------- layout
 * Terrain is grown rather than sprinkled: masses first, then a road network,
 * then smoothing. That is what gives the autotiler contiguous regions to find
 * edges in — random per-cell noise would produce nothing but edges.
 */
function buildGrid(region) {
  const seed = hash(region.id);
  const rand = pixel.rng(seed);
  const grid = Array.from({ length: MAP_H }, () => Array(MAP_W).fill(tiles.TERRAIN.GRASS));

  const biome = region.biome;
  const rocky = ['cave', 'mine', 'mountain', 'citadel', 'tower', 'ruins',
                 'dungeon', 'castle', 'wastes', 'arena', 'highland'].includes(biome);
  const wet = ['swamp', 'village', 'grass', 'canopy', 'deepforest', 'forest'].includes(biome);

  // border
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      if (x < 2 || y < 2 || x > MAP_W - 3 || y > MAP_H - 3) {
        grid[y][x] = rocky ? tiles.TERRAIN.CLIFF : tiles.TERRAIN.TREE;
      }
    }
  }

  // Grow contiguous masses rather than sprinkling cells. The autotiler finds
  // edges between regions; per-cell noise would be nothing BUT edges.
  const masses = [];
  masses.push({ code: rocky ? tiles.TERRAIN.STONE : tiles.TERRAIN.TREE,
                coverage: rocky ? 0.13 : 0.17, radius: 2.8 });
  if (wet) masses.push({ code: tiles.TERRAIN.WATER, coverage: 0.10, radius: 3.6 });
  if (rocky) masses.push({ code: tiles.TERRAIN.CLIFF, coverage: 0.09, radius: 2.4 });
  if (biome === 'mine' || biome === 'castle') {
    masses.push({ code: tiles.TERRAIN.LAVA, coverage: 0.04, radius: 2.0 });
  }
  if (['desert', 'wastes', 'arena'].includes(biome)) {
    masses.push({ code: tiles.TERRAIN.SAND, coverage: 0.16, radius: 3.4 });
  }
  masses.forEach((m, i) => {
    tiles.growMasses(grid, { ...m, base: tiles.TERRAIN.GRASS, seed: seed + i * 977 });
    tiles.smoothTerrain(grid, { code: m.code, base: tiles.TERRAIN.GRASS,
                                iterations: 2, seed: seed + i * 131 });
  });

  // roads: always walkable end to end, and they cut through whatever grew
  const midY = Math.floor(MAP_H / 2);
  const midX = Math.floor(MAP_W / 2);
  tiles.carvePath(grid, { x: 2, y: midY }, { x: MAP_W - 3, y: midY },
                  { seed, width: 2, code: tiles.TERRAIN.PATH,
                    bridge: tiles.TERRAIN.BRIDGE });
  tiles.carvePath(grid, { x: midX, y: 3 }, { x: midX, y: MAP_H - 4 },
                  { seed: seed + 1, width: 1, code: tiles.TERRAIN.PATH });
  return grid;
}

function placeMarkers(region, grid, tier) {
  const rand = pixel.rng(hash(region.id) + 99);
  const markers = [];
  const midY = Math.floor(MAP_H / 2);

  const free = (x, y) => (
    x > 2 && y > 2 && x < MAP_W - 3 && y < MAP_H - 3
    && !tiles.isSolid(grid[y][x])
    && !markers.some(m => Math.abs(m.x - x) < 2 && Math.abs(m.y - y) < 2));

  const place = (kind, count, extra = {}) => {
    for (let i = 0; i < count; i++) {
      let x = 0, y = 0, tries = 0;
      do {
        x = 3 + Math.floor(rand() * (MAP_W - 6));
        y = 3 + Math.floor(rand() * (MAP_H - 6));
        tries++;
      } while (tries < 160 && !free(x, y));
      if (!free(x, y)) continue;
      markers.push({ kind, x, y, id: `${region.id}-${kind}-${i}`, ...extra });
    }
  };

  // the settlement sits west of the road, as multi-tile buildings
  const townly = ['village', 'highland', 'arena', 'citadel', 'castle'].includes(region.biome)
    || region.id === 'python_village';
  if (townly) {
    const dry = (bx, by) => {
      for (let dy = 0; dy < 2; dy++) {
        for (let dx = 0; dx < 2; dx++) {
          const code = (grid[by + dy] || [])[bx + dx];
          if (code === undefined) return false;
          // never build on water, lava or a cliff face; a village on a lake
          // reads as a bug rather than as Venice
          if ([tiles.TERRAIN.WATER, tiles.TERRAIN.LAVA, tiles.TERRAIN.BRIDGE,
               tiles.TERRAIN.CLIFF].includes(code)) return false;
        }
      }
      return true;
    };
    for (let i = 0; i < 4; i++) {
      let bx = 5 + (i % 2) * 8;
      let by = midY - 8 + Math.floor(i / 2) * 7;
      let nudges = 0;
      while (!dry(bx, by) && nudges < 24) {
        bx = 4 + Math.floor(rand() * 12);
        by = 4 + Math.floor(rand() * (MAP_H - 10));
        nudges++;
      }
      if (by < 3 || by > MAP_H - 6 || !dry(bx, by)) continue;
      for (let dy = 0; dy < 2; dy++) {
        for (let dx = 0; dx < 2; dx++) grid[by + dy][bx + dx] = tiles.TERRAIN.BUILDING;
      }
      markers.push({ kind: 'building', x: bx, y: by, tier,
                     variant: i % 4, id: `${region.id}-bld-${i}` });
      markers.push({ kind: 'npc', x: bx, y: by + 2, mentor: region.mentor,
                     id: `${region.id}-npc-${i}` });
    }
  }

  place('shrine', 2);
  place('chest', 3);
  place('encounter', 8);
  place('elite', 2);
  for (const m of markers) {
    if (m.kind === 'shrine') grid[m.y][m.x] = tiles.TERRAIN.SHRINE;
    if (m.kind === 'chest') grid[m.y][m.x] = tiles.TERRAIN.CHEST;
  }

  /* THE MARKER CARRIES ITS CREATURE. Without these two fields the draw below
   * falls through to `m.boss || 'titan'`, and every region in the game — all
   * seventeen — put a Hash Titan on its boss tile. The Interviewer's 72x96 map
   * form, 4,859 painted pixels and the largest piece of map art in the boss
   * work, could not be drawn by any route at all. Blank for the six regions
   * with no boss row, which keeps the old fallback for exactly those. */
  /* AND A REGION WITH NO BOSS GETS NO BOSS TILE. Six of the seventeen have no
   * boss row at all — python_village, fields_of_syntax, stringwood_labyrinth,
   * stack_queue_mines, dp_ruins and coding_coliseum — and the marker was placed
   * unconditionally, so each of them drew the `titan` fallback on a tile where
   * nothing lives. A boss on the map is a promise about where the chapter ends;
   * six false ones is worse than the titan that made it visible. */
  if (region.boss_sprite) {
    markers.push({ kind: 'boss', x: MAP_W - 7, y: midY, id: `${region.id}-boss`,
                   boss: region.boss_sprite, colour: region.boss_colour || '' });
  }
  markers.push({ kind: 'exit', x: MAP_W - 3, y: midY, id: `${region.id}-exit-e` });
  markers.push({ kind: 'exit', x: 2, y: midY, id: `${region.id}-exit-w` });
  return markers;
}

/* THE WEATHER USED TO BE A TABLE HERE, AND IT WAS THE WRONG ONE.
 *
 * A biome mapped to one particle style, on forever: this file said a grass
 * region drifted leaves, fx.js said a grass region drifted leaves too but the
 * battle stage said grass was ['lightning','rain','fog'] and rained in every
 * fight. Three tables, three answers, no way for the field the player walked
 * across and the fight they walked into to agree about the sky.
 *
 * Now there is one answer and it comes from gauntlet/weather.py, riding on the
 * region record this module is already handed. load() publishes that record to
 * battlescene.js's registry and _pollSky() reads the condition back out of it,
 * which is the same call the battle stage makes at the same moment — so the two
 * are the same weather by construction rather than by coincidence.
 */
/* THE WEATHER IS COUNTED ON SCREEN, NOT ON THE MAP.
 *
 * This was `PARTICLES_AT_FULL = 70` spread over the WHOLE 768x544 map, and the
 * player has never seen the whole map: he sees viewW*viewH/s^2 of it. So the
 * zoom silently divided the storm by s^2. Measured, same window, pre-zoom scale
 * against the shipped one, at density 1: 1280x800 31.6 -> 17.4 particles inside
 * the frame, 1440x940 21.7 -> 13.7, 1600x1000 25.9 -> 16.7, 1920x1080 20.3 ->
 * 14.8. At a clear sky it is worse in the way that reads: 4.3 -> 1.9 motes at
 * 1280x800, 3.0 -> 1.7 at 1920x1080. One mote is not weather, it is a renderer
 * that stopped, and weather.py's authored `density` was buying about half the
 * drops it used to buy for the same number.
 *
 * (What the previous harness measured — ink COVERAGE — really is unchanged, and
 * that half of the claim is sound: each particle is a world-space rect, so its
 * painted area rises as s^2 by exactly the factor that removes it. The frame
 * keeps the same amount of wet. It just arrives as a third as many, three times
 * fatter, which is a different storm.)
 *
 * So the number is stated as what it always meant: how many are IN THE FRAME at
 * full density. The list over the map is then whatever that costs, which makes
 * the count independent of the zoom AND of the window — before this, a 1280x800
 * window got half again as much rain as a 1920x1080 one for the same sky.
 *
 * NINETEEN IS NOT A TASTE, IT IS THE OLD NUMBER RESTATED. weather.py's
 * densities were authored against seventy over the map at the scale this game
 * was shipping — 3x on the launcher's own 1110x893 canvas, which sees
 * (1110/3 x 893/3) of 768x544, or 26.4% of it. Seventy times 26.4% is 18.5.
 * The floor is the same sum on the same page: a clear sky's fifteen over the
 * map is 3.96 in frame. Both are the shipped weather, held still while the
 * camera moved, rather than a new storm chosen by whoever fixed the bug. */
const ON_SCREEN_AT_FULL = 19;   // particles inside the frame at density 1
const ON_SCREEN_FLOOR = 4;      // a clear sky still has air in it
const PARTICLE_CEILING = 300;   // and a dragged window never buys a swarm
const SKY_POLL_SECONDS = 2;     // how often the field notices the sky changed

export class Overworld {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.region = null;
    this.scene = null;
    this.markers = [];
    this.hero = sprites.heroSprites({});
    // Villagers are drawn from the same rig with a different palette, because a
    // world where every NPC is your own sprite is genuinely confusing to play.
    this.villagers = ['#6a8f5a', '#8f6a5a', '#5a6a8f', '#8f8a5a', '#7a5a8f']
      .map(cloak => sprites.heroSprites({ cloak, tunic: cloak, weapon: null }));
    this.player = { x: 4, y: 17, px: 4 * T, py: 17 * T, facing: 'down',
                    frame: 0, moving: false };
    this.keys = new Set();
    /* The overlay guard's state, declared here so the shape of this object is
     * fixed by the constructor rather than grown by the first frame.
     * `_overlayEl` stays undefined on purpose: that is the sentinel for "never
     * looked", and an empty array is the answer "looked, they are not there". */
    this._overlayEl = undefined;
    this._overlayBox = null;
    this._overlayBoxAt = -1;
    /* The wall-clock hour, sampled in update() and read by draw(). See both. */
    this._hour = new Date().getHours();
    this._clockAcc = 0;
    this.particles = [];
    this.particleStyle = pixel.PARTICLE_STYLE.motes;
    /* The sky over this map: the resolved condition, not a biome default.
     * _applySky() writes it, _pollSky() compares against it, and it is null
     * until the first region is loaded. */
    this.sky = null;
    this._skyAcc = 0;
    /* THE STRIP RUNS OUT. The server ships STRIP_SLOTS (24) five-minute slots
     * — two hours of sky — and nothing refetches it on its own. A player who
     * stands in one region longer than that runs off the end, readSky() clamps
     * to the last slot and says so with `stale`, and the sky is frozen there
     * for as long as they stay. `onSkyStale` is how the field asks its host for
     * a fresher one; `_skyBusy` stops a stale strip firing a request every
     * SKY_POLL_SECONDS while that answer is in flight, and `_skyAsked` — the
     * region plus the epoch of the strip that ran out — stops it asking twice
     * for the same exhausted strip when the answer does not carry a newer one. */
    this.onSkyStale = null;
    this._skyBusy = false;
    this._skyAsked = null;
    this.onEnter = null;
    this.onMove = null;
    this.solvedNodes = new Set();
    this.running = false;
    this.scale = 3;
    this.reducedMotion = false;
    this.time = 0;
    this.tier = 2;
    this.flash = 0;
    this.viewW = 640;
    this.viewH = 420;
    this._objects = [];

    /* The companion. `stateSource` is how this module reads the game state the
     * client already holds — main.js hands it over the same way it hands the
     * chrome to partyui.js — so nothing here fetches anything of its own. Until
     * somebody sets it, or calls setCompanion(), there is no pet and the world
     * renders exactly as it did before this existed. */
    this.stateSource = null;
    this.companion = null;
    this.trail = new Trail(TRAIL_SAMPLES);
    this._companionStamp = '';
    this._companionPushed = undefined;
    this._settleSide = 1;
    this._settleTries = new Int8Array(6);
    this._trailOut = { x: 0, y: 0, exhausted: true };

    /* The apex. Same two ways in as the companion, same refusal to invent a
     * request: `stateSource` is read for a hunt row, or setApex() pushes one.
     * Until an engine puts a field there, `hunt` stays null and every apex path
     * in this file is one null check — see D in apex.js. */
    this.hunt = null;
    this.onApexStage = null;      // (STATE, info) on every change, DORMANT included
    this.onApexContact = null;    // (info) on the frame the client sees it arrive
    this._apexPushed = undefined;
    this._apexStamp = '';
    this._apexStage = 'DORMANT';
    this._apexHeard = false;
    this._apexPayloadSeen = false;
    this._apexPayloadRefused = null;
    this._bearing = { x: 0, y: 0, dist: 0 };
    this._apexPeak = 0;           // the telegraph alpha last painted
    this._wayOutMarks = 0;        // exits marked on the frame edge last frame
    this._apexSortY = 0;
    this._apexUnder = 0;          // times the sort was clamped to keep it behind
    // Where the two kinds of edge mark actually landed, preallocated so the
    // overlay allocates nothing per frame and a harness can look at the pixel.
    this._threatMark = { x: 0, y: 0, edge: '' };
    this._wayOutMark = [{ x: 0, y: 0, edge: '' }, { x: 0, y: 0, edge: '' },
                        { x: 0, y: 0, edge: '' }, { x: 0, y: 0, edge: '' }];

    /* The King. Same two ways in as the companion and the apex, same refusal to
     * invent a request. Until antagonist.py has something to say, `king` is
     * null and this feature costs the frame nothing at all.
     *
     * `_kingWorld` is allocated here, once, and refreshed in place — the
     * Presence reads the live player, the live markers and the live camera out
     * of it, and a fresh object per poll would be an allocation on a path that
     * runs every frame. */
    this.king = null;
    this.onKingSpoke = null;      // (view) on the frame a new thing is said
    this.onKingGone = null;       // (info) when he stops being there, however
    this._kingPushed = undefined;
    this._kingStamp = '';
    this._kingSeq = 0;
    this._kingSortY = 0;
    this._kingUnder = 0;          // times the sort was clamped to keep him behind
    this._kingPanelAlpha = 0;
    this._kingWashPeak = 0;
    this._kingPayloadSeen = false;
    this._kingRefused = null;
    /* The Unmaking. Same two ways in as everything else in this file: a push
     * (`castUnmaking`) or a pull off `stateSource`. Until something casts it,
     * `unmaking` is null and the four call sites below are four null checks.
     *
     * `_heroLook` is the opts dict setEquipment() was last handed. unmakingfx
     * needs it to know which pixels of the rendered hero are trim and which are
     * garb, and asking sprites.js twice for the same answer is how the plate
     * ends up disagreeing with the sprite it is replacing. */
    this.unmaking = null;
    this.onUnmakingDone = null;   // (info) when the spell finishes, however
    this._heroLook = {};
    this._unmakingPushed = undefined;
    this._unmakingStamp = '';
    this._unmakingScreenPeak = 0;
    this._unmakingArcPx = 0;
    this._unmakingPrewarmed = 0;
    this._lookKey = hash('{}').toString(36);
    this._unmakingCompanionAlpha = 1;
    this._unmakingFromState = false;
    this._unmakingSpent = false;
    this._kingWorld = { regionId: '', mapW: MAP_W, mapH: MAP_H, player: this.player,
                        markers: this.markers, solid: (x, y) => this.solid(x, y),
                        viewW: 640, viewH: 420, scale: 3, camX: 0, camY: 0, seq: 0 };

    this._bindInput();
  }

  setEquipment(opts) {
    this.hero = sprites.heroSprites(opts || {});
    /* Kept because the spell needs it. It is the same object sprites.js was
     * given, not a copy and not a re-derivation: unmakingfx asks the rig which
     * hex it painted each glyph in, and a look that has drifted from the one
     * the frames were built from would substitute the wrong pixels.
     *
     * Re-equipping mid-spell is legal and cheap — the plate cache is keyed on
     * the sprite key and the take mask, so the new frames simply build new
     * plates and the old ones age out of the cap. */
    this._heroLook = opts || {};
    /* The cache key for the hero's frames, and the reason re-equipping
     * mid-spell is safe rather than merely legal. unmakingfx keys its plates
     * and contours on the string this file hands it, so a key built only from
     * facing, frame and pose would hand back the plate for the OLD armour after
     * a change of gear — right shape, wrong colours, and nothing would throw.
     * The look goes in the key, so a different look is a different sprite, and
     * the stale plates age out of that module's own cap on their own. */
    this._lookKey = hash(JSON.stringify(this._heroLook || {})).toString(36);
    if (this.unmaking) {
      this.unmaking.look = this._heroLook;
      this._prewarmUnmaking();
    }
  }

  /* Click the companion and it answers.
   *
   * Hit-tested against its drawn position rather than a tile, because it stands
   * between tiles by design — and generously, since a 16px animal on a moving
   * background is a small target and a click that misses feels broken rather
   * than inaccurate. */
  _companionHit(clientX, clientY) {
    const c = this.companion;
    if (!c || c.dead) return false;
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    const s = this.scale || 1;
    // Canvas CSS box -> backing store -> world.
    const bx = (clientX - rect.left) * (this.viewW / rect.width);
    const by = (clientY - rect.top) * (this.viewH / rect.height);
    const wx = bx / s + (this._camX || 0);
    const wy = by / s + (this._camY || 0);
    const dx = wx - c.px;
    const dy = wy - (c.py - 6);          // its body sits above its ground point
    return (dx * dx + dy * dy) <= (14 * 14);
  }

  _bindInput() {
    this.canvas.addEventListener('pointerdown', (e) => {
      if (!this.running) return;
      if (!this._companionHit(e.clientX, e.clientY)) return;
      const c = this.companion;
      // audio throttles repeat clicks itself; this only decides whether the
      // pointer landed on an animal.
      if (this.onCompanionClick) this.onCompanionClick(c);
    });

    window.addEventListener('keydown', (e) => {
      if (!this.running) return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        e.preventDefault();
      }
      this.keys.add(e.key.toLowerCase());
      /* E. He is dismissible and he is not waiting for it. Escape only: the
       * interact key belongs to the world, and a villain who eats the key you
       * press to open a chest is a villain who is in the way. Nothing else
       * about this branch changes — the keypress is not consumed, and with
       * nobody speaking it is one null check. */
      if (e.key === 'Escape' && this.king) this.dismissKing();
      if (e.key === ' ' || e.key === 'Enter') this.interact();
    });
    window.addEventListener('keyup', (e) => this.keys.delete(e.key.toLowerCase()));
    window.addEventListener('blur', () => this.keys.clear());
  }

  load(region, tier = 2, spawn) {
    this.region = region;
    this.tier = tier;
    const grid = buildGrid(region);
    this.markers = placeMarkers(region, grid, tier);
    this.scene = tiles.createScene({
      regionId: region.id, palette: region.palette, tier,
      biome: region.biome, grid,
      decorDensity: 0.05, floraDensity: 0.09,
      avoid: new Set(this.markers.map(m => `${m.x},${m.y}`)),
    });
    const midY = Math.floor(MAP_H / 2);
    const start = spawn || { x: 4, y: midY };
    this.player.x = start.x; this.player.y = start.y;
    this.player.px = start.x * T; this.player.py = start.y * T;
    /* Publish the place, then draw its sky. Publishing is what the battle reads
     * back when the fight starts — one registry, one record, so the fight and
     * the field cannot be in different weather. */
    stagelayer.publishWeather(region);
    this._applySky(stagelayer.resolveSky(region));
    // E: a region change is a discontinuity. The ground the companion was
    // retracing is in another map now, so the buffer goes with it and the
    // animal arrives already standing next to you.
    this._pickSettleSide();
    this._resetCompanion();
    // C. A region change resets the hunt outright. The apex belongs to a map;
    // carrying one across a doorway would mean the exit you took did not work,
    // which is the promise this whole feature is built around.
    this._apexStamp = '';
    this.hunt = null;
    this._apexHeard = false;
    this._setStage('DORMANT');
    this._syncApex();
    /* He does not follow you through a door either. What he said belonged to
     * the field you said it in. */
    this._kingStamp = '';
    this.king = null;
    this._kingPanelAlpha = 0;
    this._kingWashPeak = 0;
    /* And the spell does not follow you through a door either. It was cast on
     * one person standing in one field; carrying it into the next region would
     * mean the door did not work, which is the promise every escape in this
     * file is built on. */
    this.unmaking = null;
    this._unmakingStamp = '';
    this._unmakingFromState = false;
    this._unmakingSpent = false;
    this._unmakingScreenPeak = 0;
    this._unmakingArcPx = 0;
    this._unmakingCompanionAlpha = 1;
    this._kingWorld.regionId = region.id;
    this._kingWorld.markers = this.markers;
    this.resize();
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const w = Math.max(480, Math.floor(rect.width));
    const h = Math.max(320, Math.floor(rect.height));
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.imageSmoothingEnabled = false;
    this.viewW = w; this.viewH = h;
    this.scale = fieldScale(w, h);
    this._overlayBoxAt = -1;   // the row _overlayGuard measures just moved
    /* THE STORM IS REBUILT HERE OR IT IS NEVER REBUILT. resize() is the only
     * thing in this file that changes `scale`, and the particle count is a
     * function of scale — see _particleCount. load() runs _applySky() before
     * this line has ever executed, so without this the field would spend its
     * whole life with the count the constructor's 3x/640x480 guess bought.
     *
     * Only when the number actually MOVES. makeParticles draws from one seeded
     * stream — hash(key + mapWidth) — so the first N are the same N whatever
     * the count is, and changing it adds or drops drops off the TAIL rather
     * than teleporting the storm; but a window dragged a pixel at a time should
     * still not be allocating a list sixty times a second. */
    if (this.particles) {
      const dens = this.sky && typeof this.sky.density === 'number'
        ? this.sky.density : 0.22;
      if (this._particleCount(dens) !== this.particles.length) this._applySky(this.sky);
    }
  }

  start() {
    if (this.running) return;
    this.running = true;
    let last = performance.now();
    const loop = (now) => {
      if (!this.running) return;
      // rAF stamps a frame with the time the frame STARTED, which can predate
      // the performance.now() taken a moment ago in start(). Without the floor
      // the first dt is negative, this.time goes with it, and every animation
      // that indexes a frame array by time reads off the front of it.
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      this.update(dt);
      this.draw();
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }

  stop() {
    this.running = false;
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  /* A FOOTSTEP, ON THE GROUND THE FOOT IS ACTUALLY ON.
   *
   * TWO DEFECTS WERE HERE AND THEY ARE DIFFERENT DEFECTS.
   *
   * 1. THE SOUND WAS WRONG EVERYWHERE. It played audio.sfx('move') — a 22ms
   *    cursor blip — for every step on every surface. audio.js has seven
   *    authored materials (stone, grass, snow, ash, water, wood, sand) reached
   *    by audio.footstep(), which takes the terrain CODE directly through its
   *    FOOTSTEP_CODE table, and nothing in the tree called it. Snow sounded
   *    like a menu.
   *
   * 2. ABOUT 55% OF FOOTFALLS WERE SILENT, IRREGULARLY. The gate was
   *    `Math.floor(this.time * 6) % 2 === 0` — a gate on the WALL CLOCK, not on
   *    the step. It opens and shuts in sixth-of-a-second windows regardless of
   *    when a foot lands, so whether you heard a step depended on the phase you
   *    happened to walk in. Holding a direction gave an irregular limp.
   *
   * The cadence is now DISTANCE, which is what a footfall actually is. A step
   * is one tile; a stride is two, so a footfall lands every 2*T world pixels.
   * At speed 112 that is 3.5 a second — a brisk walk, and half the 7/s that
   * emitting on every tile would give. Distance rather than time also means a
   * speed change carries the cadence with it: the snow zone's skate irons are
   * 1.35x, and boots that make you faster should make you louder, not the same
   * noise at wider spacing.
   */
  _footfall() {
    const p = this.player;
    this._strideAccum = (this._strideAccum || 0) + T;
    if (this._strideAccum < T * 2) return false;
    this._strideAccum = 0;
    if (!this.scene) return false;
    const row = this.scene.grid[p.y];
    if (!row) return false;
    try {
      // The terrain CODE, not a name: audio.footstep resolves it through its
      // own table, so this file does not need a second copy of that mapping.
      return audio.footstep(row[p.x], { biome: this.scene.biome || '' });
    } catch (e) { return false; }   // a footstep is never load-bearing
  }

  solid(x, y) {
    if (!this.scene) return true;
    if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return true;
    return tiles.isSolid(this.scene.grid[y][x]);
  }

  update(dt) {
    this.time += dt;
    const p = this.player;
    const targetX = p.x * T, targetY = p.y * T;
    const speed = 112;

    if (Math.abs(p.px - targetX) > 0.5 || Math.abs(p.py - targetY) > 0.5) {
      p.moving = true;
      const dx = targetX - p.px, dy = targetY - p.py;
      const dist = Math.hypot(dx, dy) || 1;
      const step = Math.min(dist, speed * dt);
      p.px += (dx / dist) * step;
      p.py += (dy / dist) * step;
    } else {
      p.px = targetX; p.py = targetY;
      p.moving = false;
      let nx = p.x, ny = p.y, facing = p.facing;
      if (this.keys.has('arrowup') || this.keys.has('w')) { ny--; facing = 'up'; }
      else if (this.keys.has('arrowdown') || this.keys.has('s')) { ny++; facing = 'down'; }
      else if (this.keys.has('arrowleft') || this.keys.has('a')) { nx--; facing = 'left'; }
      else if (this.keys.has('arrowright') || this.keys.has('d')) { nx++; facing = 'right'; }
      if (nx !== p.x || ny !== p.y) {
        p.facing = facing;
        if (!this.solid(nx, ny)) {
          p.x = nx; p.y = ny;
          p.moving = true;
          this._footfall();
          this.checkTile();
          if (this.onMove) this.onMove(p.x, p.y);
        }
      }
    }
    p.frame = (p.moving && !this.reducedMotion)
      ? Math.floor(this.time * 8) % 4 : 0;
    if (this.flash > 0) this.flash -= dt * 3;
    this._updateCompanion(dt);
    this._updateApex(dt);
    this._updateKing(dt);
    /* After the movement branch, not before it. The order is the guarantee: by
     * the time a single line of the spell has run this frame, the player's step
     * has already been taken. */
    this._updateUnmaking(dt);
    /* Once a second, not once a frame: the day/night tint changes on the hour
     * and reading a Date twice a minute is already three thousand times more
     * often than it can possibly matter. draw() reads `_hour` and never the
     * clock — see the tint block there. */
    this._clockAcc += dt;
    if (this._clockAcc >= 1) { this._clockAcc = 0; this._hour = new Date().getHours(); }
    /* And the sky, on the same principle: the weather changes on a five-minute
     * grid, so asking twice a second would be three hundred times more often
     * than it can possibly matter. This is the line that makes it come and go
     * while the player is standing still — without it the field would only ever
     * change weather at a doorway. */
    this._skyAcc += dt;
    if (this._skyAcc >= SKY_POLL_SECONDS) {
      this._skyAcc = 0;
      this._pollSky();
    }
    /* REDUCED MOTION STOPS THE WEATHER IN BOTH RENDERERS OR IN NEITHER.
     * The battle backdrop freezes its rain, snow and fireballs by drawing them
     * at a constant t (see drawScene), and a field that kept stepping while the
     * fight it leads into stood still would be the same disagreement this whole
     * feature exists to close — walking through seventy moving raindrops into a
     * bone-dry room. The particles are still BUILT and still drawn: what stops
     * is the motion, which is the only thing the setting is about. */
    if (!this.reducedMotion) {
      pixel.stepParticles(this.particles, this.particleStyle, MAP_W * T, MAP_H * T, dt);
    }
  }

  /* Fall the condition's particles over the map.
   *
   * `density` is the same 0..1 the battle backdrop scales its rain off, so a
   * drizzle is thin in both places. A clear sky keeps a few motes: air with
   * nothing whatever in it reads as a renderer that stopped, not as a fine day.
   */
  _applySky(sky) {
    this.sky = sky || null;
    const style = (sky && pixel.PARTICLE_STYLE[sky.particle])
      || pixel.PARTICLE_STYLE.motes;
    const dens = sky && typeof sky.density === 'number' ? sky.density : 0.22;
    this.particleStyle = style;
    /* Keyed by region AND condition, so the field visibly re-seeds when the
     * weather turns rather than sliding one set of pixels into another. */
    this.particles = pixel.makeParticles(
      ((sky && sky.region) || (this.region && this.region.id) || 'map')
        + ':' + ((sky && sky.condition) || 'clear'),
      MAP_W * T, MAP_H * T,
      this._particleCount(dens));
    return this;
  }

  /* How many to make over the map so that the authored number lands inside the
   * frame. `share` is the fraction of the map the camera can see, and it is the
   * whole of the zoom's effect on the weather: at scale 4 on a 1110x893 canvas
   * it is 14.8%, so twenty-six on screen costs 176 over the map.
   *
   * Guarded rather than trusted, because load() calls _applySky() BEFORE
   * resize() has measured anything — the scale is still the constructor's 3 and
   * the view is still 640x480 at that moment — and resize() rebuilds the list
   * the instant it knows better. A zero here would divide by zero and hand
   * makeParticles a NaN count, which is an empty sky forever. */
  _particleCount(dens) {
    const s = this.scale > 0 ? this.scale : 1;
    const vw = this.viewW > 0 ? this.viewW : 640;
    const vh = this.viewH > 0 ? this.viewH : 480;
    const share = Math.min(1, (vw / s) * (vh / s) / (MAP_W * T * MAP_H * T));
    const want = Math.max(ON_SCREEN_FLOOR, ON_SCREEN_AT_FULL * dens);
    return Math.min(PARTICLE_CEILING, Math.max(12, Math.round(want / share)));
  }

  /* Has the sky turned since the last look? Cheap: one index into a strip the
   * server already sent. Nothing is rebuilt unless the condition's NAME
   * changed, so standing in one spell of rain for half an hour allocates
   * nothing at all. */
  _pollSky() {
    if (!this.region) return;
    let next = stagelayer.resolveSky(this.region);
    if (!next) return;
    /* THE FLAG IS ACTED ON, NOT MERELY RETURNED. `stale` means the strip we
     * hold does not cover this moment any more — the player has been standing
     * here for over two hours without anything fetching the game state — and
     * indexing its clamped end every two seconds forever is how a sky stops
     * being weather. Ask the host for a fresher record, once per exhausted
     * strip, then READ AGAIN: a host that already holds a newer one answers
     * synchronously, and applying the stale answer we came in with would undo
     * the refresh on the very frame it arrived.
     *
     * "Once per exhausted strip" is keyed by REGION AND EPOCH, not by epoch
     * alone: every region's strip is anchored to the same five-minute grid, so
     * two records fetched in the same moment carry the same `epoch`, and an
     * epoch-only key would let a strip that ran out in one region silence the
     * ask in the next one the player walked into. */
    const asked = this.region.id + '|'
      + ((this.region.weather && this.region.weather.epoch) || 0);
    if (next.stale && this.onSkyStale && !this._skyBusy && this._skyAsked !== asked) {
      this._skyAsked = asked;
      this._skyBusy = true;
      /* A host that already holds a fresher record answers on the spot and
       * returns nothing; a host that has to fetch returns a promise. Only the
       * second kind has anything in flight, and only the second kind should
       * hold `_skyBusy` — clearing it on a microtask after a synchronous answer
       * would leave the flag stuck for the rest of any caller that does not
       * yield, and a field that can never ask again is the bug this is here to
       * repay. */
      let answer = null;
      try { answer = this.onSkyStale(); } catch (e) { answer = null; }
      if (answer && typeof answer.then === 'function') {
        answer.then(() => { this._skyBusy = false; },
                    () => { this._skyBusy = false; });
      } else {
        this._skyBusy = false;
      }
      next = stagelayer.resolveSky(this.region) || next;
    }
    if (this.sky && next.condition === this.sky.condition) return;
    this._applySky(next);
  }

  checkTile() {
    const m = this.markers.find(mk => mk.x === this.player.x && mk.y === this.player.y);
    if (!m) return;
    if (m.kind === 'encounter' || m.kind === 'elite') {
      if (this.solvedNodes.has(m.id)) return;
      this.flash = 1;
      audio.sfx('select');
      if (this.onEnter) this.onEnter(m);
    }
  }

  interact() {
    const p = this.player;
    const dirs = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
                   side: [1, 0] };
    const [dx, dy] = dirs[p.facing] || [0, 1];
    for (const [x, y] of [[p.x, p.y], [p.x + dx, p.y + dy]]) {
      const m = this.markers.find(mk => mk.x === x && mk.y === y);
      if (m && this.onEnter) {
        if ((m.kind === 'encounter' || m.kind === 'elite')
            && this.solvedNodes.has(m.id)) continue;
        audio.sfx('select');
        this.onEnter(m);
        return;
      }
    }
  }

  /* ------------------------------------------------------------- companion
   *
   * Two ways in, because the state field this reads is being rewritten as this
   * ships. The pull path is `stateSource`, a function returning the client's
   * own state object; the push path is setCompanion(row). Neither invents a
   * request. Both accept a row and neither requires one.
   */

  /* Push. Pass null to say "nobody walks with me"; pass undefined to hand the
   * decision back to stateSource. */
  setCompanion(row) {
    this._companionPushed = row === undefined ? undefined : (row || null);
    this._syncCompanion();
  }

  /* Pull. What the state ACTUALLY carries today is `state.pets`: the array
   * pets.catalogue() ships, one row per animal, each with `found`, `active`,
   * `id`, `sprite`, `colour`, `name` and `species`. There is no separate
   * `state.companion` field and no per-pet alive flag yet, so this reads
   * `pets` and refuses anything that is not found, not chosen, or marked dead
   * under any of the spellings that rewrite might land on.
   *
   * ACTIVE_LIMIT is two, but only the first walks. A line of animals behind
   * the player is a parade, and the point of the system is that you chose one
   * to walk with. */
  _activeCompanionRow() {
    if (this._companionPushed !== undefined) {
      return walkable(this._companionPushed) ? this._companionPushed : null;
    }
    if (typeof this.stateSource !== 'function') return null;
    let s = null;
    try { s = this.stateSource(); } catch (e) { return null; }
    if (!s) return null;
    const pets = Array.isArray(s.pets) ? s.pets : (Array.isArray(s) ? s : null);
    if (!pets) return null;
    for (let i = 0; i < pets.length; i++) {
      if (walkable(pets[i])) return pets[i];
    }
    return null;
  }

  /* Build the rig only when the animal actually changed. Art arrives from a
   * dynamic import, so `art` is null for a frame or two and the draw path
   * simply skips it — an animal that pops in a moment late is invisible; a
   * world screen that throws while waiting is not. */
  _syncCompanion() {
    const row = this._activeCompanionRow();
    const animal = animalOf(row);
    const colour = (row && row.colour) || '#9b96b8';
    const tier = tierOf(row);
    // The tier is IN the stamp, not just in the build call. The starter that
    // comes back is the same id, the same animal and the same colour at a new
    // rank, so a stamp without the tier would decide nothing had changed and
    // keep drawing the old frames forever.
    /* The worn piece is in the stamp for exactly the reason the tier is, one
     * comment up: _syncCompanion() returns early when the stamp has not moved,
     * so a player who puts a collar on an animal whose id, species, colour and
     * rank are all unchanged would keep the old cached frames for the rest of
     * the session. */
    const worn = regaliaOf(row);
    const stamp = row
      ? `${row.id || animal}|${animal}|${colour}|${tier}|${worn ? worn.id + (worn.colour || '') : ''}`
      : '';
    if (stamp === this._companionStamp) return;
    this._companionStamp = stamp;
    if (!row) { this.companion = null; return; }

    const c = {
      row, animal, colour, tier,
      px: this.player.px, py: this.player.py,
      facing: 'down', frame: 0, walked: 0,
      moving: false, speed: 0, still: SETTLE_AFTER + 1, settled: true,
      art: null, shadowR: 6, shadowRY: 3, sortY: 0, overHero: false,
      // set by the apex pass below; false whenever nothing is hunting, which is
      // what keeps a world with no apex byte-identical to one without this code
      alert: false,
      // px the last cell-clearance correction moved it, so the harness can put
      // a number on how big the correction actually is rather than take the
      // word "small" for it.
      nudged: 0,
    };
    this.companion = c;
    this._pickSettleSide();
    this._resetCompanion();
    companionArt(animal, colour, tier, worn).then((built) => {
      if (this.companion !== c || !built) return;   // swapped out mid-import
      c.art = built.set;
      const sh = built.shadow;
      if (sh && sh.rx > 0) { c.shadowR = sh.rx; c.shadowRY = sh.ry || 3; }
      else {
        const probe = built.set && built.set.down && built.set.down[0];
        if (probe && probe.width) c.shadowR = Math.max(4, Math.round(probe.width / 3));
      }
    }).catch(() => { /* quiet: no art, no companion drawn */ });
  }

  /* Which shoulder it prefers, hashed from the region and the animal rather
   * than rolled. Stable across frames, across reloads and across two people
   * playing the same seed, and no random call anywhere near a draw. */
  _pickSettleSide() {
    const animal = this.companion ? this.companion.animal : '';
    const region = (this.region && this.region.id) || '';
    this._settleSide = (hash(region + '|' + animal) & 1) ? 1 : -1;
  }

  /* E. Any discontinuity — load, fast travel, an exit taken, a spawn override.
   * The buffer is the only memory this system has, so clearing it and placing
   * the animal alongside is the whole of "arrives with you". Without it the
   * companion would retrace a path across a map that no longer exists. */
  _resetCompanion() {
    const p = this.player;
    this.trail.reset(p.px, p.py);
    const c = this.companion;
    if (!c) return;
    c.still = SETTLE_AFTER + 1;
    const out = this._trailOut;
    if (this._settleTarget(out)) { c.px = out.x; c.py = out.y; }
    else { c.px = p.px; c.py = p.py; }
    c.facing = p.facing === 'side' ? 'right' : p.facing;
    c.moving = false; c.speed = 0; c.walked = 0; c.frame = 0; c.settled = true;
  }

  /* B. Somewhere to stand that is not on top of anything. Solid tiles are out
   * for the obvious reason; marker tiles are out because a shrine, a chest, an
   * NPC or an encounter is a thing the player presses a button at and an animal
   * sitting on it hides both the glyph and the prompt. */
  _settleFree(tx, ty) {
    if (this.solid(tx, ty)) return false;
    for (let i = 0; i < this.markers.length; i++) {
      const m = this.markers[i];
      if (m.kind === 'building') {
        if (tx >= m.x && tx <= m.x + 1 && ty >= m.y && ty <= m.y + 1) return false;
      } else if (m.x === tx && m.y === ty) return false;
    }
    return true;
  }

  /* Beside you, not in you. Directly behind is the tile a player backtracks
   * onto, so it is the last resort rather than the first choice; the shoulder
   * reads as company. Every candidate is perpendicular to your facing or
   * directly behind it, which is what keeps the animal off the tile in front of
   * you — the one interact() is about to talk to — by construction rather than
   * by a check that could be edited away. */
  _settleTarget(out) {
    const p = this.player;
    const f = FACE_VEC[p.facing] || FACE_VEC.down;
    const fx = f[0], fy = f[1];
    const o = this._settleTries;
    o[0] = -fy * this._settleSide; o[1] = fx * this._settleSide;   // preferred shoulder
    o[2] = fy * this._settleSide;  o[3] = -fx * this._settleSide;  // the other one
    o[4] = -fx;                    o[5] = -fy;                     // last resort: behind
    for (let i = 0; i < 6; i += 2) {
      const ox = o[i], oy = o[i + 1];
      const tx = p.x + ox, ty = p.y + oy;
      if (!this._settleFree(tx, ty)) continue;
      out.x = p.px + ox * SETTLE_PX;
      out.y = p.py + oy * SETTLE_PX;
      return true;
    }
    return false;   // boxed in; stay on the walked path, which is always legal
  }

  /* B, enforced rather than hoped for. Retracing keeps the animal behind you
   * almost always, but three things still walk it into the cell you are
   * standing in: a hard reversal, where the ground 18px back along the trail is
   * the ground you are on now; the walk into the settle pose, which crosses
   * your feet to reach your shoulder; and the first stride after a load. It is
   * drawn under the hero when that happens, so it is never a visual mess — but
   * "the pet is standing on me" is a thing a player can see in one frame of a
   * turn, and a follower whose one promise is that it will not get in your way
   * should not need the z-sort to cover for it.
   *
   * The correction is the smallest AXIS-ALIGNED nudge that leaves the cell,
   * applied after the walk and never fed back into gait or facing: it is a
   * correction, not locomotion. Axis-aligned rather than radial because the
   * settle pose is a deliberate 13px — under one tile — on a single axis, and a
   * radial push would move an animal that was already exactly where it should
   * be. A nudge onto a solid tile is refused and the other direction tried; if
   * the player is standing in a doorway with rock on both sides, the animal
   * stays where it is, because being underfoot for two frames beats being
   * inside a cliff. */
  _clearOfThePlayer(c) {
    const p = this.player;
    const pcx = p.px + T / 2, pcy = p.py + T / 2;
    /* Two cells, not one. Mid-step the player HAS two: the one his sprite is
     * standing on, floor((px+8)/T), and p.x/p.y, the one he has already
     * committed to and that checkTile() and interact() answer for. They are the
     * same cell at rest and a domino while he walks, and on the first frames of
     * a REVERSAL the tile he has committed to is exactly the tile the animal
     * trailing him is standing in. Clearing only one of the two leaves that
     * case behind, which is what the measurement showed. */
    // Scalars, not a pair of {x,y}: this runs every frame of every walk, and a
    // fresh object per frame in the update path is what scripts/verify counts.
    const px0 = Math.floor(pcx / T), py0 = Math.floor(pcy / T);
    const loX = px0 < p.x ? px0 : p.x, hiX = px0 > p.x ? px0 : p.x;
    const loY = py0 < p.y ? py0 : p.y, hiY = py0 > p.y ? py0 : p.y;
    const ccx = c.px + T / 2, ccy = c.py + T / 2;
    const cx = Math.floor(ccx / T), cy = Math.floor(ccy / T);
    c.nudged = 0;
    if (cx < loX || cx > hiX || cy < loY || cy > hiY) return;

    const f = FACE_VEC[p.facing] || FACE_VEC.down;
    /* Four ways out — past either edge of the occupied run on either axis — and
     * the SMALLEST of them wins. Choosing by "which way is it already leaning"
     * was measurably wrong: on the long side of the run it produced a 21px
     * correction, a whole tile of pop on an animal that is supposed to be
     * walking. The smallest legal exit is a few pixels, which at this scale is
     * the sprite settling rather than the sprite jumping.
     *
     * Ties go BACKWARDS: that is where a follower belongs, and it is the one
     * direction that cannot be the tile interact() is about to talk to. Fixed
     * iteration order and no rolls, so two runs of the same walk correct
     * identically. */
    let bestAxis = -1, bestPos = 0, bestD = Infinity, bestBack = false;
    for (let k = 0; k < 4; k++) {
      const axis = k >> 1, sign = (k & 1) ? -1 : 1;
      const tx = axis === 0 ? (sign > 0 ? hiX + 1 : loX - 1) : cx;
      const ty = axis === 1 ? (sign > 0 ? hiY + 1 : loY - 1) : cy;
      if (this.solid(tx, ty)) continue;
      // One pixel past the edge of the run, so the correction is as small as it
      // can be and still be true.
      const pos = axis === 0
        ? (sign > 0 ? (hiX + 1) * T : loX * T - 1)
        : (sign > 0 ? (hiY + 1) * T : loY * T - 1);
      const d = Math.abs((axis === 0 ? ccx : ccy) - pos);
      const back = ((axis === 0 ? -f[0] : -f[1]) === sign);
      if (d < bestD - 0.001 || (back && !bestBack && d < bestD + 0.001)) {
        bestAxis = axis; bestPos = pos; bestD = d; bestBack = back;
      }
    }
    if (bestAxis === 0) { c.px = bestPos - T / 2; c.nudged = bestD; return; }
    if (bestAxis === 1) { c.py = bestPos - T / 2; c.nudged = bestD; return; }

    // Boxed in on both sides: leave it. Underfoot for two frames beats inside a
    // cliff, and the draw path already sorts it under the hero.
  }

  _updateCompanion(dt) {
    this._syncCompanion();
    const c = this.companion;
    const p = this.player;
    const tr = this.trail;
    // No pet: the trail still tracks, so an animal found mid-region has ground
    // to stand on the moment it appears. Nothing else happens and nothing is
    // drawn.
    if (!c) { tr.push(p.px, p.py); return; }

    const jx = p.px - tr.lastX, jy = p.py - tr.lastY;
    if (jx * jx + jy * jy > TELEPORT_PX * TELEPORT_PX) { this._resetCompanion(); return; }
    tr.push(p.px, p.py);

    c.still = p.moving ? 0 : c.still + dt;

    const out = this._trailOut;
    let settling = c.still > SETTLE_AFTER && this._settleTarget(out);
    if (!settling) {
      tr.back(COMPANION_LAG, out);
      /* The buffer holds less than a lag's worth of ground — the first strides
       * after a load or a teleport. Standing still here and letting the trail
       * grow past it was wrong, and measurably: for the ten frames it takes to
       * walk 18px, the player walks straight THROUGH the animal he left on his
       * shoulder, and that is the first thing anyone sees on entering a region.
       *
       * Holding the settle pose instead keeps it beside you until there is real
       * ground to retrace — which is exactly what it was doing the frame before
       * you pressed a key, so there is no pop into it either. */
      if (out.exhausted) {
        if (this._settleTarget(out)) settling = true;
        else { out.x = c.px; out.y = c.py; }
      }
    }
    c.settled = settling;

    const dx = out.x - c.px, dy = out.y - c.py;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const fromX = c.px, fromY = c.py;
    if (dist > 0.05) {
      // Faster the further behind it is, so it holds station on a straight run
      // and closes a corner without teleporting. The step is clamped to the
      // remaining distance, so it cannot overshoot and oscillate.
      const speed = Math.min(COMPANION_MAX_SPEED, 52 + dist * 14);
      const step = Math.min(dist, speed * dt);
      c.px += (dx / dist) * step;
      c.py += (dy / dist) * step;
    }

    const mx = c.px - fromX, my = c.py - fromY;
    const moved = Math.sqrt(mx * mx + my * my);
    c.speed = dt > 0 ? moved / dt : 0;
    c.moving = c.speed > COMPANION_MOVING;

    // D. Its own heading, never the player's. Walking left across your path
    // while you look north means it faces left. The asymmetric thresholds are
    // hysteresis: without them a near-diagonal step flickers the sprite between
    // two facings every frame.
    if (moved > 0.08) {
      const h = Math.abs(mx), v = Math.abs(my);
      const wasH = c.facing === 'left' || c.facing === 'right';
      if (h > v * (wasH ? 0.75 : 1.3)) c.facing = mx < 0 ? 'left' : 'right';
      else if (v > h * (wasH ? 1.3 : 0.75)) c.facing = my < 0 ? 'up' : 'down';
    }

    /* B. The telegraph this world already had, and by some distance the best
     * one available: your animal knows first.
     *
     * It goes rigid and looks at the thing. Nothing else changes — it still
     * retraces, it still settles on your shoulder, it still cannot block a
     * step — because a companion that starts making decisions during a chase
     * is a companion that gets in your way at the worst possible moment. One
     * head turn and one mark over it, and only while it is standing still, so
     * a walk is never interrupted by the animal craning over its shoulder.
     *
     * This is also the only telegraph that works when the apex is behind you
     * and off screen and you are looking the other way, which is exactly when
     * a player most needs to be told. */
    const hunt = this.hunt;
    c.alert = !!(hunt && hunt.embodied && hunt.alpha > 0.004
                 && (hunt.state === 'TRACKING' || hunt.state === 'CLOSING'
                     || hunt.state === 'ENGAGED'));
    if (c.alert && !c.moving) {
      const bx = hunt.px - c.px, by = hunt.py - c.py;
      if (Math.abs(bx) > Math.abs(by)) c.facing = bx < 0 ? 'left' : 'right';
      else if (by !== 0) c.facing = by < 0 ? 'up' : 'down';
    }

    // The gait advances on ground covered rather than on the clock, so the feet
    // match the speed instead of skating. Wrapped at a multiple of every frame
    // count we use, so a long session cannot drift the index or lose precision.
    c.walked = (c.walked + moved) % (COMPANION_STRIDE * 720);
    c.frame = this.reducedMotion ? 0 : Math.floor(c.walked / COMPANION_STRIDE);

    // Last, and deliberately after the gait: the nudge out of the player's cell
    // is a correction to where it is drawn, not a step it took, so it must not
    // turn the sprite or advance a foot.
    this._clearOfThePlayer(c);
  }

  /* ------------------------------------------------------------------ apex
   *
   * gauntlet/hunters.py owns the hunt. apex.js owns mirroring it and the art.
   * What lives HERE is the three things that are properly this file's
   * business: reading the row out of the state the client already holds,
   * ticking the mirror against this map's walls, and the sort rule that keeps
   * forty-eight pixels of monster off the player, off a marker and off the
   * door. If you are looking for the escape guarantees they are in hunters.py,
   * stated as arithmetic, and this file does not get a vote on them.
   */

  /* Push. Pass null for "nothing is hunting"; pass undefined to hand the
   * decision back to stateSource. Symmetrical with setCompanion by design —
   * main.js already knows this shape. The row is a `Hunt.to_dict()`. */
  setApex(row) {
    this._apexPushed = row === undefined ? undefined : (row || null);
    this._syncApex();
  }

  /* Pull. Reads state.hunt + state.apexes — see the contract written out in
   * apex.js, taken from hunters.py rather than invented. A stateSource that
   * throws mid-rewrite, a field that does not exist yet, a row for another
   * region: all three are "nothing is hunting", silently, and the world renders
   * exactly as it did before this feature existed. */
  _apexState() {
    if (this._apexPushed !== undefined) {
      return this._apexPushed ? { hunt: this._apexPushed } : null;
    }
    if (typeof this.stateSource !== 'function') return null;
    try { return this.stateSource(); } catch (e) { return null; }
  }

  _syncApex() {
    if (!this.region || !this.scene) { this.hunt = null; return; }
    const st = this._apexState();
    let view = null;
    try { view = apexmod.resolveHunt(st, this.region.id); } catch (e) { view = null; }

    // the static table, adopted once if the client is carrying it
    if (!this._apexPayloadSeen && st && st.apex_payload) {
      this._apexPayloadSeen = true;
      try { this._apexPayloadRefused = apexmod.adoptPayload(st.apex_payload).refused; }
      catch (e) { /* a half-built payload is not a reason to stop drawing */ }
    }

    const stamp = apexmod.stampOf(view);
    if (!view) {
      this._apexStamp = '';
      this.hunt = null;
      this._setStage('DORMANT');
      return;
    }
    if (stamp !== this._apexStamp) {
      this._apexStamp = stamp;
      this.hunt = new apexmod.Pursuit(view, {
        regionId: this.region.id,
        mapW: MAP_W, mapH: MAP_H,
        player: this.player,
        markers: this.markers,
        solid: (x, y) => this.solid(x, y),
      });
      this._apexHeard = false;
    }
    // Every frame, and deliberately: this is a mirror. A new row is the
    // authority arriving, and the only thing that rebuilds the object is a
    // different creature in a different place.
    this.hunt.sync(view);
  }

  _setStage(stage) {
    if (stage === this._apexStage) return;
    this._apexStage = stage;
    if (!this.onApexStage) return;
    const h = this.hunt;
    // One object per STATE CHANGE — a handful in a whole hunt — not one per
    // frame. The per-frame paths in this file allocate nothing; this is not one.
    try {
      this.onApexStage(stage, h ? {
        state: stage, name: h.view.name, id: h.view.apexId,
        element: h.view.element, colour: h.view.colour,
        lesson: h.view.lesson, tell: h.view.tell,
        regionId: h.view.regionId,
        tiles: Number.isFinite(h.tiles) ? h.tiles : null,
        // hunters.py prints a countdown at CLOSING. The canvas does not — a
        // number is the one thing the wordless telegraph is deliberately not —
        // so it is handed to the region card, which is text and is where a
        // number belongs.
        seconds: apexmod.TELEGRAPH[stage] && apexmod.TELEGRAPH[stage].countdown
          && Number.isFinite(h.tiles)
          ? Math.max(0, Math.round((h.tiles * T - apexmod.CONTACT_PX)
                                   / apexmod.STATE_SPEED.CLOSING * 10) / 10)
          : null,
      } : { state: stage, regionId: this.region ? this.region.id : '' });
    } catch (e) { /* a listener that throws is not this module's problem */ }
  }

  _updateApex(dt) {
    this._syncApex();
    const h = this.hunt;
    if (!h) return;                       // D. one null check and out
    const event = h.update(dt, this.time);
    if (h.state !== this._apexStage) {
      // One sting, on the frame it stops being a rumour. Not a siren, and not
      // one per state: hunters.py's own telegraph table does the rest with
      // pacing, and pacing is not a sound effect.
      if (h.state === 'CLOSING' && !this._apexHeard) {
        this._apexHeard = true;
        try { audio.sfx('boss'); } catch (e) { /* muted, or no context yet */ }
      }
      if (h.state === 'DORMANT' || h.state === 'SPENT') this._apexHeard = false;
      this._setStage(h.state);
    }
    if (event === 'contact' && this.onApexContact) {
      // The ENGINE decides whether a fight starts. This says the client saw it
      // arrive, on the frame it arrived, so a caller can react on the right
      // frame instead of on the next poll.
      this.flash = 1;
      try {
        this.onApexContact({
          name: h.view.name, id: h.view.apexId, element: h.view.element,
          colour: h.view.colour, regionId: h.view.regionId,
          x: Math.floor((h.px + T / 2) / T), y: Math.floor((h.py + T / 2) / T),
        });
      } catch (e) { /* same */ }
    }
  }

  /* ----------------------------------------------------------------- the King
   *
   * gauntlet/antagonist.py decides when he speaks, which occasion it was, which
   * of five registers he is in and what the words are. This file does four
   * things with that and nothing else: reads the row, builds a Presence, gives
   * it a place in the y-sort, and takes it away again. The contract it codes
   * against is written out at the top of kingui.js, taken from antagonist.py's
   * own tables rather than invented — and every degrade is silent, so a missing
   * field, a row for another region, a row with no words or a stateSource that
   * throws mid-rewrite all mean "he has nothing to say" and the world renders
   * exactly as it did before this existed.
   *
   * THE RULE THIS WHOLE SECTION EXISTS FOR: he never blocks. There is no state
   * in which the player owes him a keypress, nothing here touches update()'s
   * movement branch, solid(), checkTile() or interact(), and a payload that
   * ever asks to be modal has the flag dropped and recorded rather than
   * honoured. He is weather.
   */

  /* Push. Pass null for silence; pass undefined to hand the decision back to
   * stateSource. */
  setKing(row) {
    this._kingPushed = row === undefined ? undefined : (row || null);
    this._syncKing();
  }

  /* E. Dismissible. Returns whether there was anything to dismiss, so a caller
   * can decide whether the key it just spent belonged to somebody else. */
  dismissKing() {
    if (!this.king) return false;
    return this.king.dismiss();
  }

  _kingState() {
    if (this._kingPushed !== undefined) {
      return this._kingPushed ? { king: this._kingPushed } : null;
    }
    if (typeof this.stateSource !== 'function') return null;
    try { return this.stateSource(); } catch (e) { return null; }
  }

  _syncKing() {
    if (!this.region || !this.scene) { this.king = null; return; }
    const st = this._kingState();
    let view = null;
    try { view = kingui.resolveKing(st, this.region.id); } catch (e) { view = null; }

    // the register table, adopted once if the client is carrying it
    if (!this._kingPayloadSeen && st && (st.king_payload || st.kingPayload)) {
      this._kingPayloadSeen = true;
      try { this._kingRefused = kingui.adoptPayload(st.king_payload || st.kingPayload).refused; }
      catch (e) { /* a half-built payload is not a reason to stop drawing */ }
    }

    /* Nothing to say. Note what this does NOT do: it does not silence a
     * sentence already in the air. The engine clears its row the moment the
     * client has seen it, and a man cut off mid-word by a poll is a bug in the
     * poll rather than a characterisation. He finishes, then he goes. */
    if (!view) { this._kingStamp = ''; return; }

    const stamp = kingui.stampOf(view);
    if (stamp === this._kingStamp) { if (this.king) this.king.sync(view); return; }

    /* A different sentence. He does not queue — the newest thing he has to say
     * replaces the one being said, because a backlog is a conversation and he
     * is not having one. */
    this._kingStamp = stamp;
    this._kingSeq++;
    const w = this._kingWorld;
    w.regionId = this.region.id;
    w.player = this.player;
    w.markers = this.markers;
    w.viewW = this.viewW; w.viewH = this.viewH; w.scale = this.scale;
    // He may arrive before the first frame has been painted, so the frame is
    // asked for rather than remembered.
    this._camera();
    w.camX = this._camX; w.camY = this._camY;
    w.seq = this._kingSeq;
    this.king = new kingui.Presence(view, w);
    this._kingUnder = 0;
    if (this.onKingSpoke) {
      // One object per THING SAID — a handful in a whole game — not one per
      // frame. The per-frame paths in this file allocate nothing; this is not
      // one of them.
      try {
        this.onKingSpoke({
          occasion: view.occasion, register: view.register, text: view.text,
          ms: view.ms, index: this.king.index, seq: this._kingSeq,
          regionId: view.regionId, placed: this.king.placed, blocking: false,
        });
      } catch (e) { /* a listener that throws is not this module's problem */ }
    }
  }

  _updateKing(dt) {
    this._syncKing();
    const k = this.king;
    if (!k) return;                       // F. one null check and out
    if (k.update(dt, this.time) !== 'gone') return;
    const why = k.dismissed ? 'dismissed' : (k.walked > 16 * 5 ? 'walked away' : 'said');
    this.king = null;
    this._kingPanelAlpha = 0;
    this._kingWashPeak = 0;
    if (this.onKingGone) {
      try { this.onKingGone({ occasion: k.view.occasion, register: k.register, why }); }
      catch (e) { /* same */ }
    }
  }

  /* -------------------------------------------------------- the Unmaking
   *
   * THE LAST SPELL, ON THE MAP HE SAID IT ON.
   *
   * gauntlet/unmaking.py owns the spell: which crutch leaves in which order,
   * what each act is called, how long each beat runs, and the words. This file
   * asks that module rather than inventing any of it — `castUnmaking` takes the
   * JSON `unmaking.cinematic()` returns and hands it straight to
   * unmakingfx.beatsFromCinematic, and the standalone table in unmakingfx is
   * only what happens when nobody passed one.
   *
   * FOUR THINGS HAPPEN TO A FRAME AND THEY ARE ALL IN THIS FILE:
   *
   *   1  the hero's image is swapped for the plate that has lost what has been
   *      taken so far — an exact colour substitution over the same pixels, so
   *      his SILHOUETTE never moves;
   *   2  the green arcs are painted on his own outline, at the same coordinates
   *      the sprite was drawn at, inside the same camera transform;
   *   3  the companion's alpha is multiplied by what the spell says, and once
   *      that is zero the animal stops being drawn;
   *   4  the screen layer goes on in screen space.
   *
   * WHERE THE SCREEN LAYER IS PAINTED, AND WHY NOT LAST. unmakingfx's own
   * integration note asks for "the same place as _drawApexOverlay". It goes
   * just BEFORE it instead, and that is deliberate: the screen layer is a
   * whole-frame wash of up to 0.30, the apex overlay ends on the gold chevron
   * that points at the way out, and this file has exactly one rule it will not
   * break for any feature — nothing it draws may end up on top of the door.
   * The King's panel is ordered against the same promise, ten lines down.
   *
   * IT DOES NOT BLOCK. There is no key it waits for, nothing to dismiss,
   * nothing to confirm, and no branch in update() that stops reading the
   * movement keys while it runs. `cancel()` exists for a host that needs the
   * sequence over now, and the player never has to use it.
   *
   * THE CONTRACT FOR main.js, which this pass does not touch. Four lines, and
   * three of them are optional.
   *
   * PUSH — the host decides:
   *
   *   G.overworld.castUnmaking({
   *     cinematic: await api.unmakingCinematic(),   // gauntlet/unmaking.py
   *   });                                          // omit for the 15.60s table
   *   G.overworld.onUnmakingDone = (info) => { ... };  // optional, fires once,
   *                                                    // {seconds, beats,
   *                                                    //  takenMask, stillPlain}
   *   G.overworld.clearUnmaking();                 // give the gear back
   *
   * PULL — the engine decides. `stateSource()` returns a row under any of
   * `unmaking` / `last_spell` / `nullKingSpell`, in the shape
   *
   *   { cinematic } | { beats } | { active: true }   // plus optional `key`
   *
   * and it is cast when the row first appears. Drop the row and the hero gets
   * his gear back once the spell has finished; change `key` and it recasts.
   *
   * AFTERWARDS, AND THIS IS THE PART THAT IS EASY TO GET WRONG. When the
   * sequence ends the hero STAYS PLAIN — see _updateUnmaking. That is the
   * event, not a leak. The host takes him out of it in exactly one of three
   * ways: clearUnmaking(), dropping the state row, or calling setEquipment()
   * with whatever the engine now says he is wearing. Doing nothing leaves a man
   * standing in a field with nothing on him, which is the correct picture.
   *
   * WHAT THE HOST NEVER HAS TO DO: wait for it, gate on it, pause anything,
   * hide the HUD, or handle a key for it. `unmakingDebug().blocking` is false
   * and there is no branch that can set it.
   *
   * Every degrade is silent: a malformed row, a cinematic from a newer schema,
   * a stateSource that throws — all of them mean "nothing is being taken", and
   * the overworld renders exactly as it did before this existed.
   */
  castUnmaking(spec = {}) {
    const o = spec || {};
    let beats = null;
    try {
      if (Array.isArray(o.beats) && o.beats.length) beats = unmakingfx.beatsFrom(o.beats);
      else if (o.cinematic) beats = unmakingfx.beatsFromCinematic(o.cinematic);
    } catch (e) { beats = null; }
    let fx = null;
    try {
      fx = unmakingfx.createUnmaking({
        sprites, look: this._heroLook,
        beats: (beats && beats.length) ? beats : undefined,
        reducedMotion: this.reducedMotion,
      });
    } catch (e) { return null; }     // a spell that will not build is silence
    this.unmaking = fx;
    this._unmakingSpent = false;
    this._unmakingFromState = false;
    this._unmakingScreenPeak = 0;
    this._unmakingArcPx = 0;
    this._unmakingCompanionAlpha = 1;
    this._prewarmUnmaking();
    return fx;
  }

  /* Every plate and every contour the sequence can ask for, built BEFORE the
   * first frame of it. Without this the effect is still correct and allocates a
   * canvas on each beat boundary from inside the draw loop, which is the one
   * thing scripts/verify/cap.mjs exists to fail on. Twenty-four hero frames —
   * four facings by four walk frames and two idle ones — and up to eight
   * companion strips: 96 plates and 56 contours, measured, a few milliseconds,
   * once, at the moment he starts. */
  _prewarmUnmaking() {
    const u = this.unmaking;
    if (!u) return 0;
    let built = 0;
    try {
      for (const facing of ['down', 'up', 'left', 'right']) {
        const walk = this.hero[facing] || [];
        for (let f = 0; f < walk.length; f++) {
          built += u.prewarm(walk[f], this._heroKey(facing, f, 'walk'), facing, f, 'walk');
        }
        const idle = (this.hero.idle && this.hero.idle[facing]) || [];
        for (let f = 0; f < idle.length; f++) {
          built += u.prewarm(idle[f], this._heroKey(facing, f, 'idle'), facing, f, 'idle');
        }
      }
      /* Every strip the draw pass can CHOOSE, chosen the same way it chooses
       * it. Enumerating c.art by hand here instead would name keys the draw
       * pass never asks for and miss the ones it does — a companion with no
       * idle strip for a facing falls back to its walk strip while still
       * reading as standing still, and that fallback has to be warmed under the
       * name the draw pass will look it up by, or the contour is traced inside
       * the render loop. */
      if (this.companion && this.companion.art) {
        for (const cf of ['down', 'up', 'left', 'right']) {
          for (const moving of [true, false]) {
            const strip = this._companionStrip(cf, moving);
            if (!strip) continue;
            for (let f = 0; f < strip.length; f++) {
              u.prewarmSprite(strip[f], this._companionKey(cf, f, !moving));
            }
          }
        }
      }
    } catch (e) { /* a rig that will not warm still draws; it just allocates */ }
    this._unmakingPrewarmed = built;
    return built;
  }

  /* The two key builders, in one place so the warm pass and the draw pass
   * cannot disagree about what a sprite is called. A key that differs between
   * them shows the wrong plate; it cannot crash, which is exactly why it would
   * never be noticed. */
  _heroKey(facing, frame, pose) {
    return `hero|${this._lookKey}|${facing}|${frame}|${pose}`;
  }
  /* Which strip the companion is drawn from, as an array, for one facing and
   * one movement state. The draw pass and the warm pass both go through here so
   * they cannot disagree about which image a key names. */
  _companionStrip(facing, moving) {
    const c = this.companion;
    if (!c || !c.art) return null;
    const idle = c.art.idle;
    const strip = (!moving && idle && idle[facing]) ? idle[facing]
                : (c.art[facing] || c.art.down);
    if (!strip) return null;
    return strip.length !== undefined ? strip : [strip];
  }
  _companionKey(facing, frame, idle) {
    const c = this.companion;
    return `pet|${(c && c.id) || '-'}|${facing}|${frame}|${idle ? 'i' : 'w'}`;
  }

  _unmakingState() {
    if (this._unmakingPushed !== undefined) return this._unmakingPushed;
    if (typeof this.stateSource !== 'function') return null;
    let st = null;
    try { st = this.stateSource(); } catch (e) { return null; }
    if (!st || typeof st !== 'object') return null;
    const row = st.unmaking || st.last_spell || st.lastSpell
             || st.nullKingSpell || st.null_king_spell;
    return (row && typeof row === 'object') ? row : null;
  }

  /* Push. Pass null to end it; pass undefined to hand the decision back to
   * stateSource. Symmetrical with setKing and setCompanion on purpose. */
  setUnmaking(row) {
    this._unmakingPushed = row === undefined ? undefined : (row || null);
    // An explicit null is the host saying "nothing is being taken any more",
    // and unlike a row that merely stopped arriving it releases a spent effect
    // outright rather than waiting to be asked twice.
    if (this._unmakingPushed === null && this.unmaking && this.unmaking.done) {
      this.clearUnmaking();
      this._unmakingPushed = null;
      return;
    }
    this._syncUnmaking();
  }

  _syncUnmaking() {
    const row = this._unmakingState();
    if (!row) {
      /* The row went away. What is already running is NOT cut off mid-beat —
       * the same rule the King gets: a spell interrupted by a poll is a bug in
       * the poll. It is asked to finish first.
       *
       * Once it HAS finished, a row that is no longer there is the engine
       * saying the world is not being unmade any more, and the spent effect is
       * released — which is the only thing that gives the hero his gear back. A
       * spell this file was handed directly rather than read off the state is
       * never released here: the host that cast it is the host that ends it. */
      this._unmakingStamp = '';
      if (this._unmakingFromState && this.unmaking && this.unmaking.done) {
        this.clearUnmaking();
      }
      return;
    }
    const stamp = String(row.key || row.stamp || row.seq
                         || (row.cinematic && row.cinematic.version) || 'cast');
    if (stamp === this._unmakingStamp) return;
    this._unmakingStamp = stamp;
    this.castUnmaking(row);
    this._unmakingFromState = true;
  }

  /* Give it back. The only way the hero returns to his gear, and it is the
   * host's decision rather than this file's — see _updateUnmaking. */
  clearUnmaking() {
    if (!this.unmaking) return false;
    this.unmaking = null;
    this._unmakingStamp = '';
    this._unmakingFromState = false;
    this._unmakingSpent = false;
    this._unmakingScreenPeak = 0;
    this._unmakingArcPx = 0;
    this._unmakingCompanionAlpha = 1;
    return true;
  }

  /* WHAT HAPPENS AFTER THE LAST BEAT, which is the whole point of the spell.
   *
   * The effect is NOT thrown away when it finishes. Nulling it here is the
   * obvious thing to write and it undoes the entire sequence on the very next
   * frame: heroImage stops being consulted, the hero reverts to the dressed
   * sprite, and fifteen seconds of being taken from ends with the player back
   * in full armour as though none of it had happened. Measured, before this
   * comment existed: zero pixels different from the dressed hero one frame
   * after the spell that took everything.
   *
   * So the spent effect is kept, and keeping it costs almost nothing: step()
   * returns immediately, `air` is zero past the last beat so there are no arcs
   * and no wash, and heroImage is a pointer comparison handing back the
   * fully-taken plate. The hero STAYS plain — which is what the spell did —
   * until the host says otherwise, by calling clearUnmaking(), by handing
   * setEquipment() the stripped look the engine now says he is wearing, or by
   * dropping the state row that cast it.
   *
   * onUnmakingDone fires exactly once, on the frame the last beat ends. */
  _updateUnmaking(dt) {
    this._syncUnmaking();
    let u = this.unmaking;
    if (!u) return;                      // one null check and out
    /* prefers-reduced-motion is a CONSTRUCTION-time flag in unmakingfx, and
     * main.js re-reads the media query into `this.reducedMotion` whenever the
     * setting changes. A player who turns it on halfway through fifteen seconds
     * of this has asked for the motion to stop and would otherwise keep getting
     * it until the spell ended. Rebuilding and seeking to the same `t` is that
     * module's own documented answer: same beats, same position, nothing
     * moving. It happens at most once or twice in a lifetime. */
    if (!!this.reducedMotion !== !!u.reducedMotion) {
      const at = u.t, spent = this._unmakingSpent, fromState = this._unmakingFromState;
      const rebuilt = this.castUnmaking({ beats: u.beats });
      if (rebuilt) {
        rebuilt.seek(at);
        this._unmakingSpent = spent;
        this._unmakingFromState = fromState;
        u = rebuilt;
      }
    }
    let done = false;
    try { done = u.step(dt); } catch (e) { done = true; }
    if (!done || this._unmakingSpent) return;
    this._unmakingSpent = true;
    this._unmakingScreenPeak = 0;
    this._unmakingArcPx = 0;
    if (this.onUnmakingDone) {
      try {
        this.onUnmakingDone({ seconds: u.duration, beats: u.beats.length,
                              takenMask: u.taken, stillPlain: true });
      } catch (e) { /* a listener that throws is not this module's problem */ }
    }
  }

  /* What scripts/verify reads back. Allocation-free for the caller to ignore. */
  unmakingDebug() {
    const u = this.unmaking;
    if (!u) return null;
    return {
      beat: u.beat, beatId: u.beatId, k: +u.k.toFixed(3),
      t: +u.t.toFixed(3), duration: +u.duration.toFixed(2), done: u.done,
      takenMask: u.taken, platesPrewarmed: this._unmakingPrewarmed,
      companionAlpha: +this._unmakingCompanionAlpha.toFixed(3),
      arcPixelsLastFrame: this._unmakingArcPx,
      screenPeakAlpha: +this._unmakingScreenPeak.toFixed(4),
      reducedMotion: !!u.reducedMotion,
      spent: !!this._unmakingSpent,
      fromState: !!this._unmakingFromState,
      // The promise, restated where a harness can read it.
      blocking: false, blocksInput: false, dismissRequired: false,
    };
  }

  /* What scripts/verify/kingui.mjs reads back. Cheap, and allocation-free for
   * the caller to ignore. */
  kingDebug() {
    if (!this.king) return null;
    const d = this.king.debug();
    d.sortY = +this._kingSortY.toFixed(2);
    d.framesSortClampedBehindSomething = this._kingUnder;
    d.panelAlpha = +this._kingPanelAlpha.toFixed(4);
    d.washPeakAlpha = +this._kingWashPeak.toFixed(4);
    d.payloadRefused = this._kingRefused || [];
    // The promise, restated where a harness can read it rather than where a
    // reviewer has to believe it.
    d.blocksInput = false;
    d.inCollision = false;
    return d;
  }

  /* What scripts/verify/apexhunt.mjs reads back. */
  apexDebug() {
    if (!this.hunt) return null;
    const d = this.hunt.debug();
    d.stateSeenByTheClient = this._apexStage;
    d.telegraphPeakAlpha = +this._apexPeak.toFixed(4);
    d.wayOutMarksDrawn = this._wayOutMarks;
    d.threatMark = this._threatMark;
    d.wayOutMarks = this._wayOutMark.slice(0, this._wayOutMarks);
    d.sortY = +this._apexSortY.toFixed(2);
    d.framesSortClampedBehindSomething = this._apexUnder;
    d.payloadRefused = this._apexPayloadRefused || [];
    return d;
  }

  /* What the hunt costs the escape, drawn in screen space after the world
   * transform is gone. The order is the whole argument:
   *
   *   1  the threat wash, capped at VIGNETTE_CAP
   *   2  the threat chevron, in the INNER lane, at the strength the state's
   *      map channel allows: a heading, a stale scent, or a live position
   *   3  the way out, in the OUTER lane, gold, LAST
   *
   * Three is painted after one and two and nearer the rim than either, so no
   * amount of dread this file can generate is capable of covering the direction
   * of the door. That is C, enforced by ordering and geometry rather than by
   * intention. */
  _drawApexOverlay(ctx) {
    this._apexPeak = 0;
    this._wayOutMarks = 0;
    const h = this.hunt;
    if (!h || !h.embodied) return;
    const cfg = apexmod.TELEGRAPH[h.state];
    if (!cfg || cfg.map === 'none') return;

    /* Pinned, not inherited. Everything above this point in draw() is a stack
     * of save/restore pairs and translucent passes, and a gold arrow pointing
     * at the door whose opacity depends on whether the particle layer happened
     * to put globalAlpha back is not a guarantee, it is a hope. Measured: the
     * rasteriser reaches this line with 0.5 left on the context, which would
     * have painted the way out at half strength in any browser that inherited
     * the same leak. */
    const prevAlpha = ctx.globalAlpha;
    ctx.globalAlpha = 1;

    this._apexPeak = apexmod.drawTelegraph(
      ctx, h, this.viewW, this.viewH, this.time, this.reducedMotion);

    /* The map channel, straight out of hunters.py's telegraph table, and the
     * only place in this file where the three readings differ:
     *
     *   heading  it is out there, that way. Dim, and no claim about distance.
     *   stale    where it WAS. The marker points at a position two seconds old
     *            on purpose, because TRACKING means "it knows where you were"
     *            and a marker that told the truth would be saying the opposite.
     *   live     where it is. Bright, and correct. */
    const strength = cfg.map === 'live' ? 0.95 : cfg.map === 'stale' ? 0.62 : 0.42;
    const b = h.bearing(this._bearing, cfg.map === 'stale');
    apexmod.drawEdgeMark(ctx, this.viewW, this.viewH, b.x, b.y,
                         h.view.colour, strength,
                         apexmod.THREAT_LANE, apexmod.MARK_SIZE, this._threatMark);

    /* The way out: every exit on this map, in gold, outboard of the threat.
     * Not the NEAREST exit — both of them. "Nearest" is a judgement this code
     * would be making on the player's behalf while something chases them, and
     * the two ends of the road are not interchangeable. */
    const p = this.player;
    for (let i = 0; i < this.markers.length; i++) {
      const m = this.markers[i];
      if (m.kind !== 'exit') continue;
      const dx = (m.x * T + T / 2) - (p.px + T / 2);
      const dy = (m.y * T + T / 2) - (p.py + T / 2);
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      apexmod.drawEdgeMark(ctx, this.viewW, this.viewH, dx / d, dy / d,
                           '#e8c37d', 0.9, apexmod.WAYOUT_LANE, apexmod.MARK_SIZE,
                           this._wayOutMark[this._wayOutMarks] || null);
      this._wayOutMarks++;
    }
    ctx.globalAlpha = prevAlpha;
  }

  /* What the harness measures. Cheap, allocation-free for the caller to read. */
  companionDebug() {
    const c = this.companion;
    if (!c) return null;
    return { animal: c.animal, tier: c.tier, px: c.px, py: c.py, facing: c.facing,
             nudged: c.nudged,
             frame: c.frame, moving: c.moving, settled: c.settled,
             speed: c.speed, hasArt: !!c.art, alert: c.alert,
             sortY: c.sortY, overHero: c.overHero };
  }

  /* Anything taller than a tile has to be y-sorted against the scenery, or the
   * hero walks in front of a tree he is standing behind. */
  _gatherObjects(view) {
    const out = [];
    tiles.collectObjects(this.scene, view, out);
    const t = this.time * 1000;

    for (const m of this.markers) {
      /* The y margin is sized for the TALLEST marker, not the commonest one.
       * A marker's sprite is drawn upward from the bottom of its tile, so a
       * marker below the viewport still paints into it while its top row is
       * on screen. At 3 that covered a 48px boss (3 tiles); the Interviewer's
       * map form is 96px — 6 tiles — so a boss at view.y1 + 4 or + 5 painted
       * into the viewport and was culled before it could. 6 restores the same
       * one tile of slack the 48px marker had. */
      if (m.x < view.x0 - 2 || m.x > view.x1 + 2
          || m.y < view.y0 - 3 || m.y > view.y1 + 6) continue;

      if (m.kind === 'encounter' || m.kind === 'elite') {
        if (this.solvedNodes.has(m.id)) {
          out.push({ x: m.x, y: m.y, sortY: m.y * T + T, draw: (ctx) => {
            ctx.globalAlpha = 0.4;
            ctx.fillStyle = '#8fd07a';
            ctx.fillRect(m.x * T + 6, m.y * T + 7, 4, 4);
            ctx.globalAlpha = 1;
          } });
          continue;
        }
        /* WHAT THIS USED TO BE, and why it is worth a comment: every
         * ordinary encounter in all seventeen regions was hardcoded to
         * 'slime' and every elite to 'construct'. The Marsh, the Mines and
         * the Castle all fielded the Fields' animals. monsterart.js resolves
         * against the region's own roster, so the creature standing on the
         * tile now belongs to the place the player is standing in.
         *
         * The pick is seeded off the marker id, so it is stable across
         * frames and across a reload of the same world, and two nodes in one
         * region are usually two different animals. Elites keep the pink
         * tint they always had — it is the only thing distinguishing them at
         * a glance, and the species colour is not load-bearing for that. */
        const regionId = (this.region && this.region.id) || null;
        /* An elite gets the ELITE BODY, not a mob in a pink coat. The 32px
         * rung — ELITE_SIZE, eight authored bodies, BIOME_ELITE — existed and
         * nothing in web/js called it: both marker kinds resolved through
         * pickFor(), which returns MOB_KEYS only, so the one thing separating
         * an elite from an ordinary encounter was a tint doing a silhouette's
         * job. eliteKeyFor() returns '' for a biome it does not know, so the
         * || keeps the old behaviour as the fallback, and monsterSize /
         * monsterShadow below already read the box off the resolved key, so a
         * 32px body places and shadows itself. */
        const key = m.kind === 'elite'
          ? (monsterart.eliteKeyFor(regionId) || monsterart.pickFor(regionId, sprites.hash(m.id)))
          : monsterart.pickFor(regionId, sprites.hash(m.id));
        const pose = monsterart.monsterFrameAt(key, t * 1000, 'idle',
                                               m.x + m.y, { region: regionId });
        const img = monsterart.monsterFrame(key, pose.frame, {
          region: regionId, pose: 'idle',
          colour: m.kind === 'elite' ? '#d84a7a' : undefined,
        });
        const size = monsterart.monsterSize(key, { region: regionId });
        const sh = monsterart.monsterShadow(key, { region: regionId });
        const ox = (T - size) / 2;
        out.push({ x: m.x, y: m.y, sortY: m.y * T + T, draw: (ctx) => {
          sprites.drawGroundShadow(ctx, m.x * T + T / 2, m.y * T + T - 1,
                                   sh.rx, sh.ry, sh.alpha);
          if (img) {
            ctx.drawImage(img, m.x * T + ox + pose.dx,
                          m.y * T + T - size + pose.dy);
          }
        } });
      } else if (m.kind === 'npc') {
        const villager = this.villagers[
          (m.x + m.y + m.id.length) % this.villagers.length];
        const img = villager.idle.down[Math.floor(this.time * 1.5) % 2];
        out.push({ x: m.x, y: m.y, sortY: m.y * T + T, draw: (ctx) => {
          sprites.drawGroundShadow(ctx, m.x * T + T / 2, m.y * T + T - 1, 6, 3, 0.3);
          ctx.drawImage(img, m.x * T, m.y * T + T - sprites.HERO_H);
          ctx.fillStyle = '#ffe8a0';
          const bob = Math.sin(this.time * 3 + m.x) > 0 ? 0 : 1;
          ctx.fillRect(m.x * T + 7, m.y * T - 6 + bob, 2, 2);
        } });
      } else if (m.kind === 'boss') {
        // The authored 64x64 boss, drawn at map scale. It carries its own
        // shadow and ambient motion, so this is one call.
        const key = m.boss || 'titan';
        out.push({ x: m.x, y: m.y, sortY: m.y * T + T, draw: (ctx) => {
          bosses.drawBoss(ctx, key, m.x * T + T / 2, m.y * T + T, {
            time: t, scale: 1, colour: m.colour || '#d84a7a',
            reducedMotion: this.reducedMotion,
          });
        } });
      } else if (m.kind === 'building') {
        const img = tiles.buildingSprite(this.scene.set.palette,
                                         hash(m.id), m.tier, m.variant);
        out.push({ x: m.x, y: m.y, sortY: m.y * T + img.height - 4,
                   draw: (ctx) => ctx.drawImage(img, m.x * T, m.y * T + T * 2 - img.height) });
      } else if (m.kind === 'exit') {
        /* C. While something is hunting, the door is lit harder and beats
         * faster. The same glow, turned up — not a new widget, and not a
         * message. A player who has just been told there is something out here
         * should be able to find the way home by looking at the map, in the
         * same place it has always been. */
        const hunted = !!(this.hunt && this.hunt.embodied
                          && this.hunt.state !== 'ROAMING');
        const base = hunted ? 0.52 : 0.3;
        const swing = hunted ? 0.22 : 0.12;
        const rate = hunted ? 4.2 : 2;
        out.push({ x: m.x, y: m.y, sortY: m.y * T, draw: (ctx) => {
          ctx.fillStyle = `rgba(232,195,125,${base + Math.sin(this.time * rate) * swing})`;
          ctx.fillRect(m.x * T, m.y * T - 4, T, T + 8);
          if (hunted) {
            ctx.fillStyle = 'rgba(232,195,125,0.85)';
            ctx.fillRect(m.x * T, m.y * T - 5, T, 1);
            ctx.fillRect(m.x * T, m.y * T + T + 4, T, 1);
          }
        } });
      }
    }

    // the hero
    const p = this.player;
    const facing = (p.facing === 'side') ? 'right' : p.facing;
    const frames = p.moving ? this.hero[facing] : this.hero.idle[facing];
    const fi = p.frame % frames.length;
    const img = frames[fi];
    /* THE UNMAKING, on the sprite. Two lines, and both of them are null checks
     * when nothing is being taken.
     *
     * `heroImage` returns the very same object it was handed until something
     * has actually been taken, so the ordinary frame is a pointer comparison
     * and `shown === img`. Once a taking has landed it returns a PLATE: the
     * same pixels with the taken ones substituted, which is why his silhouette
     * never moves and why "the trim went grey" is a number rather than a claim.
     *
     * The key must be the same string the prewarm pass used or the wrong plate
     * comes back, silently — so neither side builds it, _heroKey does. */
    const u = this.unmaking;
    const pose = p.moving ? 'walk' : 'idle';
    const ukey = u ? this._heroKey(facing, fi, pose) : '';
    let shown = img;
    if (u) { try { shown = u.heroImage(img, ukey, facing, fi, pose) || img; }
             catch (e) { shown = img; } }
    out.push({ x: p.x, y: p.y, sortY: p.py + T + 1, draw: (ctx) => {
      sprites.drawGroundShadow(ctx, p.px + T / 2, p.py + T - 1, 6, 3, 0.32);
      ctx.drawImage(shown, Math.round(p.px), Math.round(p.py + T - sprites.HERO_H));
      /* The green ON the sprite — the brief's own words. Arcs crawling his own
       * outline, painted immediately after the sprite, at the coordinates the
       * sprite went down at, inside the same camera transform. It paints single
       * pixels on the sprite's own lattice, so it stays pixel-aligned at any
       * integer world scale. */
      if (u) {
        try {
          this._unmakingArcPx = u.drawSprite(
            ctx, shown, Math.round(p.px), Math.round(p.py + T - sprites.HERO_H), ukey);
        } catch (e) { this._unmakingArcPx = 0; }
      }
      if (!p.moving) {
        /* A soft chevron above the head when standing still: enough to find
         * yourself in a village, not enough to be noise while walking.
         *
         * EVERY NUMBER HERE IS A WHOLE WORLD PIXEL, and it is the zoom that
         * made that matter. `p.px` is a float while a step is in flight and
         * the bob was a float always, so this was the one thing in the world
         * layer landing on fractional coordinates — the sprite beside it is
         * drawn at Math.round(p.px), the shadows round inside drawGroundShadow,
         * every marker is at m.x * T. A fillRect is not a drawImage and
         * imageSmoothingEnabled does not reach it: the canvas antialiases the
         * edges, and a 4x2 rectangle with soft sides is 4x2 fuzzy pixels at
         * scale 2 and 20x10 fuzzy pixels at scale 5. The zoom did not create
         * the blur, it magnified it by the same factor it magnified everything
         * else, which is the whole point of raising the scale and also its
         * whole liability. Rounding the bob to a whole pixel keeps the two-step
         * bounce it always had — the sine spends most of its time past +/-0.5. */
        const bx = Math.round(p.px), by = Math.round(p.py);
        const bob = Math.round(Math.sin(this.time * 3) * 1.5);
        ctx.fillStyle = 'rgba(232,195,125,0.85)';
        ctx.fillRect(bx + 6, by - 10 + bob, 4, 2);
        ctx.fillRect(bx + 7, by - 8 + bob, 2, 2);
      }
      /* The Green Index, landing on the player. Four corner brackets and one
       * slow read across the sprite, in the colour that has been turning up in
       * side quests since Chapter II — and this is the first time it is aimed
       * at the person holding it. kingui owns the treatment and the rule that
       * it only happens from PRECISE up; this is one null check and a call. */
      if (this.king) {
        kingui.drawIndexOnPlayer(ctx, this.king, p.px, p.py, this.time,
                                 this.reducedMotion);
      }
    } });

    /* C. The companion joins the SAME y-sort as the trees, the buildings, the
     * NPCs and the hero. It is not painted on afterwards, so it goes behind the
     * tree it is standing behind and in front of the one it is standing in
     * front of, for free and for the same reason everything else does.
     *
     * The one override is B: when its box and the hero's actually intersect it
     * is forced under him. Retracing keeps it behind you almost always, but a
     * reversal or a settle can put it a few pixels south of your feet, and a
     * pet eclipsing the character you are steering is the failure mode nobody
     * forgives. Non-overlapping cases keep the honest sort. */
    const c = this.companion;
    if (c && c.art) {
      const cf = (c.facing === 'side') ? 'right' : c.facing;
      const strip = this._companionStrip(cf, c.moving);
      const cimg = strip && strip[c.frame % strip.length];
      if (cimg && cimg.width) {
        const cw = cimg.width, ch = cimg.height;
        const cx = Math.round(c.px + (T - cw) / 2);
        const cy = Math.round(c.py + T - ch);
        const hx = Math.round(p.px), hy = Math.round(p.py + T - sprites.HERO_H);
        const over = cx < hx + sprites.HERO_W && cx + cw > hx
                  && cy < hy + sprites.HERO_H && cy + ch > hy;
        const sortY = over ? Math.min(c.py + T, p.py + T + 0.5) : c.py + T;
        c.sortY = sortY; c.overHero = over;   // what scripts/verify reads back
        const sx = c.px + T / 2, sy = c.py + T - 1;
        const sr = c.shadowR, sry = c.shadowRY;
        const alertColour = (c.alert && this.hunt) ? this.hunt.view.colour : null;
        /* THE UNMAKING, on the companion — the one thing in the sequence that
         * actually LEAVES. Everything taken off the hero is a colour
         * substitution and his outline survives all of it; the animal's shape
         * goes out, and its silhouette is the number that is not zero.
         *
         * `companionAlpha` is 1 before its beat and 0 after it, so a host that
         * multiplies by it unconditionally is correct the whole way through.
         * At zero the animal is not drawn at all, and it does not come back. */
        const uc = this.unmaking;
        let ca = 1;
        if (uc) { try { ca = uc.companionAlpha(); } catch (e) { ca = 1; } }
        this._unmakingCompanionAlpha = ca;
        /* The index of the frame that was ACTUALLY chosen out of the strip,
         * not c.frame. The walk strips are four long and the idle strips are
         * two, so `c.frame % 4` invents two key names the prewarm pass never
         * built — and an unwarmed key traces its contour on the spot, which
         * means a canvas allocated inside the draw loop. Measured: exactly the
         * thing scripts/verify/cap.mjs exists to fail on. */
        const cfi = c.frame % strip.length;
        const ckey = uc ? this._companionKey(cf, cfi, !c.moving) : '';
        if (ca > 0.004) out.push({ x: Math.floor(c.px / T), y: Math.floor(c.py / T), sortY,
                   draw: (ctx) => {
          const prev = ctx.globalAlpha;
          /* `ca` goes on globalAlpha and NEVER into drawGroundShadow's alpha
           * argument. sprites.groundShadow caches on its parameters, alpha
           * included, so a shadow whose alpha is a continuously varying number
           * is a fresh canvas built and cached on every single frame the
           * companion is fading — measured at 48 canvases allocated inside the
           * draw loop over one departure, which is precisely the failure
           * scripts/verify/cap.mjs exists to catch. The constant is the cache
           * key; the fade is free. */
          if (ca < 1) ctx.globalAlpha = prev * ca;
          sprites.drawGroundShadow(ctx, sx, sy, sr, sry, 0.28);
          ctx.drawImage(cimg, cx, cy);
          ctx.globalAlpha = prev;
          if (uc) { try { uc.drawCompanion(ctx, cimg, cx, cy, ckey); } catch (e) { /* no contour, no arc */ } }
          if (alertColour) {
            apexmod.drawCompanionAlert(ctx, cx + cw / 2 - 1, cy - 7, alertColour,
                                       this.time, this.reducedMotion);
          }
        } });
      }
    }

    /* A. The apex joins the same y-sort as the hero, the trees and the
     * companion, so it goes behind what it is behind. Then one rule on top of
     * that, and it is the rule the whole draw is for:
     *
     *   IT MAY NEVER COVER THE PLAYER, A MARKER, OR AN EXIT.
     *
     * Its drawn box is forty-eight pixels — three tiles — so it WILL overlap
     * things, often. Overlapping is fine. Being in front of them is not. So
     * every box its own box intersects contributes a ceiling, and its sortY is
     * the minimum of all of them: it is drawn before anything it touches, which
     * means underneath. A chest you were walking to is still a chest you can
     * see, with a monster looming behind it.
     *
     * This is the same override the companion gets against the hero, applied to
     * everything rather than to one case, because the companion is sixteen
     * pixels and beside you and this thing is forty-eight and coming. */
    const h = this.hunt;
    if (h && h.embodied && h.alpha > 0.004) {
      const bx = h.px + T / 2 - apexmod.APEX_SIZE / 2;
      const by = h.py + T - apexmod.APEX_SIZE;
      const bw = apexmod.APEX_SIZE, bh = apexmod.APEX_SIZE;
      let sortY = h.py + T;
      let clamped = false;
      const under = (oy, ox, ow, oh, osort) => {
        if (bx >= ox + ow || bx + bw <= ox || by >= oy + oh || by + bh <= oy) return;
        if (osort - 0.5 < sortY) { sortY = osort - 0.5; clamped = true; }
      };
      // the player, first and always
      under(p.py + T - sprites.HERO_H, p.px, sprites.HERO_W, sprites.HERO_H,
            p.py + T + 1);
      // and every marker whose glyph it is standing on top of
      for (let i = 0; i < this.markers.length; i++) {
        const m = this.markers[i];
        if (m.x < view.x0 - 4 || m.x > view.x1 + 4
            || m.y < view.y0 - 4 || m.y > view.y1 + 4) continue;
        if (m.kind === 'building') {
          under(m.y * T, m.x * T, T * 2, T * 2, m.y * T + T * 2 - 4);
        } else if (m.kind === 'exit') {
          under(m.y * T - 4, m.x * T, T, T + 8, m.y * T);
        } else if (m.kind === 'boss') {
          under(m.y * T + T - 64, m.x * T + T / 2 - 32, 64, 64, m.y * T + T);
        } else {
          under(m.y * T + T - 24, m.x * T - 4, T + 8, 24, m.y * T + T);
        }
      }
      this._apexSortY = sortY;
      if (clamped) this._apexUnder++;
      const time = this.time;
      const rm = this.reducedMotion;
      out.push({ x: Math.floor(h.px / T), y: Math.floor(h.py / T), sortY,
                 draw: (ctx) => apexmod.drawApexBody(ctx, h, time, rm) });
    }

    /* A. The King joins the same y-sort as the hero, the trees, the companion
     * and the apex, because a figure painted over the scene is a menu with a
     * costume on. He is IN the field: the tree he is standing behind covers
     * him, and that is what makes him a presence rather than an overlay.
     *
     * Then the same one rule the apex gets, for the same reason and by the same
     * arithmetic:
     *
     *   HE MAY NEVER COVER THE PLAYER, A MARKER, OR AN EXIT.
     *
     * kingui.Presence.place() has already refused every position whose box
     * touches one of those, so in the ordinary case this loop finds nothing and
     * his sort is honest. It is here for the cases geometry cannot answer — a
     * building whose sprite is two tiles tall reaching up into him, a marker
     * that moved after he arrived — and it resolves every one of them the same
     * way: drawn before the thing he touches, which means underneath it. */
    const k = this.king;
    if (k && k.placed && k.alpha > 0.004) {
      const bw = kingui.KING_W, bh = k.reg.rows;
      const bx = k.ax - bw / 2, by = k.ay - kingui.KING_H;
      let sortY = k.ay;
      let clamped = false;
      const underKing = (oy, ox, ow, oh, osort) => {
        if (bx >= ox + ow || bx + bw <= ox || by >= oy + oh || by + bh <= oy) return;
        if (osort - 0.5 < sortY) { sortY = osort - 0.5; clamped = true; }
      };
      underKing(p.py + T - sprites.HERO_H, p.px, sprites.HERO_W, sprites.HERO_H,
                p.py + T + 1);
      for (let i = 0; i < this.markers.length; i++) {
        const m = this.markers[i];
        if (m.x < view.x0 - 4 || m.x > view.x1 + 4
            || m.y < view.y0 - 4 || m.y > view.y1 + 4) continue;
        if (m.kind === 'building') {
          underKing(m.y * T, m.x * T, T * 2, T * 2, m.y * T + T * 2 - 4);
        } else if (m.kind === 'exit') {
          underKing(m.y * T - 4, m.x * T, T, T + 8, m.y * T);
        } else if (m.kind === 'boss') {
          underKing(m.y * T + T - 64, m.x * T + T / 2 - 32, 64, 64, m.y * T + T);
        } else {
          underKing(m.y * T + T - 24, m.x * T - 4, T + 8, 24, m.y * T + T);
        }
      }
      this._kingSortY = sortY;
      if (clamped) this._kingUnder++;
      const ktime = this.time;
      const krm = this.reducedMotion;
      out.push({ kind: 'king', x: Math.floor(k.ax / T), y: Math.floor(k.ay / T), sortY,
                 draw: (ctx) => kingui.drawKingBody(ctx, k, ktime, krm) });
    }

    return out;

  }

  /* THE REGION CARD AND THE CONTROL HINTS ARE NOT ALLOWED TO STAND ON HIM.
   *
   * #world-overlay is `bottom: 14px` on the canvas wrap, so it is pinned to the
   * bottom of the FRAME while the hero is pinned to the middle of it — until he
   * walks to the map's south edge, where the camera clamps and he keeps going
   * down the screen. Measured in Chrome in the south-east corner: 53% of his
   * 16x24 sprite box behind #world-overlay at 1440x940 and the same at
   * 1600x1000, with the same again behind #world-hint, which sits in that row.
   * This is OLDER than the zoom and the zoom improved it — at the pre-zoom
   * scale the same corner buried more of him — but a hero you cannot see is a
   * hero you cannot see.
   *
   * The test is a rectangle against a rectangle and the hero's rectangle is
   * taken from the EXPRESSION HE IS DRAWN AT, four lines below in this same
   * method, rather than from a second guess at where he might be. Nothing is
   * moved: the row fades, so the words stay in the place the player has learnt
   * to look for them, and the part of this screen that is an actual warning —
   * apex.js's rim marks and the way-out chevron — is on the canvas and is not
   * in this element at all.
   *
   * THE DOM IS READ FOUR TIMES A SECOND, NOT SIXTY. getBoundingClientRect
   * forces a layout, and this is a draw loop. The box only moves when the
   * window resizes or when something changes the card's height — huntui.js
   * appends the apex telegraph into #region-card while a hunt is live — so a
   * quarter-second cache is both fresh enough to be right and cheap enough to
   * be free. resize() drops it immediately rather than waiting.
   *
   * Guarded end to end because this is the one thing in the file that touches
   * the page: the verify harnesses run it against a document stub with no
   * querySelector at all, and a throw here would take the whole frame. */
  _overlayGuard(camX, camY) {
    let boxes = this._overlayBox;
    /* Written as "not still fresh" rather than "is stale" so that a NaN clock
     * re-measures instead of freezing, and so that an EMPTY measurement — the
     * world screen is not the screen on display, so the row has no box — is
     * cached for the same quarter second as a real one. Without that, every
     * frame of every fight would take a layout to be told the same thing. */
    if (!(this.time < this._overlayBoxAt + 0.25)) {
      this._overlayBoxAt = this.time;
      boxes = this._overlayBox = this._measureOverlay();
    }
    if (!boxes || !boxes.length) return;
    const s = this.scale, p = this.player;
    /* His rect, in canvas pixels. overworld draws the sprite at
     *   drawImage(shown, round(px), round(py + T - HERO_H))
     * inside a layer scaled by s and translated by -round(cam), so this IS
     * where he is — not an estimate of it. */
    const hx = s * (Math.round(p.px) - Math.round(camX));
    const hy = s * (Math.round(p.py + T - sprites.HERO_H) - Math.round(camY));
    const hw = sprites.HERO_W * s, hh = sprites.HERO_H * s;
    for (let i = 0; i < boxes.length; i++) {
      const b = boxes[i];
      const hit = hx < b.x + b.w && hx + hw > b.x && hy < b.y + b.h && hy + hh > b.y;
      if (hit === b.hidden) continue;             // one class write per crossing
      b.hidden = hit;
      try { b.el.classList.toggle('behind-hero', hit); } catch (e) { /* no DOM */ }
    }
  }

  /* The overlay's children, each in the canvas's own pixel space. Every
   * rectangle is read in one call so a scrolled or inset canvas cannot put them
   * in different coordinate systems — the subtraction is the whole point of
   * measuring the canvas at all. */
  _measureOverlay() {
    let els = this._overlayEl;
    if (els === undefined) {
      try {
        els = [document.querySelector('#region-card'),
               document.querySelector('#world-hint')].filter(Boolean);
      } catch (e) { els = []; }
      this._overlayEl = els;
    }
    if (!els.length) return null;
    let c;
    try { c = this.canvas.getBoundingClientRect(); } catch (e) { return null; }
    if (!c || !(c.width > 0)) return null;
    /* The canvas is laid out in CSS pixels and drawn in backing pixels; at
     * devicePixelRatio 1 they are the same, and above 1 they are not. The draw
     * loop works in the CSS box — resize() sets the transform to dpr — so the
     * ratio the hero's rect is in is viewW / cssWidth, which is 1 by
     * construction. Stated rather than assumed, because the day it is not 1 is
     * the day this silently tests the wrong rectangle. */
    const k = this.viewW / c.width;
    const out = [];
    for (const el of els) {
      let a;
      try { a = el.getBoundingClientRect(); } catch (e) { continue; }
      if (!a || !(a.width > 0) || !(a.height > 0)) continue;
      /* The hidden state is carried on the box, not on the overworld, because
       * there are two of them and they cross him at different moments. */
      out.push({ el, hidden: el.classList.contains('behind-hero'),
                 x: (a.left - c.left) * k, y: (a.top - c.top) * k,
                 w: a.width * k, h: a.height * k });
    }
    return out;
  }

  /* Where the frame is, clamped to the map. One copy of this arithmetic:
   * draw() paints with it, _companionHit turns a pointer back into world space
   * with it, and the King asks it whether a place he is thinking of standing is
   * actually on screen. Two copies would drift the first time either moved. */
  _camera() {
    const s = this.scale;
    const worldW = MAP_W * T, worldH = MAP_H * T;
    const spanX = this.viewW / s, spanY = this.viewH / s;
    /* THE MAP SMALLER THAN THE FRAME. The old line was
     *   max(0, min(worldW - spanX, wanted))
     * and when the view is wider than the world that inner limit goes NEGATIVE,
     * max() throws it away, the camera pins to 0 and the right-hand strip of
     * the frame is off the edge of the map. It cannot happen at the sizes this
     * game opens at — the widest span measured is 318 world pixels against a
     * 768-wide map — but it is one drag of a window corner away at SCALE_MIN,
     * and "clamps at the map edges without showing void" is not a promise you
     * keep by arithmetic that only holds for the window sizes you tested.
     * Centre the world instead: a margin on both sides is a framing, a margin
     * on one side is a bug. */
    /* BOTH LIMITS ARE WHOLE WORLD PIXELS, BECAUSE draw() ROUNDS.
     *
     * The camera used to clamp at `worldW - spanX`, which is fractional the
     * moment viewW is not a multiple of the scale — 768 - 1110/4 = 490.5 at the
     * launcher's own window. draw() then translates by -Math.round(camX), and
     * Math.round(490.5) is 491: the clamp was rounded OUTWARD, past the edge it
     * exists to hold, and the map's right edge landed at screen x 1108 of 1110.
     * Two columns of raw sky down the whole right side, and one row along the
     * bottom from the same arithmetic on Y — measured in Chrome by swapping the
     * sky-clear colour and counting which pixels changed: 757 of 893 in each of
     * columns 1108 and 1109, against 1 in column 1107. The same at 1600x1000.
     *
     * Math.floor is the whole fix. Flooring can only ever UNDER-run the edge —
     * the camera stops a fraction of a pixel early — so the map always covers
     * the frame, and "clamps at the map edges without showing void" becomes
     * true at every window size rather than at the ones that happen to divide.
     *
     * THE CENTRE IS ROUNDED FOR THE SAME REASON, AND IT IS THE HERO'S JUDDER.
     * The sprite is drawn at Math.round(p.px) inside a world translated by
     * -Math.round(camX), so his screen column is
     *     round(px) - round(px - (spanX/2 - T/2))
     * and when that offset is not a whole world pixel the two roundings step at
     * different moments: over part of every walk cycle the difference flips
     * between 130 and 131 and the hero slides one world pixel BACKWARDS against
     * the frame while the key is still held forward — `scale` screen pixels of
     * it, so the zoom made a 2px wobble a 4px one. Measured in Chrome off the
     * hero's real screen column while the key was held: 13 backward 4-pixel
     * steps in 131 frames walking east at 1440x940 and the same at 1600x1000,
     * 11 walking south at both. Headless over the same module: ZERO at
     * 1920x1080 walking east — where 1590/5/2 - 8 = 151 is already an integer.
     * That zero is the control; it is the offset, not the walk.
     *
     * Rounding the offset once, here, makes round(camX) equal round(px) - halfX
     * exactly, so the hero is pinned to one screen column and the world scrolls
     * under him in whole world pixels. That is FF6's own behaviour. */
    const maxX = Math.floor(worldW - spanX), maxY = Math.floor(worldH - spanY);
    const halfX = Math.round(spanX / 2 - T / 2);
    const halfY = Math.round(spanY / 2 - T / 2);
    this._camX = worldW <= spanX
      ? (worldW - spanX) / 2
      : Math.max(0, Math.min(maxX, Math.round(this.player.px) - halfX));
    this._camY = worldH <= spanY
      ? (worldH - spanY) / 2
      : Math.max(0, Math.min(maxY, Math.round(this.player.py) - halfY));
  }

  draw() {
    if (!this.scene) return;
    const ctx = this.ctx;
    const s = this.scale;
    this._camera();
    const camX = this._camX, camY = this._camY;

    /* THE KING'S VIEW OF THE FRAME, KEPT FRESH. _syncKing() filled these in
     * once, on the frame he arrived, and then the player walked and they were a
     * memory. kingui.drawKingPanel() now reads the camera off this object to
     * work out where the hero's head actually is — see heroTopOnScreen — and a
     * remembered camera is exactly the wrong answer to that question, because
     * the case it exists for is the player standing at a map edge, which is a
     * place he had to WALK to. Six writes to a persistent object; nothing is
     * allocated and nothing else in this file reads them per frame. */
    const kw = this._kingWorld;
    kw.viewW = this.viewW; kw.viewH = this.viewH; kw.scale = s;
    kw.camX = camX; kw.camY = camY; kw.player = this.player;

    /* AND THE DOM LAYER GETS OUT OF HIS WAY. See _overlayGuard. */
    this._overlayGuard(camX, camY);

    const pal = this.scene.set.palette;
    ctx.fillStyle = pal.sky;
    ctx.fillRect(0, 0, this.viewW, this.viewH);

    ctx.save();
    ctx.scale(s, s);
    ctx.translate(-Math.round(camX), -Math.round(camY));

    const view = tiles.viewBounds(this.scene, camX, camY, this.viewW, this.viewH, s);
    const time = this.reducedMotion ? 0 : this.time;

    tiles.drawGround(ctx, this.scene, view, time);
    tiles.drawFlora(ctx, this.scene, view, time);
    this._objects = this._gatherObjects(view);
    tiles.drawSorted(ctx, this._objects);
    this.drawMotif(ctx);
    pixel.drawParticles(ctx, this.particles, this.particleStyle, 0.45);

    /* The wall clock is READ IN update(), not here. Two reasons, and the second
     * is the one that matters: a draw path that asks what time it is is a draw
     * path that cannot be compared against itself, and every determinism check
     * in scripts/verify is a comparison of two frames drawn from the same state
     * — they agree today because they run inside the same hour and would stop
     * agreeing at nine in the evening. The same rule that keeps Math.random and
     * Date.now out of this file applies to a Date constructor; it just took a
     * clock crossing a boundary to make it visible. */
    const hour = this._hour;
    const night = hour >= 21 || hour < 5;
    tiles.drawLights(ctx, this.scene, view, time, night ? 1 : 0.45);

    ctx.restore();

    if (night) {
      ctx.fillStyle = 'rgba(24,26,64,0.16)';
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    } else if (hour >= 18) {
      ctx.fillStyle = 'rgba(80,40,30,0.07)';
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    }
    if (this.flash > 0) {
      ctx.fillStyle = `rgba(255,255,255,${this.flash * 0.35})`;
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    }

    const grad = ctx.createRadialGradient(
      this.viewW / 2, this.viewH / 2, Math.min(this.viewW, this.viewH) * 0.52,
      this.viewW / 2, this.viewH / 2, Math.max(this.viewW, this.viewH) * 0.80);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(1, 'rgba(0,0,0,0.26)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, this.viewW, this.viewH);

    /* THE UNMAKING, on the screen. Screen space, camera already unwound,
     * globalAlpha PINNED rather than inherited — everything above this line is
     * a stack of translucent passes, and a wash whose cap depends on what the
     * particle layer happened to leave on the context is not a cap, it is a
     * hope.
     *
     * THE WHOLE SCREEN ORDER, BOTTOM TO TOP, AND WHY IT IS THAT ORDER. Each
     * layer may cover the one under it and nothing else:
     *
     *   1  the room  — vignette, night tint, flash
     *   2  the spell — this, a whole-frame wash of up to 0.30
     *   3  his words — the King's panel, which has to stay READABLE while he
     *      is taking things, and would not be if the wash went on top of it
     *   4  the way out — apex.js's gold chevron, over everything, always
     *
     * That puts this ahead of his own panel and well ahead of the door. It is a
     * departure from unmakingfx's own integration note, which asks for "the
     * same place as _drawApexOverlay", and it is the right one: the two things
     * on this screen a player might actually need — what he said, and where the
     * exit is — are the two things his weather does not get to paint over. */
    if (this.unmaking) {
      const prevA = ctx.globalAlpha;
      ctx.globalAlpha = 1;
      try {
        this._unmakingScreenPeak =
          this.unmaking.drawScreen(ctx, this.viewW, this.viewH);
      } catch (e) { this._unmakingScreenPeak = 0; }
      ctx.globalAlpha = prevA;
    }

    /* His panel, in screen space, and BEFORE the hunt's telegraph on purpose.
     * PANEL_TOP already clears both of apex.js's rim lanes, so the two never
     * touch — but a margin is a hope and an ordering is a guarantee, and the
     * guarantee the whole apex overlay is built around is that nothing this
     * file draws can end up on top of the way out. He is the most dangerous
     * thing in the game and he still does not get to paint over the door. */
    if (this.king) {
      this._kingWashPeak = kingui.drawIndexWash(
        ctx, this.king, this.viewW, this.viewH, this.time, this.reducedMotion);
      this._kingPanelAlpha = kingui.drawKingPanel(
        ctx, this.king, this.viewW, this.viewH, this.scale, this.time,
        this.reducedMotion);
    }

    /* Last of everything, deliberately. The room's own vignette is 0.26 at the
     * rim and the night tint is another 0.16 on top of it, and a gold arrow
     * pointing at the door is worth nothing if it is drawn underneath both. The
     * hunt's own darkening goes on here too, so the two are painted in the one
     * place where their relative order can be read off a single function. */
    this._drawApexOverlay(ctx);
  }

  /* Each region draws the shape of its own algorithm across the terrain. */
  drawMotif(ctx) {
    const id = this.region.id;
    const t = this.reducedMotion ? 0 : this.time;
    ctx.save();
    if (id === 'sliding_window_marsh') {
      const width = (7 + Math.sin(t * 0.7) * 3) * T;
      const left = (12 + Math.sin(t * 0.35) * 7) * T;
      ctx.strokeStyle = 'rgba(168,154,255,0.85)';
      ctx.lineWidth = 2;
      ctx.strokeRect(left, 7 * T, width, 20 * T);
      ctx.fillStyle = 'rgba(168,154,255,0.09)';
      ctx.fillRect(left, 7 * T, width, 20 * T);
    } else if (id === 'twin_pointer_pass') {
      const span = MAP_W * T;
      const phase = (Math.sin(t * 0.5) * 0.5 + 0.5) * 0.42;
      ctx.fillStyle = 'rgba(126,200,255,0.85)';
      ctx.fillRect(span * phase, 16 * T, 3, 3 * T);
      ctx.fillStyle = 'rgba(255,157,74,0.85)';
      ctx.fillRect(span * (1 - phase), 16 * T, 3, 3 * T);
    } else if (id === 'dp_ruins') {
      for (let i = 0; i < 16; i++) {
        const lit = (Math.sin(t * 0.8 - i * 0.5) + 1) / 2;
        ctx.fillStyle = `rgba(255,217,122,${0.06 + lit * 0.2})`;
        ctx.fillRect((7 + i * 2) * T, 14 * T, T * 2, T * 2);
      }
    } else if (id === 'binary_tree_canopy') {
      ctx.strokeStyle = 'rgba(143,208,122,0.45)';
      ctx.lineWidth = 2;
      const branch = (x, y, len, angle, depth) => {
        if (depth === 0) return;
        const x2 = x + Math.cos(angle) * len, y2 = y + Math.sin(angle) * len;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x2, y2); ctx.stroke();
        branch(x2, y2, len * 0.7, angle - 0.55, depth - 1);
        branch(x2, y2, len * 0.7, angle + 0.55, depth - 1);
      };
      branch(MAP_W * T / 2, MAP_H * T - 48, 66, -Math.PI / 2, 5);
    } else if (id === 'graph_wastes') {
      const nodes = [[9, 9], [18, 7], [27, 11], [35, 8], [13, 21], [24, 23], [33, 19]];
      ctx.strokeStyle = 'rgba(184,180,196,0.4)';
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if ((i * 3 + j) % 3) continue;
          ctx.beginPath();
          ctx.moveTo(nodes[i][0] * T, nodes[i][1] * T);
          ctx.lineTo(nodes[j][0] * T, nodes[j][1] * T);
          ctx.stroke();
        }
      }
      ctx.fillStyle = 'rgba(216,216,224,0.75)';
      for (const [x, y] of nodes) ctx.fillRect(x * T - 3, y * T - 3, 6, 6);
    } else if (id === 'recursive_forest') {
      for (let d = 0; d < 5; d++) {
        const inset = d * 44 + Math.sin(t * 0.6) * 6;
        ctx.strokeStyle = `rgba(168,154,255,${0.3 - d * 0.045})`;
        ctx.strokeRect(inset + 64, inset + 44, MAP_W * T - 128 - inset * 2,
                       MAP_H * T - 88 - inset * 2);
      }
    } else if (id === 'stack_queue_mines') {
      for (let i = 0; i < 5; i++) {
        const y = 22 * T - i * 10 - (Math.sin(t + i) > 0.9 ? 4 : 0);
        ctx.fillStyle = 'rgba(232,195,125,0.5)';
        ctx.fillRect(11 * T, y, 26, 8);
      }
      for (let i = 0; i < 5; i++) {
        const x = 28 * T + ((t * 18 + i * 24) % 120);
        ctx.fillStyle = 'rgba(126,200,255,0.5)';
        ctx.fillRect(x, 11 * T, 8, 12);
      }
    } else if (id === 'complexity_tower') {
      for (let f = 0; f < 8; f++) {
        const lit = f <= (t * 0.6) % 9;
        ctx.fillStyle = lit ? 'rgba(126,200,255,0.26)' : 'rgba(126,200,255,0.06)';
        ctx.fillRect(MAP_W * T / 2 - 74, (24 - f * 2) * T, 148, T * 1.6);
      }
    }
    ctx.restore();
  }
}
