/* Python Coding Gauntlet Legend — the battle feedback layer.
 *
 * Everything the player feels when a cast lands lives here: the stage the fight
 * happens on, the hit that reads as a hit, the spell that reads as a spell, and
 * the close of a fight that reads as a close rather than a modal appearing.
 *
 * This module owns one canvas and one animation loop. It never touches game
 * state, never reads the API, and never decides anything — callers tell it what
 * happened and it renders that. Keeping it read-only about the game is what lets
 * it be dropped into the battle screen without disturbing the grading path.
 *
 * All art is generated here or in pixel.js. Nothing is traced or sampled.
 *
 * Nothing in here supplies an answer. Spell animations are keyed to the spell
 * the player already paid focus for; they render the cast, never its contents.
 */
import * as pixel from './pixel.js';
import * as sprites from './sprites.js';
import * as bosses from './bosses.js';
import * as spellfx from './spellfx.js';
import * as stagelayer from './battlescene.js';

/* ---------------- stage geometry ----------------
 * The stage is drawn in a fixed logical grid and then scaled by a whole number,
 * so a source pixel is always an exact square of screen pixels. Every offset
 * below is in logical units. */
export const STAGE = Object.freeze({
  w: 192,
  h: 128,
  ground: 100,   // horizon: where feet land and shadows sit
  heroX: 46,     // foot centres, not sprite origins
  enemyX: 136,
});

/* Damage readouts are colour-coded because the player has to tell four
 * different outcomes apart at a glance, mid-sequence. These match the CSS
 * custom properties in game.css so the stage and the panels agree. */
export const DAMAGE_KIND = Object.freeze({
  HIT: 'hit',
  CRIT: 'crit',
  RESIST: 'resist',
  HEAL: 'heal',
  MISS: 'miss',
});

const DAMAGE_STYLE = {
  hit:    { colour: '#ffe8a0', outline: '#3a2a10', size: 9,  rise: 22, shake: 2 },
  crit:   { colour: '#ffd97a', outline: '#4a2a00', size: 13, rise: 30, shake: 5 },
  resist: { colour: '#9b96b8', outline: '#14121f', size: 8,  rise: 16, shake: 0 },
  heal:   { colour: '#8fd07a', outline: '#132a10', size: 9,  rise: 24, shake: 0 },
  miss:   { colour: '#7ec8ff', outline: '#0b1a2a', size: 8,  rise: 18, shake: 0 },
};

/* The six hint spells the server can grant. VISION is in HINT_SPELLS alongside
 * the five named in the brief, so it gets its own look rather than a default. */
export const SPELL_FX = Object.freeze([
  'ORACLE', 'REVEAL_PATH', 'VISION', 'PSEUDOSIGHT', 'CODE_FRAGMENT', 'PHOENIX',
]);

const RANK_COLOUR = {
  S: '#ffe8a0', A: '#8fd07a', B: '#7ec8ff', C: '#ff9d4a',
  LEARNING_CLEAR: '#a89aff',
};

/* Which silhouette family a region's backdrop is built from. Sixteen regions
 * share four generators; the palette does the rest of the work. */
const BIOME_FORM = {
  village: 'spires', grass: 'trees', highland: 'peaks', forest: 'trees',
  cave: 'vault', swamp: 'trees', mountain: 'peaks', mine: 'vault',
  citadel: 'spires', deepforest: 'trees', canopy: 'trees', wastes: 'peaks',
  ruins: 'spires', dungeon: 'vault', tower: 'spires', arena: 'spires',
  castle: 'spires',
};

/* Ambient weather per biome, reusing the particle system pixel.js already has
 * so the overworld and the battle stage share one look. */
const BIOME_WEATHER = {
  village: 'motes', grass: 'leaves', highland: 'leaves', forest: 'leaves',
  cave: 'ash', swamp: 'motes', mountain: 'snow', mine: 'ember',
  citadel: 'motes', deepforest: 'leaves', canopy: 'leaves', wastes: 'ash',
  ruins: 'ash', dungeon: 'ash', tower: 'motes', arena: 'ember',
  castle: 'ash',
};

/* ---------------- small deterministic helpers ---------------- */

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < String(str).length; i++) {
    h ^= String(str).charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const lerp = (a, b, k) => a + (b - a) * k;
/* Ease-out that overshoots slightly. Used for anything that should land with
 * weight rather than glide to a stop. */
const overshoot = (k) => {
  const t = k - 1;
  return t * t * (2.70158 * t + 1.70158) + 1;
};
const easeOut = (k) => 1 - (1 - k) * (1 - k);
const easeIn = (k) => k * k;

function offscreen(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return { canvas: c, ctx: x };
}

function withAlpha(hex, a) {
  const n = parseInt(String(hex).replace('#', '').slice(0, 6), 16) || 0;
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/* ---------------- backdrop generation ----------------
 * Each layer is rasterised once per scene into a canvas twice the stage width,
 * so parallax is a wrapped blit rather than a per-frame redraw. */

function silhouette(form, pal, seed, width, height, colour) {
  const { canvas, ctx } = offscreen(width, height);
  const rand = pixel.rng(seed);
  ctx.fillStyle = colour;
  if (form === 'peaks') {
    let x = 0;
    while (x < width) {
      const w = 18 + Math.floor(rand() * 26);
      const h = 14 + Math.floor(rand() * (height - 16));
      for (let i = 0; i < w; i++) {
        const t = Math.abs(i - w / 2) / (w / 2);
        const col = Math.round(h * (1 - t * t));
        ctx.fillRect(x + i, height - col, 1, col);
      }
      x += Math.floor(w * 0.72);
    }
  } else if (form === 'trees') {
    for (let x = 0; x < width; x += 3 + Math.floor(rand() * 3)) {
      const h = 10 + Math.floor(rand() * (height - 12));
      const w = 4 + Math.floor(rand() * 5);
      ctx.fillRect(x + (w >> 1) - 1, height - h, 2, h);           // trunk
      for (let r = 0; r < 4; r++) {                                // canopy steps
        const cw = w + (3 - r) * 2;
        ctx.fillRect(x + (w >> 1) - (cw >> 1), height - h - r * 3 - 6, cw, 4);
      }
    }
  } else if (form === 'spires') {
    let x = 0;
    while (x < width) {
      const w = 8 + Math.floor(rand() * 12);
      const h = 12 + Math.floor(rand() * (height - 14));
      ctx.fillRect(x, height - h, w, h);
      if (rand() < 0.55) {                                        // roof
        for (let i = 0; i < w >> 1; i++) {
          ctx.fillRect(x + i, height - h - (w >> 1) + i, w - i * 2, 1);
        }
      } else {                                                    // battlements
        for (let i = 0; i < w; i += 3) ctx.fillRect(x + i, height - h - 3, 2, 3);
      }
      x += w + 2 + Math.floor(rand() * 6);
    }
  } else {                                                        // vault
    let x = 0;
    while (x < width) {
      const w = 12 + Math.floor(rand() * 14);
      const h = 16 + Math.floor(rand() * (height - 18));
      ctx.fillRect(x, height - h, w, h);
      const arch = Math.max(3, w - 6);
      ctx.clearRect(x + ((w - arch) >> 1), height - Math.floor(h * 0.62), arch,
                    Math.floor(h * 0.62));
      for (let i = 0; i < arch >> 1; i++) {                        // arch crown
        ctx.fillRect(x + ((w - arch) >> 1) + i,
                     height - Math.floor(h * 0.62) - (arch >> 1) + i,
                     arch - i * 2, 1);
      }
      x += w + 4 + Math.floor(rand() * 8);
    }
  }
  return canvas;
}

function buildBackdrop(pal, biome, seed) {
  const W = STAGE.w * 2;
  const form = BIOME_FORM[biome] || 'peaks';

  // Sky: a vertical ramp from the palette's sky toward its far colour, banded in
  // whole rows so it reads as 16-bit dithering rather than a CSS gradient.
  const sky = offscreen(STAGE.w, STAGE.ground + 2);
  const bands = 10;
  for (let i = 0; i < bands; i++) {
    const k = i / (bands - 1);
    sky.ctx.fillStyle = pixel.shade(pal.sky, Math.round(lerp(-14, 16, k)));
    const y0 = Math.round((i / bands) * (STAGE.ground + 2));
    const y1 = Math.round(((i + 1) / bands) * (STAGE.ground + 2));
    sky.ctx.fillRect(0, y0, STAGE.w, y1 - y0);
  }
  // A low sun band just above the horizon gives the scene a light direction.
  sky.ctx.fillStyle = withAlpha(pal.accent, 0.16);
  sky.ctx.fillRect(0, STAGE.ground - 18, STAGE.w, 18);

  const far = silhouette(form, pal, seed + 11, W, 46, pixel.shade(pal.far, -6));
  const mid = silhouette(form, pal, seed + 97, W, 34, pixel.shade(pal.mid, -22));

  // Ground plane, with a lit lip on the horizon line and a darker apron in front.
  const ground = offscreen(STAGE.w, STAGE.h - STAGE.ground + 1);
  const gh = ground.canvas.height;
  ground.ctx.fillStyle = pal.ground;
  ground.ctx.fillRect(0, 0, STAGE.w, gh);
  ground.ctx.fillStyle = pixel.shade(pal.ground, 26);
  ground.ctx.fillRect(0, 0, STAGE.w, 1);
  ground.ctx.fillStyle = pixel.shade(pal.ground, -20);
  ground.ctx.fillRect(0, Math.floor(gh * 0.55), STAGE.w, gh);
  const grand = pixel.rng(seed + 5);
  for (let i = 0; i < 220; i++) {
    const x = Math.floor(grand() * STAGE.w);
    const y = Math.floor(grand() * gh);
    ground.ctx.fillStyle = pixel.shade(pal.ground, grand() < 0.5 ? 14 : -16);
    ground.ctx.fillRect(x, y, 1 + (grand() < 0.2 ? 1 : 0), 1);
  }

  return { sky: sky.canvas, far, mid, ground: ground.canvas };
}

/* ---------------- the layer ---------------- */

export class BattleFX {
  /* host may be omitted and supplied later via mount(). */
  constructor(host, opts = {}) {
    this.opts = opts;
    this.audio = opts.audio || null;
    this.reducedMotion = !!opts.reducedMotion;

    this.el = null;
    this.canvas = null;
    this.ctx = null;
    this.host = null;
    this.ro = null;
    this.raf = 0;
    this.running = false;
    this.last = 0;
    this.clock = 0;
    this.px = 3;
    this.ox = 0;
    this.oy = 0;

    this.scene = null;          // {pal, biome, backdrop, enemy, pattern, boss}
    this.sprites = new Map();   // frame/variant cache; battles repeat, canvases should not
    this.flashCache = new WeakMap();
    this.hero = null;

    this.numbers = [];
    this.particles = [];
    this.effects = [];
    this.weather = null;
    this.weatherStyle = null;

    this.hp = 1; this.hpMax = 1; this.hpShown = 1;
    this.pips = 0; this.pipsLit = 0;
    this.combo = 0; this.comboMult = 1; this.comboGlow = 0;
    this.shakeMag = 0;
    this.stage3d = null;
    this.cam = null;
    this.bossFrame = 0;
    this.bossState = 'idle';
    this.bossStateT = 0;
    this.knock = 0;
    this.flash = 0;
    this.tintColour = null; this.tint = 0;
    this.heroLunge = 0;
    this.heroPose = 0;
    this.dissolving = 0;
    this.enemyAlpha = 1;
    this.xpShown = 0; this.xpTarget = 0; this.xpBar = null;
    this.banner = null;
    this.nameCard = null;
    this.crawl = null;
    this.chips = [];

    this.timers = [];
    this.pending = new Set();
    this._seq = 0;

    this._frame = this._frame.bind(this);
    this._resize = this._resize.bind(this);

    if (host) this.mount(host);
  }

  /* ---------------- lifecycle ---------------- */

  /* Creates its own DOM so nothing in index.html has to change. The wrapper is
   * absolutely positioned over the host and ignores pointer events, so buttons
   * and tabs underneath keep working. */
  mount(host) {
    const node = typeof host === 'string' ? document.querySelector(host) : host;
    if (!node) throw new Error('BattleFX.mount: no host element');
    if (this.el) this.unmount();

    BattleFX._ensureStyle();
    if (getComputedStyle(node).position === 'static') node.style.position = 'relative';

    this.el = document.createElement('div');
    this.el.className = 'fx-stage';
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'fx-canvas';
    this.el.appendChild(this.canvas);
    node.appendChild(this.el);

    this.ctx = this.canvas.getContext('2d');
    this.host = node;

    if (typeof ResizeObserver === 'function') {
      this.ro = new ResizeObserver(this._resize);
      this.ro.observe(node);
    } else {
      window.addEventListener('resize', this._resize);
    }
    this._resize();
    return this.el;
  }

  unmount() {
    this.stop();
    if (this.ro) { this.ro.disconnect(); this.ro = null; }
    else window.removeEventListener('resize', this._resize);
    if (this.el && this.el.parentNode) this.el.parentNode.removeChild(this.el);
    this.el = null; this.canvas = null; this.ctx = null; this.host = null;
  }

  /* Full teardown. Safe to call twice; safe to call mid-sequence. Any promise a
   * caller is awaiting resolves rather than rejects, because a torn-down stage
   * is not an error the battle flow should have to catch. */
  destroy() {
    this._flushPending();
    this.timers.length = 0;
    this.numbers.length = 0;
    this.particles.length = 0;
    this.effects.length = 0;
    this.chips.length = 0;
    this.sprites.clear();
    this.flashCache = new WeakMap();
    if (this.stage3d) { stagelayer.destroyScene(this.stage3d); this.stage3d = null; }
    this.cam = null;
    this.scene = null;
    this.hero = null;
    this.weather = null;
    this.unmount();
  }

  setReducedMotion(v) { this.reducedMotion = !!v; }
  setAudio(a) { this.audio = a || null; }

  start() {
    if (this.running || !this.ctx) return;
    this.running = true;
    this.last = 0;
    this.raf = requestAnimationFrame(this._frame);
  }

  stop() {
    this.running = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
    // The render clock is the only thing that services a wait, so cancelling the
    // loop strands every wait already queued. Hand each one to wall time on the
    // way out. Whichever clock arrives first takes the entry out of `pending`,
    // so a stage that is started again still resolves on the render clock and
    // nothing is ever resolved twice.
    for (const entry of this.pending) this._settleLater(entry, entry.at - this.clock);
  }

  /* ---------------- scene ---------------- */

  /* Call once per encounter, before start().
   *   region  { id, biome, palette }            — straight from state.regions
   *   enemy   { name, sprite, colour, boss, hp, hp_max }
   *   pattern the problem's pattern, used for the family colour on non-bosses
   *   heroPalette optional palette override for the player sprite            */
  setScene({ region, enemy, pattern, heroPalette } = {}) {
    if (this.stage3d) { stagelayer.destroyScene(this.stage3d); this.stage3d = null; }
    const palName = (region && region.palette) || 'spring';
    const pal = pixel.PALETTES[palName] || pixel.PALETTES.spring;
    const biome = (region && region.biome) || 'grass';
    const seed = hash((region && region.id) || palName);

    this.clearEffects();
    this.sprites.clear();

    this.scene = {
      pal, biome, seed,
      backdrop: buildBackdrop(pal, biome, seed),
      enemy: enemy || { name: '—', sprite: 'slime', boss: false },
      pattern: pattern || 'ARRAY',
      boss: !!(enemy && enemy.boss),
      drift: 0,
    };

    // The stage is the expensive part and the only allocating call, so it is
    // built exactly once per encounter and torn down above.
    try {
      this.stage3d = stagelayer.createScene({
        biome,
        boss: enemy && enemy.boss ? enemy : false,
        palette: palName,
        reducedMotion: this.reducedMotion,
        key: (region && region.id) || palName,
        stage: STAGE,
      });
      // `camera` is a module singleton, so its decay values survive a fight
      // unless it is explicitly reset between encounters.
      this.cam = stagelayer.camera.reset();
      this.cam.setReducedMotion(this.reducedMotion);
      if (enemy && enemy.boss) this.cam.push(4.5);
    } catch (err) {
      this.stage3d = null;
      this.cam = null;
    }
    this.bossFrame = 0;
    this.bossState = 'idle';
    this.bossStateT = 0;

    this.weatherStyle = pixel.PARTICLE_STYLE[BIOME_WEATHER[biome] || 'motes'];
    this.weather = pixel.makeParticles(biome, STAGE.w, STAGE.ground, 26);

    try {
      this.hero = sprites.heroSprites(pixel.PALETTES[heroPalette] || pal);
    } catch (e) {
      this.hero = null;   // the stage is still worth showing without a hero
    }

    this.hpMax = Math.max(1, (enemy && enemy.hp_max) || 1);
    this.hp = (enemy && enemy.hp !== undefined) ? enemy.hp : this.hpMax;
    this.hpShown = this.hp;
    this.pips = this.scene.boss ? this.hpMax : 0;
    this.pipsLit = this.pips;
    this.enemyAlpha = 1;
    this.dissolving = 0;
    this.knock = 0;
    this.flash = 0;
    this.shakeMag = 0;
    this.xpShown = 0; this.xpTarget = 0; this.xpBar = null;
    return this;
  }

  /* Wipes every transient. Used between encounters and by destroy(). */
  clearEffects() {
    this._flushPending();
    this.timers.length = 0;
    this.numbers.length = 0;
    this.particles.length = 0;
    this.effects.length = 0;
    this.chips.length = 0;
    this.banner = null;
    this.nameCard = null;
    this.crawl = null;
    this.tint = 0;
    this.tintColour = null;
    this.heroLunge = 0;
    this.dissolving = 0;
    this.enemyAlpha = 1;
    return this;
  }

  /* ---------------- public beats ---------------- */

  setEnemyHp(current, max) {
    if (max !== undefined) this.hpMax = Math.max(1, max);
    this.hp = clamp(current, 0, this.hpMax);
    if (this.reducedMotion) this.hpShown = this.hp;
    if (this.pips) this.pipsLit = this.hp;
    return this;
  }

  /* multiplier is the XP multiplier the server reports; count is the streak. */
  setCombo(count, multiplier) {
    const rising = (multiplier || 1) > this.comboMult;
    this.combo = count || 0;
    this.comboMult = multiplier || 1;
    if (rising && !this.reducedMotion) this.comboGlow = 1;
    return this;
  }

  shake(mag) {
    if (this.reducedMotion) return this;
    this.shakeMag = Math.max(this.shakeMag, mag);
    if (this.cam) this.cam.shake(mag * 0.6);
    return this;
  }

  burst({ x, y, colour = '#ffe8a0', count = 14, power = 46, gravity = 150,
          size = 1, life = 0.5 } = {}) {
    const n = this.reducedMotion ? Math.min(4, count) : count;
    for (let i = 0; i < n; i++) {
      const a = (Math.PI * 2 * i) / n + Math.random() * 0.5;
      const sp = power * (0.35 + Math.random() * 0.8);
      this.particles.push({
        x, y,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp - power * 0.25,
        g: gravity, size, colour,
        t: 0, life: life * (0.6 + Math.random() * 0.8),
      });
    }
    return this;
  }

  /* A floating readout. value may be a number or a short string. */
  damageNumber(value, { kind = DAMAGE_KIND.HIT, x, y } = {}) {
    const style = DAMAGE_STYLE[kind] || DAMAGE_STYLE.hit;
    const ex = x === undefined ? STAGE.enemyX : x;
    const ey = y === undefined ? STAGE.ground - 46 : y;
    this.numbers.push({
      text: typeof value === 'number' ? String(Math.round(value)) : String(value),
      x: ex + (Math.random() * 14 - 7),
      y: ey,
      style,
      t: 0,
      dur: this.reducedMotion ? 0.7 : 1.05,
      drift: (Math.random() - 0.5) * 10,
    });
    return this;
  }

  /* One landed blow. Everything a hit is made of, in one call. */
  hit({ damage = 1, kind = DAMAGE_KIND.HIT, label, x, y } = {}) {
    const style = DAMAGE_STYLE[kind] || DAMAGE_STYLE.hit;
    const ix = x === undefined ? STAGE.enemyX + (Math.random() * 10 - 5) : x;
    const iy = y === undefined ? STAGE.ground - 30 : y;

    // HEAL, RESIST and MISS are readouts only. Healing on this stage belongs to
    // the player, whose stamina lives on the top bar, not to the enemy's health.
    if (kind !== DAMAGE_KIND.RESIST && kind !== DAMAGE_KIND.MISS
        && kind !== DAMAGE_KIND.HEAL) {
      this.flash = Math.max(this.flash, kind === DAMAGE_KIND.CRIT ? 1 : 0.75);
      this.knock = Math.max(this.knock, this._amp(kind === DAMAGE_KIND.CRIT ? 9 : 5));
      this.setEnemyHp(this.hp - damage);
    }
    this.shake(style.shake);
    this.damageNumber(label !== undefined ? label : damage, { kind, x: ix, y: iy - 12 });
    this.burst({
      x: ix, y: iy,
      colour: style.colour,
      count: kind === DAMAGE_KIND.CRIT ? 22 : 12,
      power: kind === DAMAGE_KIND.CRIT ? 70 : 44,
    });
    if (kind === DAMAGE_KIND.CRIT) {
      this.effects.push(this._ring(ix, iy, style.colour, 34, 0.45));
    }
    this._sfx(kind === DAMAGE_KIND.CRIT ? 'crit' : kind === DAMAGE_KIND.RESIST
      ? 'tick' : 'hit');
    return this;
  }

  /* The wind-up before trials resolve. Short on purpose: the player already
   * pressed the button, the feedback should start almost immediately. */
  cast() {
    this.heroPose = 1;
    this.heroLunge = this._amp(6);
    this.effects.push(this._sweep('#a89aff', 0.32));
    this._sfx('spell');
    return this._wait(this._t(0.3));
  }

  /* Resolve a list of trials one at a time so each one is a separate event the
   * player can see. Accepts the feedback trial shape from the server:
   *   { name, passed, hidden, crit }
   * and returns a promise that settles when the last one has landed. */
  async resolveTrials(trials, { interval = 0.09, damagePerTrial } = {}) {
    const list = Array.isArray(trials) ? trials : [];
    if (!list.length) return this;
    const step = this._t(interval);
    const dmg = damagePerTrial !== undefined
      ? damagePerTrial
      : Math.max(1, this.hpMax / Math.max(1, list.length));

    for (const trial of list) {
      if (!this.el) break;                       // torn down mid-sequence
      if (trial && trial.passed === false) {
        this.hit({ kind: DAMAGE_KIND.RESIST, label: 'RESIST', damage: 0 });
      } else if (trial && trial.crit) {
        this.hit({ kind: DAMAGE_KIND.CRIT, damage: dmg * 3 });
      } else {
        this.hit({ kind: DAMAGE_KIND.HIT, damage: dmg });
      }
      await this._wait(step);
    }
    return this;
  }

  /* ---------------- spells ---------------- */

  /* One distinct look per hint spell. The animation shows that a spell was cast
   * and what kind it was; it never renders the hint body, which belongs in the
   * spells panel where the rank cost is stated next to it. */
  castSpell(spell) {
    const name = String(spell || '').toUpperCase();
    this._sfx('spell');

    // The authored animators: each spell is a multi-stage effect whose shape
    // says what the spell DOES, which is most of how a player learns what it is
    // for. createEffect never returns null — an unknown id degrades to a plain
    // hit flagged .fallback rather than throwing mid-fight.
    const effect = spellfx.createEffect(name, {
      x: STAGE.enemyX,
      y: STAGE.ground - 30,
      from: { x: STAGE.heroX, y: STAGE.ground - 24 },
      to: { x: STAGE.enemyX, y: STAGE.ground - 30 },
      reducedMotion: this.reducedMotion,
      seed: hash(name),
      onImpact: () => {
        this.shake(name === 'PHOENIX' ? 8 : 4);
        this.flash = Math.max(this.flash, name === 'PHOENIX' ? 0.7 : 0.35);
      },
    });
    this.effects.push(spellfx.toFxEffect(effect));

    const dur = spellfx.effectDuration(name, { reducedMotion: this.reducedMotion });
    return this._wait(this._t(dur, { keep: true }));
  }

  /* ---------------- outcomes ---------------- */

  /* The close of a won fight, in the order the player earned it: the enemy goes,
   * the rank lands, the XP counts, the loot drops. */
  async victory({ rank = 'B', xp = 0, xpFrom, xpTo, loot, levelUp = false } = {}) {
    const colour = RANK_COLOUR[rank] || '#ffe8a0';
    this._sfx(rank === 'S' ? 'victory' : 'crit');

    this.setEnemyHp(0);
    await this.dissolve();
    if (!this.el) return this;

    this.banner = {
      text: rank === 'LEARNING_CLEAR' ? 'LEARNING CLEAR' : rank,
      sub: rank === 'LEARNING_CLEAR' ? 'the pattern is scheduled to return'
        : 'RANK',
      colour, t: 0, dur: this.reducedMotion ? 1.2 : 1.6, slam: true,
    };
    this.shake(rank === 'S' ? 7 : 4);
    this.burst({
      x: STAGE.w / 2, y: STAGE.h / 2, colour, count: 26, power: 90,
      gravity: 40, life: 0.8,
    });
    await this._wait(this._t(0.45, { keep: true }));
    if (!this.el) return this;

    if (xp > 0) {
      this.xpTarget = xp;
      this.xpShown = 0;
      if (xpFrom !== undefined && xpTo !== undefined) {
        this.xpBar = { from: clamp(xpFrom, 0, 1), to: clamp(xpTo, 0, 1), t: 0 };
      }
      await this._wait(this._t(0.9, { keep: true }));
    }
    if (!this.el) return this;

    if (loot) {
      this._sfx('unlock');
      this.chips.push({
        text: String(loot.name || loot).toUpperCase(),
        colour: loot.rarity_colour || '#e8c37d',
        x: STAGE.enemyX, y: STAGE.ground - 34,
        tx: STAGE.w / 2, ty: STAGE.ground - 18,
        t: 0, dur: this.reducedMotion ? 1.4 : 2.2,
      });
      this.burst({
        x: STAGE.enemyX, y: STAGE.ground - 30,
        colour: loot.rarity_colour || '#e8c37d', count: 18, power: 55, life: 0.7,
      });
      await this._wait(this._t(0.4, { keep: true }));
    }
    if (levelUp && this.el) {
      this._sfx('levelup');
      this.banner = {
        text: 'LEVEL UP', sub: '', colour: '#ffe8a0', t: 0,
        dur: this.reducedMotion ? 1.0 : 1.4, slam: true,
      };
      this.burst({
        x: STAGE.heroX, y: STAGE.ground - 20, colour: '#ffe8a0',
        count: 24, power: 70, gravity: -30, life: 1.0,
      });
      await this._wait(this._t(0.5, { keep: true }));
    }
    return this;
  }

  /* A failed cast. The enemy does not gloat, nothing goes red, and the player
   * character stays standing — the game's rule is that trying is never punished,
   * and the feedback layer has to hold that line too. */
  async defeat({ message, passed, total } = {}) {
    this._sfx('fail');
    this.heroPose = 2;
    this.knock = this._amp(-4);            // the hero rocks back, not the enemy
    this.shake(2);
    this.tintColour = '#7ec8ff';
    this.tint = this.reducedMotion ? 0.12 : 0.22;
    this.effects.push(this._guard('#7ec8ff', 0.7));

    if (passed !== undefined && total) {
      this.damageNumber(`${passed}/${total}`, {
        kind: DAMAGE_KIND.MISS, x: STAGE.enemyX, y: STAGE.ground - 58,
      });
    }
    this.banner = {
      text: 'STILL STANDING',
      sub: message || 'the trials named the gap — read them and recast',
      colour: '#7ec8ff',
      t: 0, dur: this.reducedMotion ? 1.3 : 1.9, slam: false,
    };
    await this._wait(this._t(0.7, { keep: true }));
    this.tint = 0;
    return this;
  }

  /* Dissolve the enemy into its own pixels. Sampling the sprite means the
   * particles are the creature rather than a generic puff. */
  dissolve() {
    const img = this._sprite(0);
    if (img && !this.reducedMotion) {
      const scale = this.scene && this.scene.boss ? 2 : 3;
      const w = img.width * scale, h = img.height * scale;
      const x0 = STAGE.enemyX - w / 2;
      const y0 = STAGE.ground - h;
      try {
        const probe = offscreen(img.width, img.height);
        probe.ctx.drawImage(img, 0, 0);
        const data = probe.ctx.getImageData(0, 0, img.width, img.height).data;
        for (let y = 0; y < img.height; y += 1) {
          for (let x = 0; x < img.width; x += 1) {
            const i = (y * img.width + x) * 4;
            if (data[i + 3] < 40) continue;
            if (Math.random() < 0.45) continue;      // thin it out; 256 is plenty
            this.particles.push({
              x: x0 + x * scale, y: y0 + y * scale,
              vx: (Math.random() - 0.3) * 30,
              vy: -20 - Math.random() * 50,
              g: 30, size: scale,
              colour: `rgb(${data[i]},${data[i + 1]},${data[i + 2]})`,
              t: 0, life: 0.5 + Math.random() * 0.6,
            });
          }
        }
      } catch (e) {
        // getImageData can fail in exotic contexts; the fade below still reads.
      }
    }
    this.dissolving = 1;
    return this._wait(this._t(0.55));
  }

  /* ---------------- boss intro ---------------- */

  /* Name card, taunt crawl, then the phase bar filling pip by pip. The bar fill
   * is the moment the player learns a boss has six phases rather than one. */
  async bossIntro({ name = 'THE NULL KING', taunt = '', phases = 0 } = {}) {
    this.tintColour = '#000000';
    this.tint = 0.55;
    this.pips = phases || this.hpMax;
    this.pipsLit = 0;
    this._sfx('shrine');

    this.nameCard = {
      text: String(name).toUpperCase(), t: 0,
      dur: this.reducedMotion ? 0.2 : 0.55,
    };
    await this._wait(this._t(0.6, { keep: true }));
    if (!this.el) return this;

    if (taunt) {
      this.crawl = {
        text: String(taunt), shown: 0, t: 0,
        rate: this.reducedMotion ? 400 : 34,   // glyphs per second
      };
      const readSeconds = this.reducedMotion
        ? 1.2
        : Math.min(4.5, 0.9 + taunt.length / 34);
      await this._wait(this._t(readSeconds, { keep: true }));
    }
    if (!this.el) return this;

    for (let i = 1; i <= this.pips; i++) {
      this.pipsLit = i;
      this._sfx('tick');
      this.burst({
        x: this._pipX(i - 1), y: STAGE.ground - 70,
        colour: '#ff6a7a', count: 5, power: 26, life: 0.3,
      });
      await this._wait(this._t(0.11, { keep: true }));
    }
    this.hp = this.hpMax;
    this.hpShown = this.hpMax;
    await this._wait(this._t(0.3, { keep: true }));
    this.tint = 0;
    this.nameCard = null;
    this.crawl = null;
    return this;
  }

  /* ---------------- internals: timing ---------------- */

  /* Durations. Reduced motion collapses flourishes but keeps anything the
   * player has to read at full length — cutting reading time is not an
   * accessibility win. */
  _t(sec, { keep = false } = {}) {
    if (!this.reducedMotion) return sec;
    return keep ? sec * 0.8 : Math.min(sec, 0.12);
  }

  _amp(px) { return this.reducedMotion ? 0 : px; }

  /* Waits on the render clock, not on wall time, so a stopped stage does not
   * leave callers hanging on a timer that will never be serviced. */
  _wait(sec) {
    if (!this.el) return Promise.resolve(this);
    return new Promise((resolve) => {
      const entry = { at: this.clock + Math.max(0, sec), fn: () => resolve(this) };
      this.timers.push(entry);
      this.pending.add(entry);
      // A stopped stage still has to settle its promises, or a caller awaiting
      // a sequence would stall for the rest of the session.
      if (!this.running) this._settleLater(entry, sec);
    });
  }

  /* Wall-clock backstop for one queued wait. Idempotent against the render
   * clock: the first of the two to run removes the entry from `pending`, and
   * the loser finds nothing to do. */
  _settleLater(entry, sec) {
    setTimeout(() => {
      if (!this.pending.has(entry)) return;
      this.pending.delete(entry);
      const i = this.timers.indexOf(entry);
      if (i >= 0) this.timers.splice(i, 1);
      entry.fn();
    }, Math.max(0, sec) * 1000);
  }

  _flushPending() {
    for (const entry of Array.from(this.pending)) {
      this.pending.delete(entry);
      try { entry.fn(); } catch (e) { /* a resolved promise cannot fail here */ }
    }
  }

  _runTimers() {
    if (!this.timers.length) return;
    const due = [];
    for (let i = this.timers.length - 1; i >= 0; i--) {
      if (this.timers[i].at <= this.clock) due.push(this.timers.splice(i, 1)[0]);
    }
    for (const entry of due.reverse()) {
      this.pending.delete(entry);
      entry.fn();
    }
  }

  _sfx(kind) {
    if (this.audio && typeof this.audio.sfx === 'function') {
      try { this.audio.sfx(kind); } catch (e) { /* audio is never load-bearing */ }
    }
  }

  /* ---------------- internals: sprites ---------------- */

  _sprite(frame) {
    if (!this.scene) return null;
    const e = this.scene.enemy;
    const key = `${e.boss ? 'boss' : 'mob'}:${e.sprite}:${e.colour || ''}:${this.scene.pattern}:${frame}`;
    if (this.sprites.has(key)) return this.sprites.get(key);
    let img;
    try {
      img = e.boss
        ? bosses.bossSprite(e.sprite, e.colour || undefined, frame)
        : sprites.enemySprite(e.sprite, this.scene.pattern, frame, e.colour || undefined);
    } catch (err) {
      img = null;
    }
    this.sprites.set(key, img);
    return img;
  }

  /* Flat-colour silhouette of a sprite. This is the hit flash. Keyed on the
   * source canvas in a WeakMap, so it dies with the sprite it shadows and a
   * long session cannot accumulate one flash canvas per frame. */
  _silhouetteOf(img, colour) {
    if (!img) return null;
    let byColour = this.flashCache.get(img);
    if (!byColour) { byColour = new Map(); this.flashCache.set(img, byColour); }
    if (byColour.has(colour)) return byColour.get(colour);
    const { canvas, ctx } = offscreen(img.width, img.height);
    ctx.drawImage(img, 0, 0);
    ctx.globalCompositeOperation = 'source-atop';
    ctx.fillStyle = colour;
    ctx.fillRect(0, 0, img.width, img.height);
    byColour.set(colour, canvas);
    return canvas;
  }

  _pipX(i) {
    const n = Math.max(1, this.pips);
    const w = 96, x0 = STAGE.enemyX - w / 2;
    return x0 + (w / n) * (i + 0.5);
  }

  /* ---------------- internals: effect constructors ----------------
   * Each returns a plain object with t/dur and a draw(ctx, k) where k is 0..1.
   * Keeping them data rather than classes keeps the update loop a single pass. */

  _ring(x, y, colour, radius, dur) {
    return { t: 0, dur, draw: (ctx, k) => {
      const r = radius * easeOut(k);
      ctx.strokeStyle = withAlpha(colour, (1 - k) * 0.9);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.5, r), 0, Math.PI * 2);
      ctx.stroke();
    } };
  }

  _sweep(colour, dur) {
    return { t: 0, dur, draw: (ctx, k) => {
      const x = lerp(STAGE.heroX, STAGE.enemyX, easeOut(k));
      ctx.fillStyle = withAlpha(colour, (1 - k) * 0.7);
      ctx.fillRect(x - 2, STAGE.ground - 44, 3, 40);
      ctx.fillStyle = withAlpha(colour, (1 - k) * 0.25);
      ctx.fillRect(STAGE.heroX, STAGE.ground - 34, x - STAGE.heroX, 2);
    } };
  }

  _eye(colour, dur) {
    const cx = STAGE.enemyX, cy = STAGE.ground - 56;
    return { t: 0, dur, draw: (ctx, k) => {
      const open = Math.sin(Math.PI * clamp(k * 1.15, 0, 1));
      const w = 34, h = 18 * open;
      ctx.strokeStyle = withAlpha(colour, 0.9);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - w / 2, cy);
      ctx.quadraticCurveTo(cx, cy - h, cx + w / 2, cy);
      ctx.quadraticCurveTo(cx, cy + h, cx - w / 2, cy);
      ctx.stroke();
      ctx.fillStyle = withAlpha(colour, 0.85 * open);
      ctx.fillRect(cx - 3, cy - 3, 6, 6);
      ctx.fillStyle = withAlpha('#0b0a12', open);
      ctx.fillRect(cx - 1, cy - 2, 2, 4);
    } };
  }

  _path(colour, dur) {
    const pips = 9;
    return { t: 0, dur, draw: (ctx, k) => {
      const shown = Math.floor(pips * easeOut(k)) + 1;
      for (let i = 0; i < Math.min(pips, shown); i++) {
        const p = i / (pips - 1);
        const x = lerp(STAGE.heroX + 8, STAGE.enemyX - 10, p);
        const y = STAGE.ground - 14 - Math.sin(p * Math.PI) * 26;
        const age = clamp((shown - i) / 4, 0, 1);
        ctx.fillStyle = withAlpha(colour, 0.35 + 0.55 * age);
        ctx.fillRect(Math.round(x) - 1, Math.round(y) - 1, 3, 3);
      }
    } };
  }

  _lens(colour, dur) {
    return { t: 0, dur, draw: (ctx, k) => {
      const r = lerp(6, 54, easeOut(clamp(k * 1.4, 0, 1)));
      const a = (1 - k) * 0.5;
      ctx.save();
      ctx.beginPath();
      ctx.arc(STAGE.enemyX, STAGE.ground - 30, r, 0, Math.PI * 2);
      ctx.clip();
      ctx.fillStyle = withAlpha(colour, a * 0.6);
      ctx.fillRect(0, 0, STAGE.w, STAGE.h);
      for (let y = 0; y < STAGE.h; y += 3) {
        ctx.fillStyle = withAlpha('#0b0a12', a * 0.5);
        ctx.fillRect(0, y, STAGE.w, 1);
      }
      ctx.restore();
      ctx.strokeStyle = withAlpha(colour, 1 - k);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(STAGE.enemyX, STAGE.ground - 30, r, 0, Math.PI * 2);
      ctx.stroke();
    } };
  }

  _scan(colour, dur) {
    const glyphs = '01{}[]()<>=+-*/:.#';
    const cols = [];
    for (let i = 0; i < 22; i++) {
      cols.push({
        x: 4 + i * 8 + Math.random() * 3,
        speed: 40 + Math.random() * 70,
        offset: Math.random() * STAGE.h,
        ch: glyphs[(Math.random() * glyphs.length) | 0],
      });
    }
    return { t: 0, dur, draw: (ctx, k, t) => {
      const a = Math.sin(Math.PI * clamp(k * 1.1, 0, 1));
      ctx.font = `6px 'Press Start 2P', monospace`;
      for (const c of cols) {
        const y = ((c.offset + t * c.speed) % (STAGE.h + 12)) - 6;
        ctx.fillStyle = withAlpha(colour, a * 0.75);
        ctx.fillText(c.ch, c.x, y);
        ctx.fillStyle = withAlpha(colour, a * 0.3);
        ctx.fillText(c.ch, c.x, y - 8);
      }
      const line = lerp(-4, STAGE.h + 4, easeOut(k));
      ctx.fillStyle = withAlpha('#f4f4ff', a);
      ctx.fillRect(0, Math.round(line), STAGE.w, 1);
      ctx.fillStyle = withAlpha(colour, a * 0.35);
      ctx.fillRect(0, Math.round(line) - 5, STAGE.w, 5);
    } };
  }

  _assemble(colour, dur) {
    const blocks = [];
    for (let i = 0; i < 10; i++) {
      blocks.push({
        w: 6 + Math.floor(Math.random() * 16),
        tx: STAGE.enemyX - 30 + Math.random() * 60,
        ty: STAGE.ground - 60 + Math.random() * 52,
        fx: STAGE.enemyX - 90 + Math.random() * 180,
        fy: STAGE.ground - 130 + Math.random() * 160,
      });
    }
    return { t: 0, dur, draw: (ctx, k) => {
      const e = easeOut(clamp(k * 1.3, 0, 1));
      for (const b of blocks) {
        const x = lerp(b.fx, b.tx, e), y = lerp(b.fy, b.ty, e);
        ctx.fillStyle = withAlpha(colour, 0.25 + 0.6 * e * (1 - k * 0.6));
        ctx.fillRect(Math.round(x), Math.round(y), b.w, 3);
        ctx.fillStyle = withAlpha('#0b0a12', 0.5 * e);
        ctx.fillRect(Math.round(x), Math.round(y) + 3, b.w, 1);
      }
    } };
  }

  _phoenix(colour, dur) {
    return { t: 0, dur, draw: (ctx, k) => {
      const rise = lerp(0, 64, easeOut(k));
      const a = Math.sin(Math.PI * clamp(k * 1.05, 0, 1));
      const cx = STAGE.heroX, base = STAGE.ground - 4;
      for (let i = 0; i < 26; i++) {
        const p = i / 25;
        const y = base - p * rise;
        const w = Math.max(1, Math.round((1 - p) * 12 * a));
        ctx.fillStyle = withAlpha(i % 3 === 0 ? '#ffe8a0' : colour, a * (1 - p * 0.7));
        ctx.fillRect(Math.round(cx - w / 2 + Math.sin(p * 7 + k * 5) * 3), Math.round(y), w, 2);
      }
      // Wings: two arcs opening outward at the crest of the rise.
      const spread = easeOut(clamp((k - 0.35) / 0.65, 0, 1)) * 30;
      ctx.strokeStyle = withAlpha('#ffe8a0', a * 0.8);
      ctx.lineWidth = 1;
      for (const dir of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(cx, base - rise * 0.55);
        ctx.quadraticCurveTo(cx + dir * spread, base - rise * 0.95,
                             cx + dir * spread * 1.15, base - rise * 0.35);
        ctx.stroke();
      }
    } };
  }

  _guard(colour, dur) {
    // A shield flare on the player's side: the hit is absorbed, not taken.
    return { t: 0, dur, draw: (ctx, k) => {
      const a = (1 - k) * 0.8;
      const r = lerp(10, 26, easeOut(k));
      ctx.strokeStyle = withAlpha(colour, a);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(STAGE.heroX, STAGE.ground - 22, r, -Math.PI * 0.75, Math.PI * 0.75);
      ctx.stroke();
    } };
  }

  /* ---------------- internals: loop ---------------- */

  _resize() {
    if (!this.canvas || !this.host) return;
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    const rect = this.host.getBoundingClientRect();
    const cw = Math.max(64, Math.round(rect.width));
    const ch = Math.max(48, Math.round(rect.height));
    this.canvas.style.width = cw + 'px';
    this.canvas.style.height = ch + 'px';
    this.canvas.width = Math.round(cw * dpr);
    this.canvas.height = Math.round(ch * dpr);
    // Whole-number scale only. A fractional scale is what makes pixel art soft.
    this.px = Math.max(1, Math.floor(Math.min(
      this.canvas.width / STAGE.w, this.canvas.height / STAGE.h)));
    this.ox = Math.round((this.canvas.width - STAGE.w * this.px) / 2);
    this.oy = Math.round((this.canvas.height - STAGE.h * this.px) / 2);
    this.ctx.imageSmoothingEnabled = false;
  }

  _frame(now) {
    if (!this.running) return;
    this.raf = requestAnimationFrame(this._frame);
    if (!this.last) this.last = now;
    const dt = Math.min(0.05, (now - this.last) / 1000);
    this.last = now;
    this.clock += dt;
    this._runTimers();
    this._update(dt);
    this._render();
  }

  _update(dt) {
    // Advance the boss's own frame machine. Its telegraph length is per-creature,
    // which is what makes a wind-up readable as a warning rather than as noise.
    if (this.scene && this.scene.boss) {
      this.bossStateT += dt;
      const step = bosses.bossFrameAt(this.scene.enemy.sprite, this.bossState,
                                      this.bossStateT * 1000);
      this.bossFrame = step.index;
      if (step.done) { this.bossState = step.next; this.bossStateT = 0; }
    }
    if (this.cam) this.cam.update(dt);
    // decays
    this.shakeMag *= Math.pow(0.0009, dt);
    if (this.shakeMag < 0.05) this.shakeMag = 0;
    this.knock *= Math.pow(0.0015, dt);
    if (Math.abs(this.knock) < 0.05) this.knock = 0;
    this.flash = Math.max(0, this.flash - dt * 5.5);
    this.comboGlow = Math.max(0, this.comboGlow - dt * 1.4);
    this.heroLunge *= Math.pow(0.004, dt);
    if (this.heroLunge < 0.1) { this.heroLunge = 0; this.heroPose = 0; }
    if (this.dissolving) this.enemyAlpha = Math.max(0, this.enemyAlpha - dt * 3);

    // hp bar tween
    this.hpShown = this.reducedMotion ? this.hp
      : lerp(this.hpShown, this.hp, 1 - Math.pow(0.0005, dt));
    if (Math.abs(this.hpShown - this.hp) < 0.01) this.hpShown = this.hp;

    // xp counter
    if (this.xpTarget > 0 && this.xpShown < this.xpTarget) {
      const speed = Math.max(40, this.xpTarget / (this.reducedMotion ? 0.2 : 0.9));
      this.xpShown = Math.min(this.xpTarget, this.xpShown + speed * dt);
    }
    if (this.xpBar) this.xpBar.t = Math.min(1, this.xpBar.t + dt / 0.9);

    if (this.scene && !this.reducedMotion) this.scene.drift += dt;

    if (this.weather && this.weatherStyle && !this.reducedMotion) {
      pixel.stepParticles(this.weather, this.weatherStyle, STAGE.w, STAGE.ground, dt);
    }

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.t += dt;
      if (p.t >= p.life) { this.particles.splice(i, 1); continue; }
      p.vy += p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    for (let i = this.numbers.length - 1; i >= 0; i--) {
      const n = this.numbers[i];
      n.t += dt;
      if (n.t >= n.dur) this.numbers.splice(i, 1);
    }
    for (let i = this.effects.length - 1; i >= 0; i--) {
      const e = this.effects[i];
      e.t += dt;
      if (e.t >= e.dur) this.effects.splice(i, 1);
    }
    for (let i = this.chips.length - 1; i >= 0; i--) {
      const c = this.chips[i];
      c.t += dt;
      if (c.t >= c.dur) this.chips.splice(i, 1);
    }
    if (this.banner) {
      this.banner.t += dt;
      if (this.banner.t >= this.banner.dur) this.banner = null;
    }
    if (this.nameCard) this.nameCard.t += dt;
    if (this.crawl) {
      this.crawl.t += dt;
      this.crawl.shown = Math.min(this.crawl.text.length,
        Math.floor(this.crawl.t * this.crawl.rate));
    }
  }

  _render() {
    const ctx = this.ctx;
    if (!ctx) return;
    const sx = this.shakeMag ? Math.round((Math.random() - 0.5) * this.shakeMag) : 0;
    const sy = this.shakeMag ? Math.round((Math.random() - 0.5) * this.shakeMag) : 0;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = this.scene ? this.scene.pal.dark : '#0b0a12';
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.setTransform(this.px, 0, 0, this.px,
      this.ox + sx * this.px, this.oy + sy * this.px);
    ctx.imageSmoothingEnabled = false;

    if (!this.scene) return;
    this._drawBackdrop(ctx);
    this._drawWeather(ctx);
    this._drawCombo(ctx);
    this._drawHero(ctx);
    this._drawEnemy(ctx);
    this._drawEffects(ctx);
    this._drawParticles(ctx);
    if (this.stage3d) stagelayer.drawForeground(ctx, this.stage3d, this.clock, this.cam);
    this._drawHud(ctx);
    this._drawNumbers(ctx);
    this._drawChips(ctx);
    this._drawTint(ctx);
    this._drawBanner(ctx);
    this._drawBossCard(ctx);
  }

  _drawBackdrop(ctx) {
    // The authored stage layer, when we have one: three parallax depths, a
    // horizon treatment, per-biome weather and real lighting. The original
    // two-speed backdrop stays as the fallback.
    if (this.stage3d) {
      stagelayer.drawScene(ctx, this.stage3d, this.clock, this.cam);
      return;
    }
    const b = this.scene.backdrop;
    const drift = this.scene.drift;
    ctx.drawImage(b.sky, 0, 0);
    // Two parallax speeds against a static camera read as wind, which is enough
    // to stop the backdrop looking like a still image.
    const farX = -((drift * 3) % STAGE.w);
    ctx.drawImage(b.far, Math.round(farX), STAGE.ground - b.far.height);
    const midX = -((drift * 8) % STAGE.w);
    ctx.drawImage(b.mid, Math.round(midX), STAGE.ground - b.mid.height + 2);
    ctx.drawImage(b.ground, 0, STAGE.ground);
  }

  _drawWeather(ctx) {
    if (!this.weather || !this.weatherStyle) return;
    pixel.drawParticles(ctx, this.weather, this.weatherStyle, 0.45);
  }

  _shadow(ctx, x, w, alpha = 0.35) {
    ctx.save();
    ctx.fillStyle = `rgba(0,0,0,${alpha})`;
    ctx.beginPath();
    ctx.ellipse(x, STAGE.ground + 1, w / 2, Math.max(1.5, w / 7), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  _drawHero(ctx) {
    const x = STAGE.heroX + this.heroLunge;
    if (!this.hero || !this.hero.side) {
      this._shadow(ctx, x, 18, 0.3);
      return;
    }
    // sprites.heroSprites returns a true four-frame cycle [0,1,2,3], so index 1 is the forward
    // pass and index 3 is the opposite one. Indices 1 and 3 are the passing frames.
    const frames = this.hero.side;
    const img = frames[this.heroPose === 1 ? 1 : this.heroPose === 2 ? 3 : 0] || frames[0];
    const S = 3;
    const w = img.width * S, h = img.height * S;
    // A one-source-pixel breathe. Whole pixels only, so the sprite never blurs.
    const breathe = this.reducedMotion ? 0
      : (Math.sin(this.clock * 2.1) > 0.6 ? 1 : 0);
    this._shadow(ctx, x, w * 0.7, 0.32);
    ctx.drawImage(img, Math.round(x - w / 2), Math.round(STAGE.ground - h + breathe),
      w, h - breathe * S);
  }

  _drawEnemy(ctx) {
    if (this.enemyAlpha <= 0) return;
    const e = this.scene.enemy;
    if (this.scene.boss) {
      // The boss set carries its own five-frame state machine, ground shadow,
      // ambient bob and hit flash, so it is one call rather than a manual blit.
      bosses.drawBoss(ctx, e.sprite, STAGE.enemyX + this.knock, STAGE.ground, {
        frame: this.bossFrame,
        time: this.clock * 1000,
        scale: bosses.BOSS_STAGE_SCALE,
        flash: this.flash,
        alpha: this.enemyAlpha,
        colour: e.colour,
        reducedMotion: this.reducedMotion,
      });
      return;
    }
    const frame = this.reducedMotion ? 0 : (Math.floor(this.clock * 2) % 2);
    const img = this._sprite(frame);
    if (!img) return;
    const boss = false;
    const S = boss ? 2 : 3;
    const bob = this.reducedMotion ? 0 : Math.round(Math.sin(this.clock * 2.4) * 1) * S;
    const squash = this.reducedMotion ? 0 : Math.round(Math.cos(this.clock * 2.4) * 1);
    const w = img.width * S, h = img.height * S;
    const x = Math.round(STAGE.enemyX + this.knock - w / 2);
    const y = Math.round(STAGE.ground - h + bob - squash * S);

    this._shadow(ctx, STAGE.enemyX + this.knock * 0.5, w * 0.66,
      0.34 * this.enemyAlpha);

    ctx.save();
    ctx.globalAlpha = this.enemyAlpha;
    ctx.drawImage(img, x, y, w, h + squash * S);
    if (this.flash > 0.01) {
      const sil = this._silhouetteOf(img, '#ffffff');
      if (sil) {
        ctx.globalAlpha = this.enemyAlpha * Math.min(1, this.flash);
        ctx.drawImage(sil, x, y, w, h + squash * S);
      }
    }
    ctx.restore();
  }

  _drawEffects(ctx) {
    for (const e of this.effects) {
      const k = clamp(e.t / e.dur, 0, 1);
      ctx.save();
      e.draw(ctx, k, e.t);
      ctx.restore();
    }
  }

  _drawParticles(ctx) {
    for (const p of this.particles) {
      const a = 1 - p.t / p.life;
      ctx.globalAlpha = a * a;
      ctx.fillStyle = p.colour;
      ctx.fillRect(Math.round(p.x), Math.round(p.y), p.size, p.size);
    }
    ctx.globalAlpha = 1;
  }

  _drawCombo(ctx) {
    if (this.comboMult <= 1.001) return;
    const heat = clamp((this.comboMult - 1) / 0.5, 0, 1);
    const colour = heat > 0.66 ? '#ff9d4a' : heat > 0.33 ? '#e8c37d' : '#8fd07a';
    // An ember column behind the player that grows with the multiplier. The
    // number is on the top bar already; this is the felt version of it.
    const n = Math.round(4 + heat * 10);
    for (let i = 0; i < n; i++) {
      const p = i / n;
      const t = this.reducedMotion ? 0 : this.clock * (1.4 + heat);
      const y = STAGE.ground - 6 - ((p * 46 + t * 18) % 46);
      const wob = this.reducedMotion ? 0 : Math.sin(p * 9 + t * 2) * 4;
      ctx.globalAlpha = (1 - (STAGE.ground - 6 - y) / 46) * (0.3 + heat * 0.5);
      ctx.fillStyle = colour;
      ctx.fillRect(Math.round(STAGE.heroX + wob - 1), Math.round(y), 2, 2);
    }
    ctx.globalAlpha = 1;
    this._text(ctx, `x${this.comboMult.toFixed(2)}`, 5, 12, {
      size: 7, colour, align: 'left',
    });
    if (this.combo > 1) {
      this._text(ctx, `${this.combo} CLEARS`, 5, 21,
        { size: 6, colour: '#9b96b8', align: 'left' });
    }
    if (this.comboGlow > 0) {
      ctx.globalAlpha = this.comboGlow * 0.4;
      ctx.fillStyle = colour;
      ctx.fillRect(0, 0, STAGE.w, STAGE.h);
      ctx.globalAlpha = 1;
    }
  }

  _drawHud(ctx) {
    // Enemy name and health, on the stage rather than only beneath it, so the
    // hit and the bar move in the same field of view. Drawing the name here is
    // what lets the stage cover its host outright instead of leaving a strip.
    const w = 96, x0 = Math.round(STAGE.enemyX - w / 2), y0 = STAGE.ground - 70;
    if (this.enemyAlpha > 0.05 && !this.nameCard) {
      const label = String(this.scene.enemy.name || '').toUpperCase();
      this._text(ctx, label, STAGE.enemyX, y0 - 5, {
        size: label.length > 14 ? 5 : 7,
        colour: this.scene.boss ? '#ff6a7a' : '#e8c37d',
        outline: '#0b0a12',
      });
    }
    ctx.fillStyle = '#0d0b16';
    ctx.fillRect(x0 - 1, y0 - 1, w + 2, 7);
    ctx.fillStyle = '#3a3360';
    ctx.fillRect(x0, y0, w, 5);
    if (this.pips) {
      for (let i = 0; i < this.pips; i++) {
        const pw = w / this.pips;
        ctx.fillStyle = i < this.pipsLit ? '#ff6a7a' : '#241f3a';
        ctx.fillRect(Math.round(x0 + i * pw) + 1, y0, Math.round(pw) - 2, 5);
      }
    } else {
      const k = clamp(this.hpShown / this.hpMax, 0, 1);
      ctx.fillStyle = k > 0.5 ? '#ff8a7a' : k > 0.2 ? '#ff9d4a' : '#c43f4f';
      ctx.fillRect(x0, y0, Math.round(w * k), 5);
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.fillRect(x0, y0, Math.round(w * k), 1);
    }

    if (this.xpTarget > 0) {
      this._text(ctx, `+${Math.round(this.xpShown)} XP`, STAGE.w / 2, STAGE.h - 16,
        { size: 8, colour: '#ffe8a0' });
    }
    if (this.xpBar) {
      const bw = 120, bx = Math.round((STAGE.w - bw) / 2), by = STAGE.h - 10;
      const k = lerp(this.xpBar.from, this.xpBar.to, easeOut(this.xpBar.t));
      ctx.fillStyle = '#0d0b16';
      ctx.fillRect(bx - 1, by - 1, bw + 2, 5);
      ctx.fillStyle = '#ffd97a';
      ctx.fillRect(bx, by, Math.round(bw * clamp(k, 0, 1)), 3);
    }
  }

  _drawNumbers(ctx) {
    for (const n of this.numbers) {
      const k = n.t / n.dur;
      const y = n.y - n.style.rise * (this.reducedMotion ? 0.25 : easeOut(k));
      const x = n.x + n.drift * k;
      // A crit punches in from larger than life; everything else holds its size.
      const scale = n.style.size >= 13 && !this.reducedMotion
        ? lerp(1.6, 1, easeOut(clamp(k * 4, 0, 1))) : 1;
      const alpha = k > 0.7 ? 1 - (k - 0.7) / 0.3 : 1;
      this._text(ctx, n.text, x, y, {
        size: n.style.size * scale,
        colour: withAlpha(n.style.colour, alpha),
        outline: withAlpha(n.style.outline, alpha),
      });
    }
  }

  _drawChips(ctx) {
    for (const c of this.chips) {
      const k = clamp(c.t / c.dur, 0, 1);
      const fly = easeOut(clamp(k * 2.2, 0, 1));
      const x = lerp(c.x, c.tx, fly);
      const y = lerp(c.y, c.ty, fly) - Math.sin(fly * Math.PI) * 14;
      const alpha = k > 0.75 ? 1 - (k - 0.75) / 0.25 : 1;
      const w = Math.max(34, c.text.length * 5 + 10);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = '#171426';
      ctx.fillRect(Math.round(x - w / 2), Math.round(y - 6), w, 12);
      ctx.strokeStyle = c.colour;
      ctx.lineWidth = 1;
      ctx.strokeRect(Math.round(x - w / 2) + 0.5, Math.round(y - 6) + 0.5, w - 1, 11);
      this._text(ctx, c.text, x, y + 2, { size: 5, colour: c.colour });
      ctx.globalAlpha = 1;
    }
  }

  _drawTint(ctx) {
    if (!this.tint || !this.tintColour) return;
    ctx.fillStyle = withAlpha(this.tintColour, this.tint);
    ctx.fillRect(0, 0, STAGE.w, STAGE.h);
  }

  _drawBanner(ctx) {
    const b = this.banner;
    if (!b) return;
    const k = clamp(b.t / b.dur, 0, 1);
    let scale = 1, alpha = 1;
    if (b.slam && !this.reducedMotion) {
      const inK = clamp(b.t / 0.22, 0, 1);
      scale = lerp(3.2, 1, overshoot(inK));
    }
    if (k > 0.75) alpha = 1 - (k - 0.75) / 0.25;
    if (this.reducedMotion) alpha *= clamp(b.t / 0.15, 0, 1);

    const cy = STAGE.h / 2 - 6;
    ctx.globalAlpha = alpha * 0.72;
    ctx.fillStyle = '#0b0a12';
    ctx.fillRect(0, Math.round(cy - 16), STAGE.w, 34);
    ctx.fillStyle = withAlpha(b.colour, 0.55);
    ctx.fillRect(0, Math.round(cy - 16), STAGE.w, 1);
    ctx.fillRect(0, Math.round(cy + 17), STAGE.w, 1);
    ctx.globalAlpha = alpha;
    if (b.sub === 'RANK') {
      this._text(ctx, 'RANK', STAGE.w / 2 - 34, cy + 2,
        { size: 7, colour: '#9b96b8' });
      this._text(ctx, b.text, STAGE.w / 2 + 6, cy + 6,
        { size: 20 * scale, colour: b.colour, outline: '#0b0a12' });
    } else {
      this._text(ctx, b.text, STAGE.w / 2, cy - 1,
        { size: (b.text.length > 12 ? 9 : 13) * scale, colour: b.colour,
          outline: '#0b0a12' });
      if (b.sub) {
        this._text(ctx, b.sub, STAGE.w / 2, cy + 12,
          { size: 5, colour: '#9b96b8' });
      }
    }
    ctx.globalAlpha = 1;
  }

  _drawBossCard(ctx) {
    if (this.nameCard) {
      const c = this.nameCard;
      const k = clamp(c.t / c.dur, 0, 1);
      const slideFrom = this.reducedMotion ? 0 : -STAGE.w;
      const x = lerp(slideFrom, 0, overshoot(k));
      ctx.save();
      ctx.translate(Math.round(x), 0);
      ctx.fillStyle = 'rgba(11,10,18,0.85)';
      ctx.fillRect(0, 24, STAGE.w, 22);
      ctx.fillStyle = '#d84a7a';
      ctx.fillRect(0, 24, STAGE.w, 1);
      ctx.fillRect(0, 45, STAGE.w, 1);
      this._text(ctx, c.text, STAGE.w / 2, 39,
        { size: c.text.length > 14 ? 8 : 11, colour: '#ffe8a0', outline: '#2a0a14' });
      ctx.restore();
    }
    if (this.crawl) {
      const shown = this.crawl.text.slice(0, this.crawl.shown);
      const lines = this._wrap(shown, 30);
      lines.forEach((line, i) => {
        this._text(ctx, line, STAGE.w / 2, 58 + i * 9,
          { size: 6, colour: '#e8e6f5', outline: '#0b0a12' });
      });
    }
  }

  /* ---------------- internals: text ---------------- */

  _text(ctx, str, x, y, { size = 8, colour = '#e8e6f5', outline, align = 'center' } = {}) {
    ctx.save();
    ctx.font = `${size}px 'Press Start 2P', 'Courier New', monospace`;
    ctx.textAlign = align;
    ctx.textBaseline = 'alphabetic';
    if (outline) {
      ctx.fillStyle = outline;
      // A hard one-pixel drop shade rather than a stroke, which is what keeps
      // text readable over both the sky and the ground band.
      ctx.fillText(str, x + 1, y + 1);
    }
    ctx.fillStyle = colour;
    ctx.fillText(str, x, y);
    ctx.restore();
  }

  _wrap(str, width) {
    const words = String(str).split(/\s+/);
    const lines = [];
    let line = '';
    for (const w of words) {
      if ((line + ' ' + w).trim().length > width) { lines.push(line.trim()); line = w; }
      else line = (line + ' ' + w).trim();
    }
    if (line) lines.push(line);
    return lines.slice(0, 4);
  }

  /* The stage styles itself so game.css never has to know it exists. */
  static _ensureStyle() {
    if (document.getElementById('fx-stage-style')) return;
    const s = document.createElement('style');
    s.id = 'fx-stage-style';
    s.textContent = `
.fx-stage { position: absolute; inset: 0; pointer-events: none; z-index: 2; }
.fx-canvas { display: block; width: 100%; height: 100%; image-rendering: pixelated; }
body.reduced-motion .fx-canvas { transition: none; }
`;
    document.head.appendChild(s);
  }
}

/* Convenience constructor for callers that would rather not use `new`. */
export function createBattleFX(host, opts = {}) {
  return new BattleFX(host, opts);
}

/* Maps a server feedback block to the trial shape resolveTrials expects.
 * Kept here so main.js does not grow a second copy of this reshaping. */
export function trialsFromFeedback(feedback, combat) {
  // The engine's battle feedback carries `lines`; older callers passed `trials`.
  // Accept either, because silently animating nothing is the worst failure mode
  // this function has.
  const trials = (feedback && (feedback.trials || feedback.lines)) || [];
  const critNames = new Set(
    ((combat && combat.crits) || []).map(c => String(c.trial)));
  return trials.map(t => ({
    name: t.name || t.id || '',
    // a `lines` entry reports status; a `trials` entry reports passed
    passed: t.status ? t.status === 'pass' : t.passed !== false,
    status: t.status || (t.passed === false ? 'fail' : 'pass'),
    hidden: !!t.hidden,
    crit: critNames.has(String(t.name || t.id || '')),
  }));
}

export const FX_VERSION = '1.0.0';
