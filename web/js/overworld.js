/* The overworld: a tiled region you actually walk around.
 *
 * Each region's map is generated deterministically from its id, so the world is
 * stable across sessions, and its layout physically reflects the pattern it
 * teaches — the Marsh has a sliding frame of light, the Pass has a converging
 * bridge, the Ruins light up tiles you have already solved.
 */
import * as pixel from './pixel.js';
import { audio } from './audio.js';

const T = pixel.TILE_SIZE;
const MAP_W = 44;
const MAP_H = 30;

export const TILES = {
  GRASS: 0, PATH: 1, WATER: 2, TREE: 3, CLIFF: 4, STONE: 5,
  BUILDING: 6, SHRINE: 7, CHEST: 8, LAVA: 9,
};

const SOLID = new Set([TILES.WATER, TILES.TREE, TILES.CLIFF, TILES.BUILDING, TILES.LAVA]);

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function buildMap(region, tier) {
  const rand = pixel.rng(hash(region.id));
  const grid = Array.from({ length: MAP_H }, () => Array(MAP_W).fill(TILES.GRASS));
  const markers = [];

  const biome = region.biome;
  const wet = ['swamp', 'village', 'grass', 'canopy', 'deepforest'].includes(biome);
  const rocky = ['cave', 'mine', 'mountain', 'citadel', 'tower', 'ruins',
                 'dungeon', 'castle', 'wastes', 'arena', 'highland'].includes(biome);

  // base terrain
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const edge = x < 2 || y < 2 || x > MAP_W - 3 || y > MAP_H - 3;
      if (edge) { grid[y][x] = rocky ? TILES.CLIFF : TILES.TREE; continue; }
      const n = rand();
      if (rocky && n < 0.1) grid[y][x] = TILES.STONE;
      else if (!rocky && n < 0.09) grid[y][x] = TILES.TREE;
      else grid[y][x] = TILES.GRASS;
    }
  }

  // water / lava bodies
  if (wet && rand() < 0.85) {
    const cx = 6 + Math.floor(rand() * (MAP_W - 14));
    const cy = 5 + Math.floor(rand() * (MAP_H - 12));
    for (let y = -4; y <= 4; y++) {
      for (let x = -6; x <= 6; x++) {
        if (x * x / 36 + y * y / 12 < 1 && cy + y > 2 && cy + y < MAP_H - 3) {
          grid[cy + y][cx + x] = TILES.WATER;
        }
      }
    }
  }
  if (biome === 'mine' || biome === 'castle') {
    const cx = 8 + Math.floor(rand() * (MAP_W - 18));
    const cy = 6 + Math.floor(rand() * (MAP_H - 14));
    for (let y = -2; y <= 2; y++) {
      for (let x = -4; x <= 4; x++) {
        if (Math.abs(x) + Math.abs(y) * 2 < 6) grid[cy + y][cx + x] = TILES.LAVA;
      }
    }
  }

  // main road — every region is walkable end to end
  const roadY = Math.floor(MAP_H / 2);
  for (let x = 2; x < MAP_W - 2; x++) {
    grid[roadY][x] = TILES.PATH;
    grid[roadY + 1][x] = TILES.PATH;
  }
  const roadX = Math.floor(MAP_W / 2);
  for (let y = 3; y < MAP_H - 3; y++) grid[y][roadX] = TILES.PATH;

  // settlement
  const townX = 5, townY = roadY - 5;
  if (['village', 'highland', 'arena', 'citadel', 'castle'].includes(biome)
      || region.id === 'python_village') {
    for (let i = 0; i < 5; i++) {
      const bx = townX + (i % 3) * 4;
      const by = townY + Math.floor(i / 3) * 4;
      if (by < 2 || by > MAP_H - 4) continue;
      grid[by][bx] = TILES.BUILDING;
      grid[by][bx + 1] = TILES.BUILDING;
      markers.push({ kind: 'npc', x: bx, y: by + 1,
                     mentor: region.mentor, id: `${region.id}-npc-${i}` });
      if (i >= 2) break;
    }
  }

  // shrine, chests, boss pad, encounter nodes
  const place = (kind, count, extra = {}) => {
    for (let i = 0; i < count; i++) {
      let x, y, tries = 0;
      do {
        x = 3 + Math.floor(rand() * (MAP_W - 6));
        y = 3 + Math.floor(rand() * (MAP_H - 6));
        tries++;
      } while (tries < 80 && (SOLID.has(grid[y][x])
               || markers.some(m => m.x === x && m.y === y)));
      if (SOLID.has(grid[y][x])) continue;
      markers.push({ kind, x, y, id: `${region.id}-${kind}-${i}`, ...extra });
      if (kind === 'shrine') grid[y][x] = TILES.SHRINE;
      if (kind === 'chest') grid[y][x] = TILES.CHEST;
    }
  };

  place('shrine', 2);
  place('chest', 2);
  place('encounter', 7);
  place('elite', 1);

  markers.push({ kind: 'boss', x: MAP_W - 6, y: roadY, id: `${region.id}-boss` });
  markers.push({ kind: 'exit', x: MAP_W - 3, y: roadY, id: `${region.id}-exit-e` });
  markers.push({ kind: 'exit', x: 2, y: roadY, id: `${region.id}-exit-w` });

  return { grid, markers, spawn: { x: 4, y: roadY } };
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
    this.map = null;
    this.tiles = null;
    this.hero = pixel.heroSprites(pixel.PALETTES.spring);
    this.player = { x: 4, y: 15, px: 4 * T, py: 15 * T, facing: 'down', frame: 0,
                    moving: false, flip: false };
    this.keys = new Set();
    this.frameCount = 0;
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
    this._bindInput();
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
    this.tiles = pixel.tileset(region.id, region.palette, tier);
    this.map = buildMap(region, tier);
    const start = spawn || this.map.spawn;
    this.player.x = start.x; this.player.y = start.y;
    this.player.px = start.x * T; this.player.py = start.y * T;
    this.particleStyle = pixel.PARTICLE_STYLE[PARTICLE_FOR[region.biome] || 'motes'];
    this.particles = pixel.makeParticles(region.id, MAP_W * T, MAP_H * T, 60);
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
    // integer scale keeps pixels crisp on Retina
    this.scale = Math.max(2, Math.min(4, Math.floor(Math.min(w / 320, h / 220))));
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
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  stop() { this.running = false; }

  solid(x, y) {
    if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return true;
    return SOLID.has(this.map.grid[y][x]);
  }

  markerAt(x, y) {
    return this.map.markers.find(m => m.x === x && m.y === y
      && !['exit'].includes(m.kind) === true || (m.x === x && m.y === y));
  }

  update(dt) {
    this.time += dt;
    this.frameCount++;
    const p = this.player;
    const targetX = p.x * T, targetY = p.y * T;
    const speed = 110;

    if (Math.abs(p.px - targetX) > 0.5 || Math.abs(p.py - targetY) > 0.5) {
      p.moving = true;
      const dx = targetX - p.px, dy = targetY - p.py;
      const dist = Math.hypot(dx, dy);
      const step = Math.min(dist, speed * dt);
      p.px += (dx / dist) * step;
      p.py += (dy / dist) * step;
    } else {
      p.px = targetX; p.py = targetY;
      p.moving = false;
      let nx = p.x, ny = p.y, facing = p.facing, flip = p.flip;
      if (this.keys.has('arrowup') || this.keys.has('w')) { ny--; facing = 'up'; }
      else if (this.keys.has('arrowdown') || this.keys.has('s')) { ny++; facing = 'down'; }
      else if (this.keys.has('arrowleft') || this.keys.has('a')) { nx--; facing = 'side'; flip = true; }
      else if (this.keys.has('arrowright') || this.keys.has('d')) { nx++; facing = 'side'; flip = false; }
      if (nx !== p.x || ny !== p.y) {
        p.facing = facing; p.flip = flip;
        if (!this.solid(nx, ny)) {
          p.x = nx; p.y = ny;
          p.moving = true;
          if (this.frameCount % 3 === 0) audio.sfx('move');
          this.checkTile();
          if (this.onMove) this.onMove(p.x, p.y);
        }
      }
    }
    if (p.moving && !this.reducedMotion) {
      p.frame = Math.floor(this.time * 7) % 4;
    } else if (!p.moving) {
      p.frame = 0;
    }
    if (this.flash > 0) this.flash -= dt * 3;

    pixel.stepParticles(this.particles, this.particleStyle,
                        MAP_W * T, MAP_H * T, dt);
  }

  checkTile() {
    const m = this.map.markers.find(mk => mk.x === this.player.x && mk.y === this.player.y);
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
    const dirs = { up: [0, -1], down: [0, 1], side: [p.flip ? -1 : 1, 0] };
    const [dx, dy] = dirs[p.facing];
    const candidates = [[p.x, p.y], [p.x + dx, p.y + dy]];
    for (const [x, y] of candidates) {
      const m = this.map.markers.find(mk => mk.x === x && mk.y === y);
      if (m && this.onEnter) {
        if ((m.kind === 'encounter' || m.kind === 'elite') && this.solvedNodes.has(m.id)) {
          continue;
        }
        audio.sfx('select');
        this.onEnter(m);
        return;
      }
    }
  }

  draw() {
    const ctx = this.ctx;
    const s = this.scale;
    const viewTilesX = Math.ceil(this.viewW / (T * s)) + 2;
    const viewTilesY = Math.ceil(this.viewH / (T * s)) + 2;
    const camX = Math.max(0, Math.min(MAP_W * T - this.viewW / s,
                                      this.player.px - this.viewW / (2 * s) + T / 2));
    const camY = Math.max(0, Math.min(MAP_H * T - this.viewH / s,
                                      this.player.py - this.viewH / (2 * s) + T / 2));

    const pal = this.tiles.palette;
    ctx.fillStyle = pal.sky;
    ctx.fillRect(0, 0, this.viewW, this.viewH);

    ctx.save();
    ctx.scale(s, s);
    ctx.translate(-Math.round(camX), -Math.round(camY));

    const waterFrame = Math.floor(this.time * 4) % 4;
    const startX = Math.max(0, Math.floor(camX / T) - 1);
    const startY = Math.max(0, Math.floor(camY / T) - 1);
    for (let y = startY; y < Math.min(MAP_H, startY + viewTilesY); y++) {
      for (let x = startX; x < Math.min(MAP_W, startX + viewTilesX); x++) {
        const t = this.map.grid[y][x];
        let img;
        switch (t) {
          case TILES.WATER: img = this.tiles.water[waterFrame]; break;
          case TILES.LAVA: img = this.tiles.lava[waterFrame]; break;
          case TILES.PATH: img = this.tiles.path; break;
          case TILES.TREE: img = this.tiles.tree[(x * 5 + y * 11) % 3]; break;
          case TILES.CLIFF: img = this.tiles.cliff; break;
          case TILES.STONE: img = this.tiles.stone; break;
          case TILES.BUILDING: img = this.tiles.building[Math.min(3, this.tier)]; break;
          case TILES.SHRINE: img = this.tiles.shrine; break;
          case TILES.CHEST: img = this.tiles.chest; break;
          default: img = this.tiles.ground[(x * 7 + y * 3) % 4];
        }
        ctx.drawImage(img, x * T, y * T);
      }
    }

    // region-specific physical motif
    this.drawMotif(ctx, camX, camY);

    // markers
    for (const m of this.map.markers) {
      if (m.x < startX - 1 || m.x > startX + viewTilesX) continue;
      if (m.kind === 'encounter' || m.kind === 'elite') {
        if (this.solvedNodes.has(m.id)) {
          ctx.globalAlpha = 0.35;
          ctx.fillStyle = '#8fd07a';
          ctx.fillRect(m.x * T + 6, m.y * T + 6, 4, 4);
          ctx.globalAlpha = 1;
          continue;
        }
        const bob = Math.sin(this.time * 3 + m.x) * 1.5;
        const sprite = pixel.enemySprite(
          m.kind === 'elite' ? 'construct' : 'slime', 'ARRAY',
          Math.floor(this.time * 3) % 2,
          m.kind === 'elite' ? '#d84a7a' : null);
        ctx.drawImage(sprite, m.x * T, m.y * T + bob);
      } else if (m.kind === 'npc') {
        const sprite = this.hero.down[0];
        ctx.save();
        ctx.globalAlpha = 0.95;
        ctx.drawImage(sprite, m.x * T + 2, m.y * T);
        ctx.restore();
        ctx.fillStyle = '#ffe8a0';
        ctx.fillRect(m.x * T + 7, m.y * T - 5, 2, 2);
      } else if (m.kind === 'boss') {
        const pulse = Math.sin(this.time * 2) * 2;
        ctx.drawImage(pixel.bossSprite('titan', '#d84a7a',
                                       Math.floor(this.time * 2) % 2),
                      m.x * T - 16, m.y * T - 20 + pulse);
      } else if (m.kind === 'exit') {
        ctx.fillStyle = 'rgba(232,195,125,0.5)';
        ctx.fillRect(m.x * T, m.y * T - 4, T, T + 8);
      }
    }

    // hero
    const frames = this.hero[this.player.facing];
    const sprite = frames[this.player.frame];
    ctx.save();
    if (this.player.flip && this.player.facing === 'side') {
      ctx.translate(Math.round(this.player.px) + 12, Math.round(this.player.py));
      ctx.scale(-1, 1);
      ctx.drawImage(sprite, 0, 0);
    } else {
      ctx.drawImage(sprite, Math.round(this.player.px), Math.round(this.player.py));
    }
    ctx.restore();

    pixel.drawParticles(ctx, this.particles, this.particleStyle, 0.5);
    ctx.restore();

    // day/night tint driven by the wall clock, so a night session actually looks like one
    const hour = new Date().getHours();
    const night = hour >= 21 || hour < 5;
    const dusk = hour >= 18 && hour < 21;
    if (night) {
      ctx.fillStyle = 'rgba(24,26,64,0.16)';
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    } else if (dusk) {
      ctx.fillStyle = 'rgba(80,40,30,0.07)';
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    }
    if (this.flash > 0) {
      ctx.fillStyle = `rgba(255,255,255,${this.flash * 0.4})`;
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    }

    // vignette
    const grad = ctx.createRadialGradient(
      this.viewW / 2, this.viewH / 2, Math.min(this.viewW, this.viewH) * 0.52,
      this.viewW / 2, this.viewH / 2, Math.max(this.viewW, this.viewH) * 0.80);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(1, 'rgba(0,0,0,0.26)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, this.viewW, this.viewH);
  }

  /* The world reinforces the mental model: each region draws the shape of its
   * own algorithm across the terrain. */
  drawMotif(ctx, camX, camY) {
    const id = this.region.id;
    const t = this.time;
    ctx.save();
    if (id === 'sliding_window_marsh') {
      const width = (6 + Math.sin(t * 0.7) * 3) * T;
      const left = (10 + Math.sin(t * 0.35) * 6) * T;
      ctx.strokeStyle = 'rgba(168,154,255,0.85)';
      ctx.lineWidth = 2;
      ctx.strokeRect(left, 6 * T, width, 18 * T);
      ctx.fillStyle = 'rgba(168,154,255,0.10)';
      ctx.fillRect(left, 6 * T, width, 18 * T);
    } else if (id === 'twin_pointer_pass') {
      const span = MAP_W * T;
      const phase = (Math.sin(t * 0.5) * 0.5 + 0.5) * 0.42;
      const lx = span * phase, rx = span * (1 - phase);
      ctx.fillStyle = 'rgba(126,200,255,0.8)';
      ctx.fillRect(lx, 14 * T, 3, 3 * T);
      ctx.fillStyle = 'rgba(255,157,74,0.8)';
      ctx.fillRect(rx, 14 * T, 3, 3 * T);
    } else if (id === 'dp_ruins') {
      for (let i = 0; i < 14; i++) {
        const lit = (Math.sin(t * 0.8 - i * 0.5) + 1) / 2;
        ctx.fillStyle = `rgba(255,217,122,${0.08 + lit * 0.22})`;
        ctx.fillRect((6 + i * 2) * T, 12 * T, T * 2, T * 2);
      }
    } else if (id === 'binary_tree_canopy') {
      ctx.strokeStyle = 'rgba(143,208,122,0.5)';
      ctx.lineWidth = 2;
      const drawBranch = (x, y, len, angle, depth) => {
        if (depth === 0) return;
        const x2 = x + Math.cos(angle) * len, y2 = y + Math.sin(angle) * len;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x2, y2); ctx.stroke();
        drawBranch(x2, y2, len * 0.7, angle - 0.55, depth - 1);
        drawBranch(x2, y2, len * 0.7, angle + 0.55, depth - 1);
      };
      drawBranch(MAP_W * T / 2, MAP_H * T - 40, 60, -Math.PI / 2, 5);
    } else if (id === 'graph_wastes') {
      const nodes = [[8, 8], [16, 6], [24, 10], [32, 7], [12, 18], [22, 20], [30, 17]];
      ctx.strokeStyle = 'rgba(184,180,196,0.45)';
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
      ctx.fillStyle = 'rgba(216,216,224,0.8)';
      for (const [x, y] of nodes) ctx.fillRect(x * T - 3, y * T - 3, 6, 6);
    } else if (id === 'recursive_forest') {
      for (let d = 0; d < 5; d++) {
        const inset = d * 40 + Math.sin(t * 0.6) * 6;
        ctx.strokeStyle = `rgba(168,154,255,${0.35 - d * 0.05})`;
        ctx.strokeRect(inset + 60, inset + 40, MAP_W * T - 120 - inset * 2,
                       MAP_H * T - 80 - inset * 2);
      }
    } else if (id === 'stack_queue_mines') {
      for (let i = 0; i < 5; i++) {
        const y = 20 * T - i * 10 - (Math.sin(t + i) > 0.9 ? 4 : 0);
        ctx.fillStyle = 'rgba(232,195,125,0.55)';
        ctx.fillRect(10 * T, y, 26, 8);
      }
      for (let i = 0; i < 5; i++) {
        const x = 26 * T + ((t * 18 + i * 24) % 120);
        ctx.fillStyle = 'rgba(126,200,255,0.55)';
        ctx.fillRect(x, 10 * T, 8, 12);
      }
    } else if (id === 'complexity_tower') {
      for (let f = 0; f < 8; f++) {
        const lit = f <= (t * 0.6) % 9;
        ctx.fillStyle = lit ? 'rgba(126,200,255,0.30)' : 'rgba(126,200,255,0.07)';
        ctx.fillRect(MAP_W * T / 2 - 70, (22 - f * 2) * T, 140, T * 1.6);
      }
    }
    ctx.restore();
  }
}
