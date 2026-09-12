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
 */
import * as tiles from './tiles.js';
import * as sprites from './sprites.js';
import * as bosses from './bosses.js';
import * as pixel from './pixel.js';
import * as apexmod from './apex.js';
import { audio } from './audio.js';

const T = tiles.TILE_SIZE;
const MAP_W = 48;
const MAP_H = 34;

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
async function companionArt(animal, colour, tier) {
  const art = await petArtModule();
  if (art) {
    try {
      const set = art.petSprites(animal, { colour, tier });
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
  if (row.dead || row.lost || row.fallen || row.gone) return false;
  if (row.alive === false) return false;
  return true;
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

  markers.push({ kind: 'boss', x: MAP_W - 7, y: midY, id: `${region.id}-boss` });
  markers.push({ kind: 'exit', x: MAP_W - 3, y: midY, id: `${region.id}-exit-e` });
  markers.push({ kind: 'exit', x: 2, y: midY, id: `${region.id}-exit-w` });
  return markers;
}

const PARTICLE_FOR = {
  village: 'motes', grass: 'leaves', forest: 'leaves', deepforest: 'motes',
  canopy: 'leaves', swamp: 'motes', cave: 'ash', mine: 'ember',
  mountain: 'snow', highland: 'leaves', citadel: 'motes', wastes: 'ash',
  ruins: 'motes', dungeon: 'ash', tower: 'motes', arena: 'ember', castle: 'ember',
};

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
    this.particles = [];
    this.particleStyle = pixel.PARTICLE_STYLE.motes;
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

    this._bindInput();
  }

  setEquipment(opts) {
    this.hero = sprites.heroSprites(opts || {});
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
    this.particleStyle = pixel.PARTICLE_STYLE[PARTICLE_FOR[region.biome] || 'motes'];
    this.particles = pixel.makeParticles(region.id, MAP_W * T, MAP_H * T, 70);
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
    this.scale = Math.max(2, Math.min(4, Math.floor(Math.min(w / 340, h / 230))));
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
          if (Math.floor(this.time * 6) % 2 === 0) audio.sfx('move');
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
    pixel.stepParticles(this.particles, this.particleStyle, MAP_W * T, MAP_H * T, dt);
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
    const stamp = row ? `${row.id || animal}|${animal}|${colour}|${tier}` : '';
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
    companionArt(animal, colour, tier).then((built) => {
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
      if (m.x < view.x0 - 2 || m.x > view.x1 + 2
          || m.y < view.y0 - 3 || m.y > view.y1 + 3) continue;

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
        const key = m.kind === 'elite' ? 'construct' : 'slime';
        const motion = sprites.enemyMotion(key);
        const pose = sprites.idlePose(motion, t, m.x + m.y);
        const img = sprites.enemySprite(
          key, 'ARRAY', pose.frame, m.kind === 'elite' ? '#d84a7a' : null);
        const ox = (T - sprites.ENEMY_SIZE) / 2;
        out.push({ x: m.x, y: m.y, sortY: m.y * T + T, draw: (ctx) => {
          sprites.drawGroundShadow(ctx, m.x * T + T / 2, m.y * T + T - 1, 7, 3, 0.3);
          ctx.drawImage(img, m.x * T + ox + pose.dx,
                        m.y * T + T - sprites.ENEMY_SIZE + pose.dy);
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
    const img = frames[p.frame % frames.length];
    out.push({ x: p.x, y: p.y, sortY: p.py + T + 1, draw: (ctx) => {
      sprites.drawGroundShadow(ctx, p.px + T / 2, p.py + T - 1, 6, 3, 0.32);
      ctx.drawImage(img, Math.round(p.px), Math.round(p.py + T - sprites.HERO_H));
      if (!p.moving) {
        // a soft chevron above the head when standing still: enough to find
        // yourself in a village, not enough to be noise while walking
        const bob = Math.sin(this.time * 3) * 1.5;
        ctx.fillStyle = 'rgba(232,195,125,0.85)';
        ctx.fillRect(p.px + 6, p.py - 10 + bob, 4, 2);
        ctx.fillRect(p.px + 7, p.py - 8 + bob, 2, 2);
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
      const idle = c.art.idle;
      const strip = (!c.moving && idle && idle[cf]) ? idle[cf] : (c.art[cf] || c.art.down);
      const cimg = strip && (strip.length !== undefined ? strip[c.frame % strip.length] : strip);
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
        out.push({ x: Math.floor(c.px / T), y: Math.floor(c.py / T), sortY,
                   draw: (ctx) => {
          sprites.drawGroundShadow(ctx, sx, sy, sr, sry, 0.28);
          ctx.drawImage(cimg, cx, cy);
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

    return out;

  }

  draw() {
    if (!this.scene) return;
    const ctx = this.ctx;
    const s = this.scale;
    const camX = Math.max(0, Math.min(MAP_W * T - this.viewW / s,
                                      this.player.px - this.viewW / (2 * s) + T / 2));
    const camY = Math.max(0, Math.min(MAP_H * T - this.viewH / s,
                                      this.player.py - this.viewH / (2 * s) + T / 2));
    // Kept so a pointer event can be turned back into world space. Recomputing
    // the camera in the click handler would be a second copy of this clamp, and
    // the two would drift the first time either is touched.
    this._camX = camX; this._camY = camY;

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

    const hour = new Date().getHours();
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
