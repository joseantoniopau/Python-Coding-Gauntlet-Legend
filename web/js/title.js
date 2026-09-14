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
import { createTitleArt } from './cinema.js';

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
    this.index = 0;
    this.entered = false;
    this.art = createTitleArt();

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

    this.shards = Array.from({ length: 14 }, (_, i) => ({
      a: (i / 14) * Math.PI * 2, r: 26 + seed() * 30, s: 2 + Math.floor(seed() * 3),
      speed: 0.16 + seed() * 0.22,
    }));

    this._key = (e) => this.onKey(e);
    window.addEventListener('keydown', this._key);
    this.mountMenu();
  }

  get options() {
    const out = [];
    if (this.hasSave) out.push({ id: 'continue', label: MENU_CONTINUE });
    out.push({ id: 'new', label: this.hasSave ? 'NEW ARCHITECT' : MENU_NEW });
    out.push({ id: 'settings', label: MENU_SETTINGS });
    out.push({ id: 'about', label: MENU_ABOUT });
    return out;
  }

  mountMenu() {
    const doc = this.canvas.ownerDocument || document;
    this._document = doc;
    const root = doc.createElement('div'); root.className = 'title-native';
    const style = doc.createElement('style');
    style.textContent = `.title-native{position:absolute;inset:0;z-index:2;pointer-events:none}.title-native .title-accessible-heading{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}.title-native nav{position:absolute;left:50%;transform:translateX(-50%);display:grid;gap:6px;pointer-events:auto;width:min(390px,calc(100% - 40px))}.title-native button{font:600 16px/1.3 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.06em;color:#c8c4d7;background:rgba(16,20,32,.9);border:1px solid #65667c;border-radius:3px;min-height:46px;padding:10px 18px;cursor:pointer;text-align:center;box-shadow:0 3px 0 #070b12}.title-native button.selected{color:#ffe0a8;border-color:#d3ab72;background:rgba(57,43,41,.96)}.title-native button:focus-visible{outline:3px solid #f9d091;outline-offset:3px}.title-native button:disabled{cursor:default;opacity:.65}.title-native .title-key-help{position:absolute;bottom:8px;left:0;width:100%;margin:0;text-align:center;font:13px/1.4 system-ui,sans-serif;color:#c3c1cd}.title-native nav.compact{width:min(600px,calc(100% - 32px));grid-template-columns:repeat(2,minmax(0,1fr))}.title-native nav.compact button{padding:8px;font-size:14px}@media(prefers-reduced-motion:reduce){.title-native *{scroll-behavior:auto}}`;
    // All names are real text. The artwork can remain a pixel composition.
    const heading = doc.createElement('h1'); heading.className = 'title-accessible-heading';
    heading.textContent = 'Python Coding Gauntlet Legend — The Algorithm Realms';
    const nav = doc.createElement('nav'); nav.setAttribute('aria-label', 'Main menu');
    this.buttons = this.options.map((option, i) => {
      const button = doc.createElement('button'); button.type = 'button';
      button.textContent = option.label;
      button.onclick = () => { this.index = i; this.syncMenu(); this.choose(option.id); };
      button.onfocus = () => {
        const moved = this.index !== i; this.index = i; this.syncMenu();
        if (moved && this.running) this.onSelect('move');
      };
      nav.appendChild(button); return button;
    });
    const help = doc.createElement('p'); help.className = 'title-key-help';
    help.textContent = 'Arrow keys or Tab · Enter to choose';
    root.appendChild(style); root.appendChild(heading); root.appendChild(nav); root.appendChild(help);
    this._priorAria = this.canvas.getAttribute('aria-hidden');
    this.canvas.setAttribute('aria-hidden', 'true');
    this.canvas.parentElement.appendChild(root);
    this.menuRoot = root; this.menu = nav; this.syncMenu();
    // About borrows the game's shared modal. Suspend the title controls while
    // that modal owns input, then restore the selected button on dismissal.
    const modal = doc.querySelector('#modal-bg');
    if (modal && typeof MutationObserver !== 'undefined') {
      this._modalObserver = new MutationObserver(() => this.syncModal());
      this._modalObserver.observe(modal, {attributes:true, attributeFilter:['class']});
    }
  }

  syncMenu() {
    this.buttons?.forEach((button, i) => {
      button.classList.toggle('selected', i === this.index);
      button.disabled = !!this._selected;
    });
  }

  syncModal() {
    const open = !!this._document.querySelector('#modal-bg.show');
    if (open === this._modalOpen) return;
    this._modalOpen = open;
    this.menuRoot.inert = open;
    if (open) {
      const first = this._document.querySelector('#modal button, #modal input, #modal select');
      if (first) first.focus();
    } else if (this.running && !this._selected) this.buttons[this.index]?.focus();
  }

  choose(id) {
    if (!this.running || this._selected || this._document.querySelector('#modal-bg.show')) return;
    // Continue/new/options leave through a short fade. Repeated Enter during
    // that fade must never create another run. About can be opened again.
    if (id !== 'about') { this._selected = true; this.syncMenu(); }
    this.onSelect(id);
    if (id === 'about') this.syncModal();
  }

  layout() {
    const preferredCell = Math.max(3, Math.min(10, Math.floor(this.w / 96)));
    const compact = this.h < 520;
    const rows = Math.ceil(this.options.length / (compact ? 2 : 1));
    const menuHeight = rows * 46 + Math.max(0, rows - 1) * 6;
    const menuTop = Math.min(this.h - menuHeight - 40, this.h * .6);
    const cell = Math.max(3, Math.min(preferredCell, Math.floor((menuTop - 64) / 15.2)));
    const logoTop = Math.min(this.h * .31, menuTop - cell * 15.2 - 36);
    return {cell, compact, menuTop, logoTop};
  }

  onKey(e) {
    if (!this.running || this._selected || e.metaKey || e.ctrlKey || e.altKey ||
        this._document.querySelector('#modal-bg.show')) return;
    const options = this.options;
    if (['ArrowDown','ArrowRight','s'].includes(e.key)) {
      e.preventDefault(); this.index = (this.index + 1) % options.length;
      this.syncMenu(); this.buttons[this.index]?.focus(); this.onSelect('move');
    } else if (['ArrowUp','ArrowLeft','w'].includes(e.key)) {
      e.preventDefault(); this.index = (this.index + options.length - 1) % options.length;
      this.syncMenu(); this.buttons[this.index]?.focus(); this.onSelect('move');
    } else if ((e.key === 'Enter' || e.key === ' ') && !this.buttons.includes(e.target)) {
      // Native buttons already turn Enter/Space into exactly one click.
      e.preventDefault(); this.choose(options[this.index].id);
    }
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.menuRoot.hidden = false;
    this.buttons[this.index]?.focus();
    if (this.reducedMotion) { this.time = 4; this.draw(); return; }
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
    if (this.menuRoot) this.menuRoot.hidden = true;
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  destroy() {
    this.stop();
    window.removeEventListener('keydown', this._key);
    this._modalObserver?.disconnect();
    this.buttons?.forEach(button => { button.onclick = button.onfocus = null; });
    this.menuRoot?.remove();
    if (this._priorAria === null) this.canvas.removeAttribute('aria-hidden');
    else this.canvas.setAttribute('aria-hidden', this._priorAria);
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const w = Math.max(280, Math.floor(rect.width));
    const h = Math.max(260, Math.floor(rect.height));
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.imageSmoothingEnabled = false;
    this.w = w; this.h = h;
    const layout = this.layout();
    this.menu.style.top = `${Math.round(layout.menuTop)}px`;
    this.menu.classList.toggle('compact', layout.compact);
    if (this.running && this.reducedMotion) this.draw();
  }

  draw() {
    const ctx = this.ctx;
    if (!this.w) this.resize();
    const { w, h } = this;
    const t = this.time;

    this.art.draw(ctx, w, h, t, this.reducedMotion);

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

    // --- the logo, assembling from falling runes
    const {cell, logoTop:y0} = this.layout();
    const logoW = Math.max(this.top.width, this.bottom.width) * cell;
    const x0 = (w - logoW) / 2;
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

    // --- footer
    ctx.textAlign = 'left';
    ctx.font = '10px "Press Start 2P", monospace';
    ctx.fillStyle = 'rgba(106,102,133,0.9)';
    ctx.fillText('v1.1.0', 14, h - 14);
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(106,102,133,0.75)';

    // --- quiet edge falloff; lettering stays free of scanlines
    const vig = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.42,
                                         w / 2, h / 2, Math.max(w, h) * 0.78);
    vig.addColorStop(0, 'rgba(0,0,0,0)');
    vig.addColorStop(1, 'rgba(0,0,0,0.52)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);
  }
}
