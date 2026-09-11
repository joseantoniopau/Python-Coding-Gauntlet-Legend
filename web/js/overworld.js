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
 */
import * as tiles from './tiles.js';
import * as sprites from './sprites.js';
import * as bosses from './bosses.js';
import * as pixel from './pixel.js';
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
    this._bindInput();
  }

  setEquipment(opts) {
    this.hero = sprites.heroSprites(opts || {});
  }

  _bindInput() {
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
      const dt = Math.min(0.05, (now - last) / 1000);
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
        out.push({ x: m.x, y: m.y, sortY: m.y * T, draw: (ctx) => {
          ctx.fillStyle = `rgba(232,195,125,${0.3 + Math.sin(this.time * 2) * 0.12})`;
          ctx.fillRect(m.x * T, m.y * T - 4, T, T + 8);
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
