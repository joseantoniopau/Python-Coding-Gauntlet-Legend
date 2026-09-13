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
import * as monsterart from './monsterart.js';
import * as lootart from './lootart.js';
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

/* ---------------- the wheel, as motion ----------------
 *
 * elements.py owns what an element DOES. This owns what one LOOKS like, and the
 * two are kept apart on purpose: the server sends an element id, a multiplier
 * and a matchup kind, and nothing below ever decides any of them.
 *
 * `colour` and `dark` are elements.Element's own two fields, copied rather than
 * fetched because the stage is drawn sixty times a second and an element's
 * palette is not something that changes mid-fight. If elements.py ever restyles
 * one, scripts/verify checks the ids still line up; the hexes are art.
 *
 * `motion` is the part that matters and the part no colour swap can substitute
 * for. Six elements that differed only in tint would be one element with a
 * paint tray, and a player would learn the wheel by reading the label instead
 * of by watching the screen. So each one moves in a way that means something:
 *
 *   FIRE       rises. It starts at the feet and goes up, and keeps going after.
 *   COLD       converges. Shards arrive from outside and lock in place.
 *   POISON     lingers. It seeps upward slowly and is still there afterwards.
 *   BRUTE      arrives. One vertical slam and a shock down the standing line.
 *   LIGHTNING  is already over. One jagged instant, from the top of the frame.
 *   VOID       implodes. Everything is drawn inward and then there is nothing.
 *
 * `weather` names the ambient particle style an area of this element wears, so
 * a cold region reads cold before anything has been cast in it.
 */
export const ELEMENT_FX = Object.freeze({
  FIRE:      { colour: '#e06a3c', dark: '#8f3a1e', motion: 'rise',
               weather: 'ember', sfx: 'crit' },
  COLD:      { colour: '#7ec8ff', dark: '#2f6d9e', motion: 'converge',
               weather: 'snow', sfx: 'tick' },
  POISON:    { colour: '#8fd07a', dark: '#3f7a3a', motion: 'seep',
               weather: 'motes', sfx: 'tick' },
  BRUTE:     { colour: '#bf8f4f', dark: '#6f4f28', motion: 'slam',
               weather: 'ash', sfx: 'hit' },
  LIGHTNING: { colour: '#f2dc6a', dark: '#9a8220', motion: 'strike',
               weather: 'rain', sfx: 'crit' },
  VOID:      { colour: '#6a4f8f', dark: '#2f2445', motion: 'implode',
               weather: 'ash', sfx: 'spell' },
  NEUTRAL:   { colour: '#9b96b8', dark: '#4a4450', motion: 'plain',
               weather: '', sfx: 'hit' },
});

/* elements.MATCHUP_MULT's floor and ceiling. Everything elemental on this stage
 * is a lerp between them, so an opposed hit is not "the big one" by a table
 * somebody has to keep in step — it is big because 1.5 is the top of the range
 * the server can send. */
const MULT_FLOOR = 0.65;
const MULT_CEIL = 1.50;

/* 0 at the most-shrugged-off hit in the game, 1 at the hardest counter. This is
 * the single number every elemental effect below scales off. */
function elementalK(multiplier) {
  const m = typeof multiplier === 'number' && isFinite(multiplier)
    ? multiplier : 1;
  return clamp((m - MULT_FLOOR) / (MULT_CEIL - MULT_FLOOR), 0, 1);
}

export function elementFx(id) {
  return ELEMENT_FX[String(id || '').toUpperCase()] || ELEMENT_FX.NEUTRAL;
}

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

/* THE BIOME NO LONGER DECIDES THE WEATHER.
 *
 * There used to be a table here mapping each biome to one particle style, on
 * forever: a mountain snowed in every fight, a mine threw embers in every
 * fight, and a grass region rained in every fight. It agreed with nothing —
 * the overworld had its own private table saying something different, and the
 * battle backdrop in battlescene.js had a third — so the three of them could
 * not have matched even by accident.
 *
 * What replaces it is one question asked of gauntlet/weather.py, through
 * battlescene.js's registry: what is the sky doing in this region, right now.
 * The answer names a pixel.PARTICLE_STYLE and how much of it, and the same
 * answer is what the overworld is drawing at that moment. */
const WEATHER_COUNT = 34;      // at density 1. A drizzle gets a fraction of it.

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
    this.gear = null;           // {weapon: itemDict} — the forged blade, if any
    this.holdUntil = 0;         // the impact freeze, in render-clock seconds

    this.numbers = [];
    this.particles = [];
    this.effects = [];
    this.weather = null;
    this.weatherStyle = null;
    /* The resolved sky for the encounter on the stage. Set in setScene, read by
     * setAffinity, and null until the first one. */
    this.sky = null;
    // The region's own element, and the faint wash that says so. Separate from
    // `tint`, which is a transient an outcome owns: the affinity is the room and
    // does not fade.
    this.affinity = '';
    this.hazard = '';
    this.affinityTint = 0;

    this.hp = 1; this.hpMax = 1; this.hpShown = 1;
    this.pips = 0; this.pipsLit = 0;
    this.combo = 0; this.comboMult = 1; this.comboGlow = 0;
    this.shakeMag = 0;
    this.stage3d = null;
    this.cam = null;
    this.bossFrame = 0;
    this.bossState = 'idle';
    this.bossStateT = 0;
    /* THE ART PHASE, and it is the fix for a bug rather than a feature.
     *
     * web/js/bosses.js has had a phase system since it was written: the plate
     * opens, the creature sheds a limb, a core lights. _drawEnemy never passed
     * one. Nothing in the tree ever passed one. So every boss in every fight
     * was drawn at stage 0 — the art existed, was measured, was verified, and
     * was never once on screen. Two numbers, carried from the server's phase
     * turn to the sprite builder, is the whole of it. */
    this.bossPhase = 0;          // art stage, 0..bosses.BOSS_PHASE_COUNT-1
    this.bossPhases = 0;         // how many phases this fight has
    this.phaseCard = null;       // the herald and the tell, mid-turn
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
    this.gear = null;
    this.holdUntil = 0;
    this.weather = null;
    this.affinity = '';
    this.hazard = '';
    this.affinityTint = 0;
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
  setScene({ region, enemy, pattern, heroPalette, heroLook, gear } = {}) {
    if (this.stage3d) { stagelayer.destroyScene(this.stage3d); this.stage3d = null; }
    /* `region` is documented above as a record and main.js passes a PALETTE
     * NAME — `payload.region.palette` — which is why `region.biome` has been
     * undefined at this line for the whole life of the file and every fight in
     * the game has been staged in the fallback biome. Both shapes are accepted
     * now and resolveSky() untangles them: a record wins, a palette name is
     * matched against the region the overworld last published, and only a total
     * failure to resolve anything falls through to the old defaults. */
    const palName = (typeof region === 'string' ? region
      : (region && region.palette)) || 'spring';
    const pal = pixel.PALETTES[palName] || pixel.PALETTES.spring;
    /* THE SKY. One lookup, used for the stage, for the 2D fallback backdrop and
     * for the particle layer below, so those three cannot disagree either. */
    const sky = stagelayer.resolveSky(region, palName);
    const biome = (region && region.biome) || sky.biome || 'grass';
    const seed = hash((region && region.id) || sky.region || palName);

    this.clearEffects();
    this.sprites.clear();

    this.scene = {
      pal, biome, seed,
      /* The region ID, kept because monsterart resolves a bestiary sprite key
       * against the region's OWN roster. Without it every region draws the
       * default roster's animals, which is the bug monsterart.js exists to
       * fix. `biome` above is not a substitute: two regions share a biome. */
      regionId: (region && region.id) || null,
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
        // Resolved once, above. The stage does not go and ask again, so the
        // backdrop and the particles in front of it are the same weather.
        weather: sky,
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
    /* A boss that walks in already cracked has thrown away the only moment
     * where cracking it means anything, so a fight opens at stage 0 unless the
     * payload says otherwise — which it does on a reload into a fight already
     * three phases deep. */
    this.bossPhases = Math.max(0, (enemy && enemy.phases) | 0);
    this.bossPhase = this.scene.boss
      ? bosses.bossPhase(enemy && (enemy.art_phase !== undefined
        ? { art_phase: enemy.art_phase }
        : { phase: enemy.phase, phases: enemy.phases }))
      : 0;
    this.phaseCard = null;
    if (this.scene.boss) this._warmPhase(this.bossPhase);

    /* The condition names the style and carries how much of it. A clear day is
     * a handful of motes in the air and nothing else — which is the state this
     * stage did not have until now, and the whole of the complaint. */
    this.sky = sky;
    this._setSkyParticles(sky);
    // Cleared rather than carried. A fight in the Coliseum straight after one in
    // the marsh must read as the Coliseum, and setAffinity is called after this
    // by whoever knows what region this is.
    this.affinity = '';
    this.hazard = '';
    this.affinityTint = 0;

    const tint = heroLook || pixel.PALETTES[heroPalette] || pal;
    // A forged blade is not a tint. `gear` carries the weapon as an item dict
    // with its forge block, and lootart.equippedHeroSprites returns exactly the
    // structure sprites.heroSprites returns, so the rung the player paid nine
    // regions' metal for is the thing in the hand on the stage — not a recoloured
    // rusty blade. Falls back the moment anything about that is missing.
    this.gear = (gear && gear.weapon) ? gear : null;
    try {
      this.hero = this.gear
        ? lootart.equippedHeroSprites(this.gear, tint)
        : sprites.heroSprites(tint);
    } catch (e) {
      try {
        this.hero = sprites.heroSprites(tint);
      } catch (e2) {
        this.hero = null;   // the stage is still worth showing without a hero
      }
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
    this.phaseCard = null;
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

  /* ---------------- the technique ----------------
   *
   * A forged blade's technique is not a second combat system. What it DOES is
   * an ordinary effect on the encounter — another probe, a longer clock, a ward
   * — resolved server-side through the same path items and class nodes already
   * use, and this method renders none of that. What it renders is the swing,
   * and the swing is the one place the player gets to feel nine regions of
   * metal.
   *
   * Everything here scales off ONE number: the rung, 1..9. A rung-eight blade
   * is bigger, brighter, louder, shakes harder and holds the impact frame four
   * times as long as a rung-one blade, and every one of those is a lerp off `k`
   * rather than a table somebody has to keep in step.
   *
   * Nothing here says anything about the problem. It cannot: it is handed a
   * colour, a rung and a rank name, and it has never seen the encounter.
   */
  async technique({ tier = 1, name = '', rank = '', colour = '#ffe8a0',
                    accent = '', crit = false } = {}) {
    const rung = clamp(Math.round(tier) || 1, 1, 9);
    const k = (rung - 1) / 8;                  // 0 at rung one, 1 at rung nine
    const edge = accent || colour;

    // The wind-up. Longer at the top of the ladder, because the anticipation is
    // most of what makes a big hit read as a big hit.
    this.heroPose = 1;
    this.heroLunge = this._amp(5 + 7 * k);
    if (this.cam) {
      this.cam.focus(STAGE.heroX);
      this.cam.cast(0.035 + 0.055 * k, 0.5 + 0.5 * k, 0.2 + 0.2 * k);
    }
    this.effects.push(this._charge(colour, edge, 0.26 + 0.24 * k, k));
    this._sfx('spell');
    await this._wait(this._t(0.22 + 0.22 * k));
    if (!this.el) return this;

    // The blow. The arc is drawn once, the length and thickness of it are the
    // rung, and the flash is capped at 1 because a screen cannot go whiter.
    this.effects.push(this._arc(colour, edge, 0.3 + 0.2 * k, k));
    this.flash = Math.min(1, 0.55 + 0.45 * k);
    this.knock = Math.max(this.knock, this._amp(6 + 8 * k));
    this.shake(3 + 8 * k);
    if (this.cam) {
      this.cam.punch(0.05 + 0.1 * k, 0.35 + 0.2 * k);
      this.cam.snap();
      // THE HOLD FRAME. One tenth of a second at rung one, four tenths at rung
      // nine: the frame the blow landed on is the one the eye gets to read.
      this.cam.hold(this._t(0.09 + 0.3 * k, { keep: true }));
    }
    this.burst({
      x: STAGE.enemyX, y: STAGE.ground - 30, colour,
      count: Math.round(14 + 26 * k), power: 46 + 74 * k,
      gravity: 120, life: 0.5 + 0.4 * k,
    });
    // One ring at the bottom of the ladder, four nested ones at the top, each
    // a beat behind the last. This is the cheapest legible way to say "bigger".
    const rings = 1 + Math.round(3 * k);
    for (let i = 0; i < rings; i++) {
      this.effects.push(this._ring(
        STAGE.enemyX, STAGE.ground - 30, i % 2 ? edge : colour,
        26 + 18 * i + 22 * k, (0.34 + 0.16 * k) * (1 + i * 0.35)));
    }
    if (rank) {
      // The rank's trailing numeral, not its whole name. "THE MEASURED CUT IX"
      // is a banner; a floating readout on a 192-pixel stage is two characters
      // wide before it starts overhanging the frame.
      const mark = String(rank).trim().split(/\s+/).pop().toUpperCase();
      this.damageNumber(mark, {
        kind: crit ? DAMAGE_KIND.CRIT : DAMAGE_KIND.HIT,
        x: STAGE.enemyX, y: STAGE.ground - 62 - 8 * k,
      });
    }
    this._sfx(rung >= 6 ? 'victory' : rung >= 3 ? 'crit' : 'hit');
    // The banner is the top third of the ladder only. A rung-two blade
    // announcing itself in forty-point letters is the thing that makes an
    // escalation stop meaning anything.
    if (rung >= 7 && name) {
      this.banner = {
        text: String(name).toUpperCase(),
        sub: String(rank || '').toUpperCase(),
        colour, t: 0, dur: this.reducedMotion ? 0.9 : 1.1 + 0.3 * k, slam: true,
      };
    }
    await this._wait(this._t(0.3 + 0.35 * k, { keep: true }));
    if (this.cam) this.cam.release();
    return this;
  }

  /* The wind-up: motes drawn IN toward the blade hand, tightening as they
   * arrive. The count and the reach are the rung. */
  _charge(colour, edge, dur, k) {
    const cx = STAGE.heroX + 6, cy = STAGE.ground - 26;
    const n = 5 + Math.round(9 * k);
    const reach = 20 + 26 * k;
    return { t: 0, dur, draw: (ctx, p) => {
      const pull = easeIn(p);
      for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i) / n + p * 2.2;
        const r = reach * (1 - pull) + 3;
        ctx.fillStyle = withAlpha(i % 3 === 0 ? edge : colour, 0.35 + 0.6 * pull);
        ctx.fillRect(Math.round(cx + Math.cos(a) * r),
                     Math.round(cy + Math.sin(a) * r * 0.6), 2, 2);
      }
      ctx.fillStyle = withAlpha(edge, pull * 0.9);
      const core = Math.round(1 + 4 * pull * (0.4 + k));
      ctx.fillRect(Math.round(cx - core / 2), Math.round(cy - core / 2), core, core);
    } };
  }

  /* The blow: one arc swept from over the hero's shoulder through the enemy,
   * with a trailing wake. Width, sweep and the wake's depth are the rung. */
  _arc(colour, edge, dur, k) {
    const x0 = STAGE.heroX + 4, x1 = STAGE.enemyX + 10;
    const top = STAGE.ground - 58 - 14 * k;
    const bottom = STAGE.ground - 8;
    const thick = 2 + Math.round(4 * k);
    const wake = 2 + Math.round(4 * k);
    return { t: 0, dur, draw: (ctx, p) => {
      const sweep = easeOut(p);
      const a = 1 - p;
      for (let i = 0; i < wake; i++) {
        const lag = clamp(sweep - i * 0.06, 0, 1);
        const x = lerp(x0, x1, lag);
        const y = lerp(top, bottom, lag * lag);
        ctx.strokeStyle = withAlpha(i === 0 ? edge : colour,
                                    a * (0.85 - i * 0.13));
        ctx.lineWidth = Math.max(1, thick - i);
        ctx.beginPath();
        ctx.moveTo(x0, top);
        ctx.quadraticCurveTo((x0 + x) / 2, top - 10 - 10 * k, x, y);
        ctx.stroke();
      }
      // The cut line itself: a hard bright bar at the point of contact.
      if (p > 0.45) {
        const cut = (p - 0.45) / 0.55;
        ctx.fillStyle = withAlpha('#ffffff', (1 - cut) * (0.5 + 0.5 * k));
        const h = Math.round(2 + 6 * k);
        ctx.fillRect(STAGE.enemyX - 22 - 14 * k, STAGE.ground - 34 - 4 * k,
                     Math.round(44 + 28 * k), h);
      }
    } };
  }

  /* ---------------- the elemental layer ----------------
   *
   * WHAT THIS IS NOT. It is not damage. Every number that reaches these methods
   * was decided by elements.resolve_damage on a base the player's typing had
   * already earned, and a cast that landed nothing arrives here as a zero and
   * renders as a zero. Nothing below can make a wrong line into a right one,
   * and nothing below is consulted until after grading.
   *
   * What it IS: the part of the fight the player can read. A hit that was worth
   * one and a half times as much has to LOOK worth one and a half times as
   * much, or the wheel is arithmetic happening somewhere off-screen and the
   * player learns it from a tooltip instead of from the fight.
   */

  /* Fall the condition's particles in front of the stage.
   *
   * `density` is the same 0..1 the backdrop scales its rain and its motes off,
   * so the 2D layer and the 3D stage are the same weather at the same strength
   * rather than two effects that happen to be on at once. A clear sky still
   * gets a few motes: air with nothing in it at all reads as a broken renderer,
   * not as a fine day. */
  _setSkyParticles(sky) {
    const s = sky || null;
    const style = (s && pixel.PARTICLE_STYLE[s.particle])
      || pixel.PARTICLE_STYLE.motes;
    const dens = s && typeof s.density === 'number' ? s.density : 0.22;
    const count = Math.max(5, Math.round(WEATHER_COUNT * dens));
    this.weatherStyle = style;
    /* Keyed by the condition, not by the biome: a region that has cleared up
     * gets a different particle field from the same region in a storm, which is
     * what makes the change visible when a fight opens. */
    this.weather = pixel.makeParticles(
      ((s && s.region) || '') + ':' + ((s && s.condition) || 'clear'),
      STAGE.w, STAGE.ground, count);
    return this;
  }

  /* The ground's own element. Called once per encounter, straight after
   * setScene, with the region's affinity — the region's BIOME pushed through
   * elements.BIOME_AFFINITY, so a cold place reads cold because of what it is.
   *
   * A neutral region gets nothing added, and that is the point: five of the
   * seventeen are neutral, and they are the control group the other twelve are
   * felt against. Tinting everything would leave nothing to notice.
   *
   * It is a TINT and a hazard now, and nothing else. What falls out of the sky
   * is the sky's business — see the block inside.
   */
  setAffinity(element, { hazard = '' } = {}) {
    const id = String(element || '').toUpperCase();
    this.affinity = (id && id !== 'NEUTRAL' && ELEMENT_FX[id]) ? id : '';
    this.hazard = this.affinity ? String(hazard || '') : '';
    if (!this.affinity) {
      /* Back to whatever the sky is doing. It was resolved in setScene and it
       * is not re-derived here: a second opinion about the weather is the exact
       * defect this pass exists to delete. */
      this._setSkyParticles(this.sky);
      this.affinityTint = 0;
      return this;
    }
    /* THE ELEMENT TINTS. IT NO LONGER DECIDES WHETHER IT IS RAINING.
     *
     * This used to overwrite the particle layer outright: a COLD region snowed
     * here whatever the sky said, a FIRE region threw embers whatever the sky
     * said, and twelve of the seventeen regions therefore had exactly one
     * weather each, permanently. The affinity of a place is a real thing and it
     * still colours the room — but it is a property of the GROUND, and the
     * ground does not get a vote on the sky. weather.py already puts snow in
     * cold places and fire in fire places, by climate, which is where that
     * belongs. */
    // Deliberately faint. This is the room, not an effect — at the strength a
    // cast uses it would read as something happening rather than as somewhere
    // being somewhere.
    this.affinityTint = this.reducedMotion ? 0.06 : 0.10;
    return this;
  }

  /* One elemental blow, landing on whoever it lands on.
   *
   *   element     what the blow is made of
   *   multiplier  elements.DamageResult.multiplier — the whole scale of this
   *   kind        OPPOSED | SECONDARY | WEAK_INTO | SAME | NEUTRAL
   *   damage      what the server says it cost, already resolved
   *   label       the server's own sentence fragment for the readout
   *   side        'enemy' (the player struck) or 'hero' (the player was struck)
   *
   * The enemy's health bar is moved ONLY when the enemy was the one hit. The
   * player's health lives on the top bar and belongs to the HUD, which reads it
   * off the same state the server just wrote.
   */
  async elemental({ element = 'NEUTRAL', multiplier = 1, kind = 'NEUTRAL',
                    damage = 0, label = '', side = 'enemy',
                    absorbed = 0, resisted = 0 } = {}) {
    const fx = elementFx(element);
    const k = elementalK(multiplier);
    const opposed = kind === 'OPPOSED';
    const shrugged = kind === 'SAME';
    const x = side === 'hero' ? STAGE.heroX : STAGE.enemyX;
    const y = STAGE.ground - 30;

    if (this.cam) this.cam.focus(x);

    // The wind-up is the tell. An opposed hit gets a visible gather before it
    // lands — which is the half-second in which a player who read the room
    // gets to know they read it right.
    if (opposed && !this.reducedMotion) {
      this.effects.push(this._gather(fx.colour, fx.dark, 0.24, x, y));
      await this._wait(this._t(0.2));
      if (!this.el) return this;
    }

    this.effects.push(this._elementEffect(fx.motion, {
      x, y, k, colour: fx.colour, dark: fx.dark, shrugged,
    }));

    // Weight. Every one of these is the same lerp off `k`, so the difference
    // between a counter and a shrug is one number and not six special cases.
    this.flash = Math.max(this.flash, shrugged ? 0.12 : 0.25 + 0.55 * k);
    this.shake(shrugged ? 1 : 2 + 7 * k);
    if (side === 'enemy') {
      this.knock = Math.max(this.knock, this._amp(3 + 8 * k));
      this.setEnemyHp(this.hp - Math.max(0, damage));
    } else {
      // The hero rocks back rather than the enemy rocking forward. Nothing goes
      // red and the character stays standing: being wrong is never punished
      // with a death screen in this game, and the stage holds that line too.
      this.knock = this._amp(-(2 + 5 * k));
      this.heroPose = 2;
    }
    if (this.cam) {
      this.cam.punch(0.03 + 0.09 * k, 0.3 + 0.2 * k);
      if (opposed) { this.cam.snap(); this.cam.hold(this._t(0.1 + 0.16 * k, { keep: true })); }
    }
    this.burst({
      x, y, colour: shrugged ? fx.dark : fx.colour,
      count: Math.round((shrugged ? 5 : 10) + 20 * k),
      power: 34 + 60 * k,
      // Fire and void refuse gravity in opposite directions, which is most of
      // what makes the two of them impossible to confuse at a glance.
      gravity: fx.motion === 'rise' ? -70 : fx.motion === 'implode' ? -10 : 130,
      life: 0.4 + 0.4 * k,
    });
    for (let i = 0; i < (opposed ? 3 : shrugged ? 0 : 1); i++) {
      this.effects.push(this._ring(x, y, i % 2 ? fx.dark : fx.colour,
        24 + 16 * i + 20 * k, (0.3 + 0.15 * k) * (1 + i * 0.3)));
    }

    // The readout. `damage` is the server's number and is never recomputed
    // here; `label` is the server's own word for the matchup. A zero with a
    // label on it is the elemental READING of an exchange the trials have
    // already counted, so it prints the label and not a second total — two
    // numbers for one blow is two truths about one blow.
    if (damage > 0 || !label) {
      this.damageNumber(damage, {
        kind: opposed ? DAMAGE_KIND.CRIT
          : shrugged ? DAMAGE_KIND.RESIST : DAMAGE_KIND.HIT,
        x, y: y - 14,
      });
    }
    if (label) {
      this.chips.push({
        text: String(label).toUpperCase(),
        colour: shrugged ? '#9b96b8' : fx.colour,
        x, y: y - 30, tx: x, ty: y - 44,
        t: 0, dur: this.reducedMotion ? 0.9 : 1.4,
      });
    }
    // What the armour actually did, said separately from the elemental
    // multiplier, because they are two different jobs and blending them into
    // one "defence" number is the thing elements.py refuses to do.
    if (absorbed > 0) {
      this.damageNumber(`-${absorbed} PLATE`, {
        kind: DAMAGE_KIND.RESIST, x: x + 18, y: y - 2,
      });
    } else if (resisted > 0.01) {
      this.damageNumber(`-${Math.round(resisted * 100)}%`, {
        kind: DAMAGE_KIND.RESIST, x: x + 18, y: y - 2,
      });
    }

    this._sfx(opposed ? 'crit' : shrugged ? 'tick' : fx.sfx);
    await this._wait(this._t(0.22 + 0.26 * k, { keep: true }));
    if (this.cam) this.cam.release();
    return this;
  }

  /* A status doing its work, on the turn it does it. Poison ticking has to be
   * visible ON THE VICTIM or a player watching their bar drop concludes the
   * game is cheating — which is the same complaint, differently worded, as
   * "the antidote does nothing". */
  statusTick({ status = '', element = '', damage = 0, side = 'hero',
               label = '' } = {}) {
    const fx = elementFx(element);
    const x = side === 'hero' ? STAGE.heroX : STAGE.enemyX;
    const y = STAGE.ground - 26;
    this.effects.push(this._motes(fx.colour, fx.dark, 0.7, x, y,
                                  String(status).toUpperCase() === 'POISONED'));
    if (damage > 0) {
      this.damageNumber(damage, { kind: DAMAGE_KIND.HIT, x: x - 14, y: y - 10 });
      if (side === 'enemy') this.setEnemyHp(this.hp - damage);
      this.shake(1);
    }
    if (label || status) {
      this.chips.push({
        text: String(label || status).toUpperCase(), colour: fx.colour,
        x, y: y - 24, tx: x, ty: y - 36,
        t: 0, dur: this.reducedMotion ? 0.8 : 1.2,
      });
    }
    this._sfx('tick');
    return this;
  }

  /* A draught going down. Deliberately on the player's side of the stage and
   * deliberately short: it is not a turn, and an animation long enough to feel
   * like one would be the interface arguing with the rule. */
  drink({ colour = '#ff6a7a', amount = 0, name = '' } = {}) {
    const x = STAGE.heroX, y = STAGE.ground - 24;
    this.effects.push(this._guard(colour, 0.45));
    this.burst({ x, y, colour, count: this.reducedMotion ? 4 : 14,
                 power: 30, gravity: -60, life: 0.5 });
    if (amount > 0) {
      this.damageNumber(`+${amount}`, { kind: DAMAGE_KIND.HEAL, x, y: y - 14 });
    }
    if (name) {
      this.chips.push({ text: String(name).toUpperCase(), colour,
                        x, y: y - 28, tx: x, ty: y - 42,
                        t: 0, dur: this.reducedMotion ? 0.8 : 1.3 });
    }
    this._sfx('unlock');
    return this;
  }

  /* ---------------- the six motions ----------------
   *
   * One builder each, all returning the same {t, dur, draw} shape the rest of
   * this file's effects use, so none of them needs its own place in the loop.
   * `k` is the elemental scale and is the ONLY thing that differs between a
   * counter and a shrug — the shape is the element's identity and does not
   * change with how well it went.
   */
  _elementEffect(motion, o) {
    switch (motion) {
      case 'rise':      return this._fxRise(o);
      case 'converge':  return this._fxConverge(o);
      case 'seep':      return this._fxSeep(o);
      case 'slam':      return this._fxSlam(o);
      case 'strike':    return this._fxStrike(o);
      case 'implode':   return this._fxImplode(o);
      default:          return this._fxPlain(o);
    }
  }

  /* FIRE. Columns that start at the feet and go up, and keep going after the
   * blow is over. Nothing about fire arrives; it grows. */
  _fxRise({ x, y, k, colour, dark, shrugged }) {
    const n = 3 + Math.round(5 * k);
    const dur = 0.42 + 0.3 * k;
    const reach = (shrugged ? 14 : 26) + 30 * k;
    const base = STAGE.ground;
    return { t: 0, dur, draw: (ctx, p) => {
      const a = 1 - easeIn(p);
      for (let i = 0; i < n; i++) {
        const off = ((i / Math.max(1, n - 1)) - 0.5) * (18 + 18 * k);
        const phase = (p + i * 0.13) % 1;
        const h = reach * easeOut(phase) * (0.6 + 0.4 * Math.sin(i * 2.1));
        const w = Math.max(1, Math.round(3 + 3 * k - phase * 3));
        ctx.fillStyle = withAlpha(i % 2 ? dark : colour, a * (1 - phase * 0.6));
        ctx.fillRect(Math.round(x + off - w / 2), Math.round(base - h), w,
                     Math.max(1, Math.round(h)));
        // the tip, brighter and one pixel narrower — a flame has a point
        ctx.fillStyle = withAlpha('#ffe8a0', a * (1 - phase) * 0.8);
        ctx.fillRect(Math.round(x + off - 1), Math.round(base - h - 2), 2, 3);
      }
    } };
  }

  /* COLD. Shards from outside the frame, arriving together and stopping dead.
   * Then a sheet of frost across the standing line that does not leave. */
  _fxConverge({ x, y, k, colour, dark, shrugged }) {
    const n = 5 + Math.round(7 * k);
    const dur = 0.45 + 0.25 * k;
    const reach = 34 + 30 * k;
    const len = 4 + Math.round(5 * k);
    return { t: 0, dur, draw: (ctx, p) => {
      const arrive = easeOut(clamp(p / 0.55, 0, 1));
      const hold = clamp((p - 0.55) / 0.45, 0, 1);
      for (let i = 0; i < n; i++) {
        const ang = (Math.PI * 2 * i) / n + 0.4;
        const r = reach * (1 - arrive) + 4;
        const px = x + Math.cos(ang) * r;
        const py = y + Math.sin(ang) * r * 0.7;
        ctx.strokeStyle = withAlpha(i % 3 ? colour : '#ffffff',
                                    (1 - hold) * (shrugged ? 0.45 : 0.95));
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px + Math.cos(ang) * len, py + Math.sin(ang) * len * 0.7);
        ctx.stroke();
      }
      // the sheet: it spreads outward along the ground and stays put
      const spread = (16 + 30 * k) * easeOut(p);
      ctx.fillStyle = withAlpha(dark, (1 - p * 0.7) * 0.55);
      ctx.fillRect(Math.round(x - spread), STAGE.ground - 1,
                   Math.round(spread * 2), 2);
    } };
  }

  /* POISON. Slow, upward, and still there when the animation is over. It does
   * not care how the fight is going right now. */
  _fxSeep({ x, y, k, colour, dark, shrugged }) {
    const n = 6 + Math.round(10 * k);
    const dur = 0.7 + 0.4 * k;
    const spread = 12 + 14 * k;
    const rise = 26 + 24 * k;
    return { t: 0, dur, draw: (ctx, p) => {
      const fade = p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3;
      for (let i = 0; i < n; i++) {
        const phase = (p * 0.8 + i / n) % 1;
        const off = Math.sin(i * 3.7) * spread;
        const py = STAGE.ground - 4 - rise * phase;
        const r = Math.max(1, Math.round(1 + 2.5 * (1 - phase) + 2 * k));
        ctx.fillStyle = withAlpha(i % 3 ? colour : dark,
                                  fade * (1 - phase) * (shrugged ? 0.4 : 0.85));
        ctx.fillRect(Math.round(x + off - r / 2), Math.round(py), r, r);
      }
      // the low cloud, which is what makes it read as air rather than as sparks
      ctx.fillStyle = withAlpha(dark, fade * 0.3 * (shrugged ? 0.5 : 1));
      const w = spread * 2 * (0.6 + 0.4 * easeOut(p));
      ctx.fillRect(Math.round(x - w / 2), STAGE.ground - 6, Math.round(w), 6);
    } };
  }

  /* BRUTE. One thing comes down and the ground takes it. No cleverness at all. */
  _fxSlam({ x, y, k, colour, dark, shrugged }) {
    const dur = 0.4 + 0.22 * k;
    const w = Math.round(10 + 14 * k);
    return { t: 0, dur, draw: (ctx, p) => {
      const fall = easeIn(clamp(p / 0.35, 0, 1));
      if (p < 0.4) {
        const top = lerp(STAGE.ground - 92, STAGE.ground - 30, fall);
        ctx.fillStyle = withAlpha(colour, 0.9);
        ctx.fillRect(Math.round(x - w / 2), Math.round(top), w,
                     Math.round(STAGE.ground - 26 - top));
        ctx.fillStyle = withAlpha('#ffffff', 0.5 * (1 - fall));
        ctx.fillRect(Math.round(x - 2), Math.round(top), 4,
                     Math.round(STAGE.ground - 26 - top));
      }
      // the shock, running both ways down the standing line
      if (p >= 0.3) {
        const q = (p - 0.3) / 0.7;
        const reach = (26 + 46 * k) * easeOut(q);
        const a = (1 - q) * (shrugged ? 0.4 : 0.9);
        ctx.fillStyle = withAlpha(dark, a);
        for (const dir of [-1, 1]) {
          const h = Math.max(1, Math.round(5 * (1 - q) + 2 * k));
          ctx.fillRect(Math.round(x + dir * reach), STAGE.ground - h,
                       Math.round(3 + 3 * k), h);
        }
        ctx.fillStyle = withAlpha(colour, a * 0.7);
        ctx.fillRect(Math.round(x - reach), STAGE.ground - 1,
                     Math.round(reach * 2), 1);
      }
    } };
  }

  /* LIGHTNING. Already over by the time you saw it. One jagged instant from the
   * top of the frame, redrawn on a different path two or three times. */
  _fxStrike({ x, y, k, colour, dark, shrugged }) {
    const dur = 0.3 + 0.12 * k;
    const segs = 5 + Math.round(4 * k);
    const jitter = 5 + 6 * k;
    // The path is baked, not drawn per frame: a bolt that re-randomised every
    // frame would be a flicker, and a bolt is a shape.
    const paths = [];
    for (let s = 0; s < 2 + Math.round(2 * k); s++) {
      const pts = [];
      for (let i = 0; i <= segs; i++) {
        const t = i / segs;
        pts.push([x + (Math.random() - 0.5) * jitter * (1 - t) * 2 + (s - 1) * 3,
                  lerp(0, y, t)]);
      }
      paths.push(pts);
    }
    return { t: 0, dur, draw: (ctx, p) => {
      // Strobe: on, off, on. That is what makes it read as electricity rather
      // than as a beam.
      const on = p < 0.12 || (p > 0.2 && p < 0.32) || (p > 0.42 && p < 0.5);
      if (!on) return;
      const a = shrugged ? 0.5 : 1;
      paths.forEach((pts, i) => {
        ctx.strokeStyle = withAlpha(i === 0 ? '#ffffff' : colour, a * (1 - i * 0.25));
        ctx.lineWidth = Math.max(1, 2 + Math.round(2 * k) - i);
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (const [px, py] of pts.slice(1)) ctx.lineTo(px, py);
        ctx.stroke();
      });
      ctx.fillStyle = withAlpha(dark, a * 0.5);
      ctx.fillRect(Math.round(x - 10 - 8 * k), Math.round(y - 2),
                   Math.round(20 + 16 * k), 4);
    } };
  }

  /* VOID. Not a force — an absence, arriving where a force was expected. The
   * only effect in this file that runs inward. */
  _fxImplode({ x, y, k, colour, dark, shrugged }) {
    const dur = 0.5 + 0.3 * k;
    const n = 8 + Math.round(10 * k);
    const reach = 30 + 32 * k;
    return { t: 0, dur, draw: (ctx, p) => {
      const pull = easeIn(clamp(p / 0.7, 0, 1));
      for (let i = 0; i < n; i++) {
        const ang = (Math.PI * 2 * i) / n + p * 1.6;
        const r = reach * (1 - pull) + 2;
        ctx.fillStyle = withAlpha(i % 2 ? colour : dark,
                                  (shrugged ? 0.4 : 0.9) * (0.3 + 0.7 * pull));
        ctx.fillRect(Math.round(x + Math.cos(ang) * r),
                     Math.round(y + Math.sin(ang) * r * 0.75), 2, 2);
      }
      // the hole. It grows while everything is being drawn in and then it is
      // simply not there any more, which is the whole idea.
      const core = (3 + 9 * k) * (p < 0.7 ? pull : 1 - (p - 0.7) / 0.3);
      ctx.fillStyle = withAlpha('#120f1c', 0.9);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.5, core), 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = withAlpha(colour, (1 - p) * 0.8);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.5, core + 2 + 4 * (1 - pull)), 0, Math.PI * 2);
      ctx.stroke();
    } };
  }

  /* NEUTRAL. A plain impact. Weather-free: whatever happened, happened because
   * you did it. */
  _fxPlain({ x, y, k, colour, shrugged }) {
    const dur = 0.3 + 0.15 * k;
    return { t: 0, dur, draw: (ctx, p) => {
      const r = (10 + 22 * k) * easeOut(p);
      ctx.strokeStyle = withAlpha(colour, (1 - p) * (shrugged ? 0.4 : 0.85));
      ctx.lineWidth = Math.max(1, 2 - Math.round(p * 2));
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.5, r), 0, Math.PI * 2);
      ctx.stroke();
    } };
  }

  /* The gather before a counter lands. Only opposed hits get one — it is the
   * half-second that says "you read the room right" before the number appears. */
  _gather(colour, dark, dur, x, y) {
    return { t: 0, dur, draw: (ctx, p) => {
      const pull = easeIn(p);
      for (let i = 0; i < 10; i++) {
        const ang = (Math.PI * 2 * i) / 10 + p * 3;
        const r = 34 * (1 - pull) + 3;
        ctx.fillStyle = withAlpha(i % 3 ? colour : dark, 0.3 + 0.6 * pull);
        ctx.fillRect(Math.round(x + Math.cos(ang) * r),
                     Math.round(y + Math.sin(ang) * r * 0.7), 2, 2);
      }
    } };
  }

  /* The lingering mark of a status: a slow drift of the element's own colour
   * over whoever is carrying it. Drips downward for poison, rises for the rest,
   * because poison is the one that is IN you rather than on you. */
  _motes(colour, dark, dur, x, y, down) {
    const n = 7;
    return { t: 0, dur, draw: (ctx, p) => {
      const a = 1 - p;
      for (let i = 0; i < n; i++) {
        const phase = (p + i / n) % 1;
        const off = Math.sin(i * 2.3 + p * 2) * 9;
        const py = down ? y - 12 + 24 * phase : y + 8 - 26 * phase;
        ctx.fillStyle = withAlpha(i % 2 ? colour : dark, a * (1 - phase) * 0.9);
        ctx.fillRect(Math.round(x + off), Math.round(py), 2, 2);
      }
    } };
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

  /* ---------------- the phase turn ----------------
   *
   * THE ONE BEAT THIS PASS ADDS, and the requirement it answers is not "make
   * it pretty". It is: a player has to SEE the phase turn, SEE it get
   * stronger, and be told WHY they are suddenly losing. Three jobs, three
   * places, and if any one of them is cut the other two stop working.
   *
   * Everything here is driven by the payload gauntlet/bestiary.phase_beat()
   * returns. Nothing about the timing is invented at this end: the server owns
   * the beat because the server owns the fight, and a client that made up its
   * own 1900ms would drift from the combat log the moment either was tuned.
   * Every field has a fallback, so a caller holding an older payload — or none
   * at all — still gets a legible turn.
   *
   *   0ms      FREEZE. The stage stops for freeze_ms. The cheapest way to make
   *            a hit read as an event, and it costs no art.
   *   0ms      FLASH and SHAKE, and the pip for the phase just cleared goes
   *            out. This is "something happened".
   *   140ms    THE ART TURNS, under the flash, so the creature is DIFFERENT
   *            when the white clears instead of transforming in front of an
   *            eye that is watching it. This is the line that was missing: the
   *            sprite builder has drawn six stages since it was written and
   *            nothing ever asked it for one.
   *   420ms    THE HERALD — the boss's own line for the phase it is entering.
   *   1100ms   THE TELL — one sentence naming what changed. The easiest thing
   *            on this list to cut and the one that must not be, because it is
   *            the entire difference between "this got hard" and "this got
   *            hard because it is two elements now".
   *
   * Reduced motion collapses the flourishes and keeps both text holds at full
   * length. Cutting reading time is not an accessibility win.
   */
  async bossPhaseTurn(beat = {}) {
    const stage = bosses.bossPhase(beat.art_phase !== undefined
      ? { art_phase: beat.art_phase }
      : { phase: beat.phase, phases: beat.phases });
    const phases = (beat.phases | 0) || this.bossPhases;
    const ms = (v, d) => Math.max(0, (v === undefined ? d : v)) / 1000;

    /* Warm the incoming stage BEFORE the flash. A phase change is the one
     * moment in a fight that asks for fifteen canvases at once, and generating
     * them inside the render loop is a visible hitch at exactly the moment the
     * player is looking hardest. */
    this._warmPhase(stage);

    this._sfx('crit');
    this.flash = Math.max(this.flash, beat.flash === undefined ? 0.92 : beat.flash);
    this.shake(this._amp(beat.shake === undefined ? 8 : beat.shake));
    this.holdUntil = this.clock + ms(beat.freeze_ms, 180);
    this.tintColour = beat.colour || '#ff6a7a';
    this.tint = this.reducedMotion ? 0 : 0.38;
    if (phases) {
      this.pips = phases;
      this.pipsLit = Math.max(0, phases - (beat.phase | 0));
    }
    this.burst({
      x: STAGE.enemyX, y: STAGE.ground - 54,
      colour: beat.colour || '#ff6a7a', count: 22, power: 70, life: 0.55,
    });

    await this._wait(this._t(ms(beat.art_at_ms, 140), { keep: true }));
    if (!this.el) return this;
    // The turn itself. Everything above is announcement; this is the change.
    this.bossPhase = stage;
    if (phases) this.bossPhases = phases;
    this.bossState = 'hurt';
    this.bossStateT = 0;
    this.sprites.clear();          // the cached frames are of the old creature

    await this._wait(this._t(Math.max(0, ms(beat.herald_at_ms, 420)
      - ms(beat.art_at_ms, 140)), { keep: true }));
    if (!this.el) return this;
    this.tint = 0;
    this.phaseCard = {
      label: String(beat.label || beat.phase_label || 'IT CHANGES').toUpperCase(),
      herald: String(beat.herald || ''),
      tell: '',
      colour: beat.colour || '#ff6a7a',
      t: 0, dur: this.reducedMotion ? 2.4 : 2.6,
    };

    await this._wait(this._t(Math.max(0, ms(beat.tell_at_ms, 1100)
      - ms(beat.herald_at_ms, 420)), { keep: true }));
    if (!this.el || !this.phaseCard) return this;
    this.phaseCard.tell = String(beat.tell || '');
    this._sfx('tick');
    return this;
  }

  /* The art stage, set without the beat. For a reload into a fight already
   * three phases deep, and for any caller that would rather drive the turn
   * itself. */
  setBossPhase(phase, phases) {
    if (phases !== undefined) this.bossPhases = Math.max(0, phases | 0);
    const stage = bosses.bossPhase(
      phases === undefined ? phase : { phase, phases });
    if (stage === this.bossPhase) return this;
    this.bossPhase = stage;
    this.sprites.clear();
    this._warmPhase(stage);
    return this;
  }

  /* Build one stage's canvases outside the render loop. Never load-bearing:
   * bossSprite generates on demand anyway, so a throw here costs a hitch and
   * nothing else. */
  _warmPhase(stage) {
    if (!this.scene || !this.scene.boss) return this;
    try {
      bosses.warmBoss(this.scene.enemy.sprite,
        this.scene.enemy.colour || undefined, stage);
    } catch (e) { /* the sprite builder will do it lazily instead */ }
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
        : monsterart.monsterSprite(e.sprite, this.scene.pattern, frame,
            e.colour || undefined, { region: this.scene.regionId });
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
    /* The impact freeze. `holdUntil` was declared in the constructor, reset in
     * destroy(), and never once read — so the one field in this class whose
     * entire job is to stop time did not. A phase turn is the beat it was put
     * there for. Timers and the render still run: freezing the promise queue
     * would strand whatever is awaiting the rest of the beat. */
    if (this.clock >= this.holdUntil || this.reducedMotion) this._update(dt);
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
    if (this.phaseCard) {
      this.phaseCard.t += dt;
      if (this.phaseCard.t >= this.phaseCard.dur) this.phaseCard = null;
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
    this._drawAffinity(ctx);
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
    this._drawPhaseCard(ctx);
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

  /* The area's affinity, as a wash over the room and a band along the ground.
   * Under the fighters rather than over them, because it is where they are
   * standing and not something that is happening to them — and because a wash
   * over the top would drag every sprite in the game off its own ramp. */
  _drawAffinity(ctx) {
    if (!this.affinity || !this.affinityTint) return;
    const fx = elementFx(this.affinity);
    ctx.fillStyle = withAlpha(fx.colour, this.affinityTint);
    ctx.fillRect(0, 0, STAGE.w, STAGE.ground);
    // The hazard is the floor. Boots answer it, so it is drawn at boot height:
    // a band the player's feet are actually in.
    if (this.hazard) {
      ctx.fillStyle = withAlpha(fx.dark, this.affinityTint * 2.2);
      ctx.fillRect(0, STAGE.ground - 3, STAGE.w, 4);
      ctx.fillStyle = withAlpha(fx.colour, this.affinityTint * 1.6);
      for (let x = (Math.floor(this.clock * 6) % 8); x < STAGE.w; x += 8) {
        ctx.fillRect(x, STAGE.ground - 1, 3, 1);
      }
    }
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
        phase: this.bossPhase,
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

  /* The herald and the tell. Two registers on purpose: the boss's own line is
   * theatre and is allowed to be long, the tell is mechanics and is one short
   * sentence in a plainer colour underneath it. A player who reads only the
   * second one has still been told why they are losing, which is the point.
   *
   * Drawn low rather than across the middle: the middle is where the banner
   * goes and where the creature IS, and covering the creature during the one
   * beat whose whole purpose is showing the creature change would be a joke at
   * the file's own expense. */
  _drawPhaseCard(ctx) {
    const c = this.phaseCard;
    if (!c) return;
    const k = clamp(c.t / c.dur, 0, 1);
    const inK = clamp(c.t / 0.18, 0, 1);
    const alpha = (k > 0.82 ? 1 - (k - 0.82) / 0.18 : 1) * inK;
    const herald = this._wrap(c.herald, 34);
    const tell = c.tell ? this._wrap(c.tell, 40) : [];
    const lines = 1 + herald.length + tell.length;
    const h = 10 + lines * 9;
    const y0 = STAGE.h - h - 22;

    ctx.globalAlpha = alpha * 0.86;
    ctx.fillStyle = '#0b0a12';
    ctx.fillRect(0, y0, STAGE.w, h);
    ctx.fillStyle = withAlpha(c.colour, 0.7);
    ctx.fillRect(0, y0, STAGE.w, 1);
    ctx.fillRect(0, y0 + h - 1, STAGE.w, 1);
    /* A bar that drains for as long as the card is up, so the player can see
     * how much reading time is left rather than losing a sentence to a
     * disappearance they did not expect. */
    ctx.fillStyle = withAlpha(c.colour, 0.45);
    ctx.fillRect(0, y0 + h - 1, Math.round(STAGE.w * (1 - k)), 1);
    ctx.globalAlpha = alpha;

    let y = y0 + 9;
    this._text(ctx, c.label, STAGE.w / 2, y, {
      size: c.label.length > 24 ? 5 : 6, colour: c.colour, outline: '#0b0a12' });
    y += 10;
    for (const line of herald) {
      this._text(ctx, line, STAGE.w / 2, y, {
        size: 6, colour: '#e8e6f5', outline: '#0b0a12' });
      y += 9;
    }
    for (const line of tell) {
      this._text(ctx, line, STAGE.w / 2, y, {
        size: 5, colour: '#9b96b8', outline: '#0b0a12' });
      y += 9;
    }
    ctx.globalAlpha = 1;
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

/* 1.1.0 adds technique(): the forged blade's swing, scaled entirely by its
 * rung, and the camera hold frame in battlescene.js that it drives. */
export const FX_VERSION = '1.2.0';   // 1.2: bossPhaseTurn, and the art phase finally reaches drawBoss
