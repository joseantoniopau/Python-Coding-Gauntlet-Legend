/* The title screen.
 *
 * A 16-bit game is judged in its first four seconds, and until now this one
 * opened on a modal over a half-drawn map. This is a proper attract screen:
 * a parallax sky, a shattered Source turning overhead, the logo assembling
 * itself out of falling runes, and a menu you drive from the keyboard.
 *
 * Everything is drawn; there are no image assets.
 */
import * as pixel from './pixel.js';
import * as sprites from './sprites.js';

/* The logo, authored as a pixel grid. Two words, stacked, because
 * "PYTHON CODING GAUNTLET LEGEND" on one line at this resolution is unreadable. */
const GLYPHS = {
  A: ['.###.', '#...#', '#####', '#...#', '#...#'],
  B: ['####.', '#...#', '####.', '#...#', '####.'],
  C: ['.####', '#....', '#....', '#....', '.####'],
  D: ['####.', '#...#', '#...#', '#...#', '####.'],
  E: ['#####', '#....', '###..', '#....', '#####'],
  G: ['.####', '#....', '#..##', '#...#', '.###.'],
  H: ['#...#', '#...#', '#####', '#...#', '#...#'],
  I: ['#####', '..#..', '..#..', '..#..', '#####'],
  L: ['#....', '#....', '#....', '#....', '#####'],
  N: ['#...#', '##..#', '#.#.#', '#..##', '#...#'],
  O: ['.###.', '#...#', '#...#', '#...#', '.###.'],
  P: ['####.', '#...#', '####.', '#....', '#....'],
  R: ['####.', '#...#', '####.', '#..#.', '#...#'],
  T: ['#####', '..#..', '..#..', '..#..', '..#..'],
  U: ['#...#', '#...#', '#...#', '#...#', '.###.'],
  Y: ['#...#', '.#.#.', '..#..', '..#..', '..#..'],
  ' ': ['.....', '.....', '.....', '.....', '.....'],
};

function wordCells(word) {
  const cells = [];
  let cursor = 0;
  for (const ch of word) {
    const glyph = GLYPHS[ch] || GLYPHS[' '];
    for (let y = 0; y < glyph.length; y++) {
      for (let x = 0; x < glyph[y].length; x++) {
        if (glyph[y][x] === '#') cells.push({ x: cursor + x, y });
      }
    }
    cursor += 6;
  }
  return { cells, width: Math.max(0, cursor - 1) };
}

const MENU_NEW = 'BEGIN THE TRIAL';
const MENU_CONTINUE = 'CONTINUE';
const MENU_SETTINGS = 'OPTIONS';
const MENU_ABOUT = 'ABOUT';

export class TitleScreen {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.time = 0;
    this.born = 0;
    this.bornWall = 0;
    this.frames = 0;
    this.running = false;
    this.reducedMotion = !!opts.reducedMotion;
    this.hasSave = !!opts.hasSave;
    this.onSelect = opts.onSelect || (() => {});
    this.index = this.hasSave ? 1 : 0;
    this.entered = false;

    this.top = wordCells('GAUNTLET');
    this.bottom = wordCells('LEGEND');

    // each rune of the logo falls in from above and settles
    const seed = pixel.rng(0x51ade);
    this.runes = [];
    const place = (word, rowOffset) => {
      word.cells.forEach((c, i) => {
        this.runes.push({
          tx: c.x, ty: c.y + rowOffset,
          delay: 0.15 + seed() * 0.55 + i * 0.0022,
          spin: seed() * 6.28,
          driftX: (seed() - 0.5) * 26,
        });
      });
    };
    place(this.top, 0);
    place(this.bottom, 7);

    this.stars = Array.from({ length: 90 }, () => ({
      x: seed(), y: seed() * 0.62, s: seed() < 0.82 ? 1 : 2, tw: seed() * 6.28,
    }));
    this.shards = Array.from({ length: 14 }, (_, i) => ({
      a: (i / 14) * Math.PI * 2, r: 26 + seed() * 30, s: 2 + Math.floor(seed() * 3),
      speed: 0.16 + seed() * 0.22,
    }));
    this.embers = pixel.makeParticles('title', 480, 300, 54);

    this._key = (e) => this.onKey(e);
    window.addEventListener('keydown', this._key);
    this.canvas.addEventListener('click', (e) => this.onClick(e));
    this.canvas.style.cursor = 'pointer';
  }

  get options() {
    const out = [];
    if (this.hasSave) out.push({ id: 'continue', label: MENU_CONTINUE });
    out.push({ id: 'new', label: this.hasSave ? 'NEW ARCHITECT' : MENU_NEW });
    out.push({ id: 'settings', label: MENU_SETTINGS });
    out.push({ id: 'about', label: MENU_ABOUT });
    return out;
  }

  onKey(e) {
    if (!this.running) return;
    const options = this.options;
    if (e.key === 'ArrowDown' || e.key === 's') {
      e.preventDefault();
      this.index = (this.index + 1) % options.length;
      this.onSelect('move');
    } else if (e.key === 'ArrowUp' || e.key === 'w') {
      e.preventDefault();
      this.index = (this.index + options.length - 1) % options.length;
      this.onSelect('move');
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.onSelect(options[this.index].id);
    }
  }

  onClick(event) {
    if (!this.running || !this._hit) return;
    const rect = this.canvas.getBoundingClientRect();
    const y = (event.clientY - rect.top);
    for (const entry of this._hit) {
      if (y >= entry.top && y <= entry.bottom) {
        this.index = entry.index;
        this.onSelect(this.options[entry.index].id);
        return;
      }
    }
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.born = performance.now();
    this.bornWall = Date.now();
    this.frames = 0;
    const loop = (now) => {
      if (!this.running) return;
      this.frames++;
      // Three independent clocks, whichever has advanced furthest. Accumulated
      // dt stalls in a throttled tab, performance.now can be frozen by a virtual
      // clock, and frame count stalls if rAF is suspended — but not all three at
      // once, so the logo always finishes assembling.
      this.time = this.reducedMotion ? 4 : Math.max(
        (now - this.born) / 1000,
        (Date.now() - this.bornWall) / 1000,
        this.frames / 60);
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

  destroy() {
    this.stop();
    window.removeEventListener('keydown', this._key);
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const w = Math.max(480, Math.floor(rect.width));
    const h = Math.max(360, Math.floor(rect.height));
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.imageSmoothingEnabled = false;
    this.w = w; this.h = h;
  }

  draw() {
    const ctx = this.ctx;
    if (!this.w) this.resize();
    const { w, h } = this;
    const t = this.time;

    // --- sky: a vertical gradient, banded to stay in the palette's spirit
    const sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, '#0a0814');
    sky.addColorStop(0.45, '#1b1436');
    sky.addColorStop(0.72, '#3a2050');
    sky.addColorStop(1, '#6a2f44');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, h);

    // --- stars
    for (const s of this.stars) {
      const tw = 0.45 + Math.abs(Math.sin(t * 1.1 + s.tw)) * 0.55;
      ctx.fillStyle = `rgba(232,232,255,${tw * 0.8})`;
      ctx.fillRect((s.x * w) | 0, (s.y * h) | 0, s.s, s.s);
    }

    // --- the shattered Source, turning overhead
    const cx = w / 2, cy = h * 0.19;
    const pulse = 1 + Math.sin(t * 1.4) * 0.06;
    ctx.save();
    const glow = ctx.createRadialGradient(cx, cy, 4, cx, cy, 92 * pulse);
    glow.addColorStop(0, 'rgba(232,195,125,0.42)');
    glow.addColorStop(0.5, 'rgba(168,154,255,0.14)');
    glow.addColorStop(1, 'rgba(168,154,255,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(cx - 110, cy - 110, 220, 220);
    for (const shard of this.shards) {
      const a = shard.a + t * shard.speed;
      const r = shard.r * pulse;
      const x = cx + Math.cos(a) * r * 1.55;
      const y = cy + Math.sin(a) * r * 0.68;
      ctx.fillStyle = Math.sin(a * 2) > 0 ? '#e8c37d' : '#a89aff';
      ctx.globalAlpha = 0.55 + Math.sin(a) * 0.3;
      ctx.fillRect(x | 0, y | 0, shard.s, shard.s);
    }
    ctx.globalAlpha = 1;
    // the core: a broken square, deliberately not whole
    ctx.strokeStyle = '#ffe8a0';
    ctx.lineWidth = 2;
    for (let i = 0; i < 4; i++) {
      const a0 = (i / 4) * Math.PI * 2 + t * 0.25;
      const a1 = a0 + 1.1;
      ctx.beginPath();
      ctx.arc(cx, cy, 14 * pulse, a0, a1);
      ctx.stroke();
    }
    ctx.restore();

    // --- distant mountains, two parallax layers
    const ridge = (baseY, colour, amp, freq, offset) => {
      ctx.fillStyle = colour;
      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let x = 0; x <= w; x += 4) {
        const y = baseY + Math.sin((x + offset) * freq) * amp
          + Math.sin((x + offset) * freq * 2.3) * amp * 0.4;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fill();
    };
    ridge(h * 0.62, '#241a3a', 16, 0.011, t * 5);
    ridge(h * 0.72, '#1a1230', 22, 0.008, t * 9);
    ridge(h * 0.84, '#120c22', 12, 0.017, t * 15);

    // --- the logo, assembling from falling runes
    const cell = Math.max(4, Math.min(10, Math.floor(w / 96)));
    const logoW = Math.max(this.top.width, this.bottom.width) * cell;
    const x0 = (w - logoW) / 2;
    const y0 = h * 0.42;
    const topOffset = (Math.max(this.top.width, this.bottom.width) - this.top.width) / 2;
    const botOffset = (Math.max(this.top.width, this.bottom.width) - this.bottom.width) / 2;

    for (const rune of this.runes) {
      const settle = Math.min(1, Math.max(0, (t - rune.delay) / 0.75));
      if (settle <= 0) continue;
      const ease = 1 - Math.pow(1 - settle, 3);
      const isTop = rune.ty < 6;
      const nudge = isTop ? topOffset : botOffset;
      const tx = x0 + (rune.tx + nudge) * cell;
      const ty = y0 + rune.ty * cell;
      const fromY = ty - 150 - Math.abs(rune.driftX) * 1.4;
      const y = fromY + (ty - fromY) * ease;
      const x = tx + rune.driftX * (1 - ease);
      ctx.globalAlpha = 0.25 + ease * 0.75;
      if (ease < 1) {
        ctx.fillStyle = '#a89aff';
      } else {
        const shimmer = Math.sin(t * 2.2 + rune.tx * 0.25) * 0.5 + 0.5;
        ctx.fillStyle = isTop
          ? (shimmer > 0.7 ? '#ffe8a0' : '#e8c37d')
          : (shimmer > 0.7 ? '#d8c4ff' : '#a89aff');
      }
      ctx.fillRect(x | 0, y | 0, cell, cell);
      ctx.globalAlpha = 1;
    }

    // --- the words above and below
    ctx.textAlign = 'center';
    ctx.font = `${Math.max(9, Math.floor(cell * 1.35))}px "Press Start 2P", monospace`;
    ctx.fillStyle = 'rgba(232,232,245,0.72)';
    ctx.fillText('PYTHON CODING', w / 2, y0 - cell * 2.2);
    const sub = 'THE ALGORITHM REALMS';
    ctx.fillStyle = `rgba(168,154,255,${0.55 + Math.sin(t * 1.6) * 0.2})`;
    ctx.fillText(sub, w / 2, y0 + 12 * cell + cell * 3.2);

    // --- menu
    const options = this.options;
    const menuTop = Math.min(h - 40 - options.length * 34,
                             y0 + 12 * cell + cell * 3.2 + 44);
    this._hit = [];
    ctx.font = `${Math.max(9, Math.floor(cell * 1.7))}px "Press Start 2P", monospace`;
    options.forEach((option, i) => {
      const y = menuTop + i * 34;
      const active = i === this.index;
      if (active) {
        const width = ctx.measureText(option.label).width + 46;
        ctx.fillStyle = 'rgba(58,51,96,0.55)';
        ctx.fillRect(w / 2 - width / 2, y - 15, width, 24);
        ctx.strokeStyle = '#a89aff';
        ctx.lineWidth = 2;
        ctx.strokeRect(w / 2 - width / 2, y - 15, width, 24);
      }
      ctx.fillStyle = active ? '#ffe8a0' : 'rgba(155,150,184,0.85)';
      ctx.fillText(option.label, w / 2, y + 3);
      if (active && Math.sin(t * 6) > -0.3) {
        ctx.fillStyle = '#e8c37d';
        const width = ctx.measureText(option.label).width;
        ctx.fillRect(w / 2 - width / 2 - 18, y - 5, 7, 7);
      }
      this._hit.push({ index: i, top: y - 17, bottom: y + 11 });
    });

    // --- hero silhouette, watching from the ridge
    const heroFrames = this._hero || (this._hero = sprites.heroSprites({}));
    const idle = heroFrames.idle.down[Math.floor(t * 1.6) % 2];
    const scale = Math.max(2, Math.floor(cell / 2));
    const hx = w * 0.13, hy = h * 0.80;
    ctx.save();
    ctx.globalAlpha = 0.9;
    sprites.drawGroundShadow(ctx, hx + sprites.HERO_W * scale / 2,
                             hy + sprites.HERO_H * scale, 9 * scale / 2, 3, 0.34);
    ctx.drawImage(idle, hx, hy, sprites.HERO_W * scale, sprites.HERO_H * scale);
    ctx.restore();

    // --- embers drifting up
    pixel.stepParticles(this.embers, pixel.PARTICLE_STYLE.ember, w, h, 1 / 60);
    pixel.drawParticles(ctx, this.embers, pixel.PARTICLE_STYLE.ember, 0.4);

    // --- footer
    ctx.textAlign = 'left';
    ctx.font = '10px "Press Start 2P", monospace';
    ctx.fillStyle = 'rgba(106,102,133,0.9)';
    ctx.fillText('v1.1', 14, h - 14);
    ctx.textAlign = 'right';
    ctx.fillText('↑ ↓  ENTER', w - 14, h - 14);
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(106,102,133,0.75)';
    ctx.fillText('ORIGINAL WORK — NO THIRD-PARTY GAME ASSETS', w / 2, h - 14);

    // --- vignette + scanline feel
    const vig = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.42,
                                         w / 2, h / 2, Math.max(w, h) * 0.78);
    vig.addColorStop(0, 'rgba(0,0,0,0)');
    vig.addColorStop(1, 'rgba(0,0,0,0.52)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);
  }
}
