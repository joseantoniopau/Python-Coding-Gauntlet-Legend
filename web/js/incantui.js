/* Python Coding Gauntlet Legend — the incantation interface.
 *
 * This is the typed-combat screen: a line of Python rendered as grey ghost text
 * with holes in it, a battlefield of enemies whose names ARE the identifiers
 * that fill those holes, and a bar of incantations the player has learned.
 *
 * The input mechanic is deliberately untimed by default. Correctness is the
 * only gate in Adventure Mode — the player may take as long as they like, and a
 * wrong cast costs the turn and nothing else. That is the desirable difficulty:
 * enough of a sting to make the next attempt effortful, never enough to punish.
 * Timed Practical Mode turns the timer on, because measuring is a different job from
 * teaching and the two are never blurred.
 *
 * Four things this module does NOT do, on purpose:
 *   - It does not grade. It assembles what the player typed and hands it to the
 *     caller. Every verdict, every point of damage and every teaching line comes
 *     back from the server, so the UI can never become a second grader that
 *     disagrees with the first one.
 *   - It does not supply answers. The only text it ever writes into a hole is a
 *     name the player clicked, or a tier-0 scaffold fill the server explicitly
 *     sent as part of the teaching ramp.
 *   - It does not own game state. Enemy HP, turn number and mastery are pushed
 *     in; nothing is inferred.
 *   - It does not teach in Timed Practical Mode. Notes, template previews and the
 *     teaching line under a failure are all suppressed there.
 *
 * It styles itself, like fx.js does, so index.html and game.css never have to
 * know it exists.
 */
import { highlight } from './editor.js';

/* ------------------------------------------------------------------ tiers */

/* The retrieval-support gradient. Each rung removes one kind of help, and the
 * rung the player is on is shown on screen — seeing the scaffold go is the
 * reward for no longer needing it. */
export const TIER = Object.freeze({ SHOWN: 0, BLANKS: 1, SHAPE: 2, NAME: 3 });

const TIER_META = Object.freeze([
  { key: 'SHOWN',  label: 'LINE SHOWN',
    blurb: 'The whole line is given. Fill the one blank that carries the idea.' },
  { key: 'BLANKS', label: 'BLANKS',
    blurb: 'The line is given. Every blank in it is yours to fill.' },
  { key: 'SHAPE',  label: 'SHAPE ONLY',
    blurb: 'Keywords and punctuation remain. The names are gone.' },
  { key: 'NAME',   label: 'NAME ONLY',
    blurb: 'Only the name of the incantation. Write the line from memory.' },
]);

/* The three layers a cast can fail at, in the order they are checked. The
 * player is told which one broke, never a bare "wrong" — knowing whether the
 * Python was malformed, aimed at nothing, or simply the wrong idea is the
 * difference between a correction and a guess. */
export const CAST_LAYER = Object.freeze({
  SYNTAX: 'syntax', BINDING: 'binding', SEMANTICS: 'semantics',
});

const LAYER_META = Object.freeze({
  syntax: {
    label: 'SYNTAX', tone: 'red',
    title: 'The words did not form Python.',
    teach: 'Python read the line and could not parse it. Punctuation, a colon, '
         + 'a bracket — something structural, not something about this fight.',
  },
  binding: {
    label: 'BINDING', tone: 'gold',
    title: 'The line is Python. It is aimed at nothing.',
    teach: 'Every name in a line has to exist. You named something that is not '
         + 'on this battlefield, or spelled one of them differently.',
  },
  semantics: {
    label: 'SEMANTICS', tone: 'violet',
    title: 'Real Python, real names, wrong idea.',
    teach: 'The line runs. It does not do what this enemy requires — the wrong '
         + 'operation for that structure, or the right one in the wrong place.',
  },
});

/* Kept locally rather than imported because editor.js does not export its sets.
 * Used only to decide what survives at tier 2; if the two drift, the cost is a
 * word being dotted out that could have been shown, never a wrong verdict. */
const PY_KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break',
  'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
  'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal',
  'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
]);

const PY_BUILTINS = new Set([
  'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float', 'int',
  'len', 'list', 'map', 'max', 'min', 'range', 'reversed', 'round', 'set',
  'sorted', 'str', 'sum', 'tuple', 'zip', 'print', 'isinstance', 'type',
]);

const HOLE_GLYPH = '____';
const MAX_HOTKEYS = 8;
const LOG_LINES = 4;

/* --------------------------------------------------------------- helpers */

function esc(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

function node(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}

/* Highlighting is delegated to editor.js so a line of Python looks identical
 * here and in the editor the player already knows. */
function paint(source) {
  try { return highlight(source); } catch (e) { return esc(source); }
}

/* A template is literal Python with holes in it. Two hole forms are accepted:
 *   ____            an unnamed hole
 *   {{what}}        a NAMED hole; the name is shown dim inside it as a hint
 * Runs of two or more underscores count, so ______ is one hole and not three.
 *
 * A named hole may appear more than once, and every occurrence is the SAME
 * blank: `{{dp}}[{{i}}] = {{dp}}[{{i}} - 1] + {{dp}}[{{i}} - 2]` is two blanks
 * written six times, not six blanks. That is not a rendering convenience — it
 * is the lesson. A variable used repeatedly in one line is one variable, and
 * asking the player to type `dp` six times would teach the opposite while
 * silently disagreeing with the engine about how many answers a cast has. */
export function parseTemplate(template) {
  const parts = [];
  const text = String(template || '');
  const re = /_{2,}|\{\{([^}]*)\}\}/g;
  let last = 0;
  let index = 0;
  const claimed = new Map();        // hole name -> the slot it already owns
  let m = re.exec(text);
  while (m) {
    if (m.index > last) parts.push({ type: 'text', text: text.slice(last, m.index) });
    const name = (m[1] || '').trim();
    let at;
    if (name && claimed.has(name)) {
      at = claimed.get(name);
    } else {
      at = index;
      index += 1;
      if (name) claimed.set(name, at);
    }
    parts.push({ type: 'hole', index: at, name, hint: name });
    last = m.index + m[0].length;
    m = re.exec(text);
  }
  if (last < text.length) parts.push({ type: 'text', text: text.slice(last) });
  return parts;
}

/* How many ANSWERS a template wants, which is the number of distinct holes and
 * not the number of blanks drawn on screen. */
export function holeCount(template) {
  const holes = parseTemplate(template).filter(p => p.type === 'hole');
  return holes.length ? Math.max(...holes.map(h => h.index)) + 1 : 0;
}

/* The hole names, in slot order. Empty strings for unnamed `____` holes, so a
 * caller can still map a positional answer array back onto named holes. */
export function holeNames(template) {
  const names = [];
  for (const part of parseTemplate(template)) {
    if (part.type === 'hole' && names[part.index] === undefined) {
      names[part.index] = part.name || '';
    }
  }
  for (let i = 0; i < names.length; i += 1) if (names[i] === undefined) names[i] = '';
  return names;
}

/* Assembles the line the player actually wrote, holes substituted in place. */
export function assemble(template, values) {
  return parseTemplate(template).map((part) => (
    part.type === 'text' ? part.text : (values[part.index] || '')
  )).join('');
}

/* Tier 2 keeps the skeleton and takes the names: keywords, builtins, numbers,
 * strings and every piece of punctuation stay; anything that is a name the
 * player has to remember becomes dots of the same width, so the shape of the
 * line still tells them how long the word was without telling them the word. */
function shapeOf(segment) {
  const out = [];
  const re = /[A-Za-z_][A-Za-z0-9_]*/g;
  let last = 0;
  let m = re.exec(segment);
  while (m) {
    if (m.index > last) out.push(paint(segment.slice(last, m.index)));
    const word = m[0];
    if (PY_KEYWORDS.has(word) || PY_BUILTINS.has(word)) out.push(paint(word));
    else out.push(`<span class="inc-shape">${'·'.repeat(word.length)}</span>`);
    last = m.index + word.length;
    m = re.exec(segment);
  }
  if (last < segment.length) out.push(paint(segment.slice(last)));
  return out.join('');
}

function clamp(n, lo, hi) { return Math.max(lo, Math.min(hi, n)); }

function fmtClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/* ------------------------------------------------------------------ class */

export class IncantationUI {
  /* host may be omitted and supplied later via mount(), matching BattleFX. */
  constructor(host, opts = {}) {
    this.opts = opts || {};
    this.onCast = this.opts.onCast || null;
    this.onSelectMove = this.opts.onSelectMove || null;
    this.onTimeout = this.opts.onTimeout || null;
    this.audio = this.opts.audio || null;
    /* WHAT A CAST SOUNDS LIKE IS WHAT THE CASTER IS MADE OF.
     * audio.castElement() has seven architectures, not seven pitches — a FIRE
     * cast and a VOID cast do not share a layer — so this field is the whole
     * difference between "a spell went off" and "you cast fire". The server
     * names it (`element.player`, elements.py's own id) and main.js hands it
     * over; unknown and absent both mean NEUTRAL, never an exception. */
    this.element = String(this.opts.element || '') || 'neutral';

    this.mode = this.opts.mode === 'interview' ? 'interview' : 'adventure';
    /* Timed Practical measures, so it never shows a scaffold. Overridable for a
     * future format that deliberately measures at a lower rung. */
    this.interviewTier = this.opts.interviewTier === undefined
      ? TIER.NAME : this.opts.interviewTier;
    this.castOnTimeout = this.opts.castOnTimeout !== false;

    this.reducedMotion = this.opts.reducedMotion === undefined
      ? IncantationUI._prefersReducedMotion() : !!this.opts.reducedMotion;

    this.el = null;
    this.hostEl = null;
    this.destroyed = false;

    this.encounter = null;
    this.enemies = [];
    this.moves = [];
    this.moveIndex = -1;
    this.defaultTier = TIER.BLANKS;
    this.turn = 1;
    this.busy = false;

    this.holeParts = [];      // the parsed template of the selected move
    this.holeNodes = [];      // [{wrap, ghost, input, locked}]
    this.holeValues = [];
    this.focusHole = 0;
    this.rawInput = null;     // tier 3: one field for the whole line
    this.rawValue = '';
    this.startedAt = 0;
    this.log = [];

    this.timerTotal = 0;
    this.timerLeft = 0;
    this.timerHandle = 0;

    this._listeners = [];
    this._flashTimer = 0;

    this._onDocKey = this._onDocKey.bind(this);
    this._tickTimer = this._tickTimer.bind(this);

    if (host) this.mount(host);
  }

  /* ------------------------------------------------------ lifecycle */

  mount(host) {
    const target = typeof host === 'string' ? document.querySelector(host) : host;
    if (!target) throw new Error('IncantationUI.mount: no host element');
    if (this.el) this.unmount();

    IncantationUI._ensureStyle();

    this.hostEl = target;
    this.el = node('div', 'inc-root');
    this.el.setAttribute('data-tier', String(this.defaultTier));

    this.enemyBar = node('div', 'inc-enemies');
    this.enemyBar.setAttribute('role', 'list');
    this.enemyBar.setAttribute('aria-label', 'the battlefield — every name here is a name you can type');

    this.stage = node('div', 'inc-stage');

    this.tierBar = node('div', 'inc-tier');
    this.lineWrap = node('div', 'inc-linewrap');
    this.moveTitle = node('div', 'inc-movetitle');
    this.line = node('div', 'inc-line');
    this.line.setAttribute('role', 'group');
    this.lineWrap.appendChild(this.moveTitle);
    this.lineWrap.appendChild(this.line);

    this.timerWrap = node('div', 'inc-timerwrap');
    this.timerBar = node('div', 'inc-timerbar');
    this.timerFill = node('i', '');
    this.timerBar.appendChild(this.timerFill);
    this.timerText = node('span', 'inc-timertext', '00:00');
    this.timerWrap.appendChild(this.timerBar);
    this.timerWrap.appendChild(this.timerText);
    this.timerWrap.style.display = 'none';

    this.feedback = node('div', 'inc-feedback');
    this.feedback.setAttribute('role', 'status');
    this.feedback.setAttribute('aria-live', 'polite');

    this.actions = node('div', 'inc-actions');
    this.castBtn = node('button', 'btn primary inc-cast', 'CAST ✦');
    this.castBtn.type = 'button';
    this.turnTag = node('span', 'inc-turn', 'TURN 1');
    this.keyHint = node('span', 'inc-keys');
    this.keyHint.innerHTML = '<b>tab</b> next blank · <b>enter</b> cast · '
      + '<b>esc</b> out to the moveset · <b>1-8</b> pick';
    this.actions.appendChild(this.castBtn);
    this.actions.appendChild(this.turnTag);
    this.actions.appendChild(this.keyHint);

    this.logBox = node('div', 'inc-log');

    this.stage.appendChild(this.tierBar);
    this.stage.appendChild(this.lineWrap);
    this.stage.appendChild(this.timerWrap);
    this.stage.appendChild(this.feedback);
    this.stage.appendChild(this.actions);
    this.stage.appendChild(this.logBox);

    this.moveBar = node('div', 'inc-moveset');
    this.moveBar.setAttribute('role', 'toolbar');
    this.moveBar.setAttribute('aria-label', 'moveset');
    this.teachBox = node('div', 'inc-teach');

    this.el.appendChild(this.enemyBar);
    this.el.appendChild(this.stage);
    this.el.appendChild(this.moveBar);
    this.el.appendChild(this.teachBox);
    target.appendChild(this.el);

    this._on(this.castBtn, 'click', () => this.cast());
    this._on(this.el, 'keydown', (e) => this._onRootKey(e));
    this._on(document, 'keydown', this._onDocKey);

    this._applyMotion();
    this._renderAll();
    return this.el;
  }

  unmount() {
    this._stopTimer();
    if (this._flashTimer) { clearTimeout(this._flashTimer); this._flashTimer = 0; }
    for (const [target, type, fn] of this._listeners) {
      if (target && target.removeEventListener) target.removeEventListener(type, fn);
    }
    this._listeners.length = 0;
    if (this.el && this.el.parentNode) this.el.parentNode.removeChild(this.el);
    this.el = null;
    this.hostEl = null;
    this.holeNodes = [];
    this.rawInput = null;
  }

  /* Safe to call twice, and safe to call while a cast is in flight: a late
   * resolveCast on a destroyed UI is ignored rather than thrown. */
  destroy() {
    this.unmount();
    this.destroyed = true;
    this.encounter = null;
    this.enemies = [];
    this.moves = [];
    this.holeParts = [];
    this.holeValues = [];
    this.log = [];
    this.onCast = null;
    this.onSelectMove = null;
    this.onTimeout = null;
    this.audio = null;
    IncantationUI._releaseStyle();
  }

  /* ------------------------------------------------------ state in */

  /* encounter = {
   *   id, mode, turn, timer_seconds, banner,
   *   enemies: [{ id, name, title, type, value, note, hp, hp_max, dead }],
   * }
   * `name` is the Python identifier and the thing the player types. `title` is
   * the theatrical name and is decoration. */
  /** The element the player casts in. Settable mid-field: a fight can change
   *  what the player is made of, and the cast has to follow it. */
  setElement(id) {
    this.element = String(id || '') || 'neutral';
    return this;
  }

  setEncounter(encounter) {
    this.encounter = encounter || null;
    const enc = this.encounter || {};
    if (enc.element !== undefined) this.setElement(enc.element);
    this.enemies = Array.isArray(enc.enemies) ? enc.enemies.slice() : [];
    this.turn = enc.turn || 1;
    if (enc.mode) this.setMode(enc.mode, { silent: true });
    this.busy = false;
    this.log = [];
    this.startedAt = Date.now();
    this._clearFeedback();
    if (this.moveIndex < 0 || this.moveIndex >= this.moves.length) {
      this.moveIndex = this._firstUsableMove();
    }
    this._loadMove({ keepValues: false });
    this._renderAll();
    this.setTimer(enc.timer_seconds || 0);
    return this;
  }

  /* moves = [{ id, name, template, teach, tier, mastery, locked, prefill }]
   * `prefill` is only ever read at tier 0 — the scaffold rung where the game
   * shows the line and asks for one blank — and comes from the server, which is
   * the only thing allowed to know an answer. */
  setMoveset(moves) {
    this.moves = Array.isArray(moves) ? moves.slice(0, 32) : [];
    if (this.moveIndex >= this.moves.length) this.moveIndex = -1;
    if (this.moveIndex < 0) this.moveIndex = this._firstUsableMove();
    this._loadMove({ keepValues: false });
    this._renderMoveset();
    this._renderLine();
    this._renderTier();
    return this;
  }

  /* tier without a moveId sets the floor for every move that does not carry its
   * own; with one, it sets that move's earned rung. */
  setTier(tier, moveId) {
    const t = clamp(Math.round(Number(tier) || 0), TIER.SHOWN, TIER.NAME);
    if (moveId === undefined || moveId === null) {
      this.defaultTier = t;
    } else {
      const m = this.moves.find(x => x.id === moveId);
      if (m) m.tier = t;
    }
    this._loadMove({ keepValues: true });
    this._renderTier();
    this._renderLine();
    this._renderMoveset();
    return this;
  }

  setMode(mode, { silent = false } = {}) {
    this.mode = mode === 'interview' ? 'interview' : 'adventure';
    if (this.el) this.el.classList.toggle('inc-interview', this.mode === 'interview');
    if (!silent) {
      this._loadMove({ keepValues: true });
      this._renderAll();
    }
    return this;
  }

  /* seconds <= 0 hides the bar entirely, which is the Adventure default: an
   * untimed correctness check is the better teacher, and the clock is the thing
   * Timed Practical Mode adds to measure with. */
  setTimer(seconds) {
    this._stopTimer();
    const s = Math.max(0, Number(seconds) || 0);
    this.timerTotal = s;
    this.timerLeft = s;
    if (!this.timerWrap) return this;
    this.timerWrap.style.display = s > 0 ? '' : 'none';
    if (s > 0) {
      this._paintTimer();
      this.timerHandle = setInterval(this._tickTimer, 250);
    }
    return this;
  }

  setReducedMotion(v) {
    this.reducedMotion = !!v;
    this._applyMotion();
    return this;
  }

  setBusy(v) {
    this.busy = !!v;
    if (this.castBtn) this.castBtn.disabled = this.busy;
    for (const h of this.holeNodes) if (h.input) h.input.disabled = this.busy;
    if (this.rawInput) this.rawInput.disabled = this.busy;
    return this;
  }

  setTurn(n) {
    this.turn = Math.max(1, Math.round(Number(n) || 1));
    if (this.turnTag) this.turnTag.textContent = `TURN ${this.turn}`;
    return this;
  }

  /* Longer fights mean HP moves many times per encounter; this is the cheap
   * path that does not rebuild the battlefield. */
  updateEnemy(id, patch) {
    const i = this.enemies.findIndex(e => String(e.id) === String(id));
    if (i < 0) return this;
    this.enemies[i] = Object.assign({}, this.enemies[i], patch || {});
    this._renderEnemies();
    return this;
  }

  setEnemyHp(id, hp, hpMax) {
    const patch = { hp };
    if (hpMax !== undefined) patch.hp_max = hpMax;
    if (Number(hp) <= 0) patch.dead = true;
    return this.updateEnemy(id, patch);
  }

  /* ------------------------------------------------------ moves */

  selectMove(which) {
    let i = -1;
    if (typeof which === 'number') i = which;
    else i = this.moves.findIndex(m => m.id === which || m.name === which);
    if (i < 0 || i >= this.moves.length) return this;
    if (this.moves[i].locked) {
      this._say('locked', 'NOT YET LEARNED',
        'That incantation is not in your book yet.', '');
      return this;
    }
    const changed = i !== this.moveIndex;
    this.moveIndex = i;
    this._loadMove({ keepValues: false });
    this._renderMoveset();
    this._renderTier();
    this._renderLine();
    this._renderTeach(this.moves[i]);
    this.focus();
    if (changed && this.onSelectMove) this.onSelectMove(this.moves[i]);
    this._sfx('select');
    return this;
  }

  get move() {
    return this.moveIndex >= 0 ? this.moves[this.moveIndex] || null : null;
  }

  /* The rung this move is actually being cast at right now. */
  tierOf(move) {
    if (this.mode === 'interview') return this.interviewTier;
    const m = move || this.move;
    if (m && m.tier !== undefined && m.tier !== null) {
      return clamp(Math.round(Number(m.tier) || 0), TIER.SHOWN, TIER.NAME);
    }
    return this.defaultTier;
  }

  _firstUsableMove() {
    const i = this.moves.findIndex(m => !m.locked);
    return i >= 0 ? i : (this.moves.length ? 0 : -1);
  }

  /* ------------------------------------------------------ the line */

  _loadMove({ keepValues }) {
    const m = this.move;
    this.holeParts = m ? parseTemplate(m.template) : [];
    const holes = m ? holeCount(m.template) : 0;
    const before = keepValues ? this.holeValues.slice() : [];
    this.holeValues = [];
    for (let i = 0; i < holes; i++) this.holeValues.push(before[i] || '');
    if (!keepValues) this.rawValue = '';
    this.focusHole = 0;

    /* Tier 0 hands back every blank but one, so the player meets the idea in a
     * line that is otherwise complete. It degrades to tier 1 rather than
     * failing if the server sent no scaffold fills — the ramp may be missing,
     * the fight may never be. */
    const tier = this.tierOf(m);
    this.scaffoldFill = null;
    if (tier === TIER.SHOWN && m && Array.isArray(m.prefill) && m.prefill.length) {
      this.scaffoldFill = m.prefill;
      const open = (m.focus_hole === undefined || m.focus_hole === null)
        ? Math.max(0, holes - 1) : clamp(m.focus_hole, 0, Math.max(0, holes - 1));
      this.openHole = open;
      for (let i = 0; i < holes; i++) {
        if (i !== open) this.holeValues[i] = String(m.prefill[i] || '');
      }
      this.focusHole = open;
    } else {
      this.openHole = -1;
    }
  }

  _renderLine() {
    if (!this.line) return;
    const m = this.move;
    this.line.innerHTML = '';
    this.holeNodes = [];
    this.rawInput = null;

    if (!m) {
      this.moveTitle.textContent = '';
      this.line.appendChild(node('span', 'inc-empty',
        'No incantation equipped. There is nothing to cast.'));
      return;
    }

    const tier = this.tierOf(m);
    this.moveTitle.innerHTML = '';
    this.moveTitle.appendChild(node('span', 'inc-mtname', m.name));
    this.moveTitle.appendChild(node('span', 'inc-mttier', TIER_META[tier].label));
    this.line.setAttribute('aria-label',
      `incantation ${m.name}, ${TIER_META[tier].label.toLowerCase()}`);

    if (tier === TIER.NAME) { this._renderRawLine(m); return; }

    for (const part of this.holeParts) {
      if (part.type === 'text') {
        const span = node('span', 'inc-lit');
        span.innerHTML = tier >= TIER.SHAPE ? shapeOf(part.text) : paint(part.text);
        this.line.appendChild(span);
      } else {
        /* part.index, not a running count: a repeated name draws a second box
         * onto the SAME slot, and the two mirror each other as you type. */
        this.line.appendChild(this._buildHole(part.index, part));
      }
    }
    this._syncAllHoles();
  }

  _buildHole(index, part) {
    const locked = this.openHole >= 0 && index !== this.openHole;
    const wrap = node('span', 'inc-hole' + (locked ? ' is-given' : ''));
    const ghost = node('span', 'inc-ghost');
    ghost.setAttribute('aria-hidden', 'true');
    const input = document.createElement('input');
    input.className = 'inc-input';
    input.type = 'text';
    input.spellcheck = false;
    input.autocomplete = 'off';
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('data-hole', String(index));
    input.setAttribute('aria-label',
      part.hint ? `blank ${index + 1}: ${part.hint}` : `blank ${index + 1}`);
    input.value = this.holeValues[index] || '';
    if (locked) {
      input.readOnly = true;
      input.tabIndex = -1;
      input.setAttribute('aria-readonly', 'true');
    }
    wrap.appendChild(ghost);
    wrap.appendChild(input);

    const entry = { wrap, ghost, input, locked, hint: part.hint, index };
    this.holeNodes.push(entry);

    this._on(input, 'input', () => {
      this.holeValues[index] = input.value;
      this._mirrorHole(index, input);
      // The blanks ARE the typing in this fight. audio.sfx('type') throttles
      // itself at 22ms and varies its own pitch, so a held key is a typewriter
      // and not a buzz; a paste is one click, which is the truth about a paste.
      this._sfx('type');
    });
    this._on(input, 'focus', () => {
      this.focusHole = index;
      this._markFocus();
    });
    this._on(input, 'keydown', (e) => this._onHoleKey(e, index));
    return wrap;
  }

  /* Tier 3 is one field holding the whole line, highlighted the same way, so
   * the last rung still reads as Python and not as a text box. */
  _renderRawLine(m) {
    const wrap = node('span', 'inc-hole inc-raw');
    const ghost = node('span', 'inc-ghost');
    ghost.setAttribute('aria-hidden', 'true');
    const input = document.createElement('input');
    input.className = 'inc-input';
    input.type = 'text';
    input.spellcheck = false;
    input.autocomplete = 'off';
    input.setAttribute('aria-label', `write the ${m.name} incantation in full`);
    input.value = this.rawValue || '';
    wrap.appendChild(ghost);
    wrap.appendChild(input);
    this.line.appendChild(wrap);

    const entry = { wrap, ghost, input, locked: false, hint: '', index: 0, raw: true };
    this.holeNodes.push(entry);
    this.rawInput = input;

    this._on(input, 'input', () => {
      this.rawValue = input.value;
      this._syncHole(entry);
      this._sfx('type');
    });
    this._on(input, 'focus', () => { this.focusHole = 0; this._markFocus(); });
    this._on(input, 'keydown', (e) => this._onHoleKey(e, 0));
    this._syncHole(entry);
  }

  /* One slot, possibly several boxes. Typing in any of them writes the slot and
   * repaints the rest, so a repeated variable stays visibly one variable. */
  _mirrorHole(index, source) {
    const value = this.holeValues[index] || '';
    for (const entry of this.holeNodes) {
      if (entry.raw || entry.index !== index) continue;
      if (entry.input !== source && entry.input.value !== value) {
        entry.input.value = value;
      }
      this._syncHole(entry);
    }
  }

  _syncAllHoles() {
    for (const entry of this.holeNodes) this._syncHole(entry);
    this._markFocus();
  }

  /* The ghost layer under each input is what the player actually sees: the
   * input's own text is transparent, so the value is syntax-highlighted while
   * it is being typed rather than after. */
  _syncHole(entry) {
    const value = entry.raw ? this.rawValue : (this.holeValues[entry.index] || '');
    if (!value) {
      const placeholder = entry.raw
        ? (this.move ? `${this.move.name.toLowerCase()} …` : '…')
        : (entry.hint || HOLE_GLYPH);
      entry.ghost.innerHTML = `<span class="inc-placeholder">${esc(placeholder)}</span>`;
      entry.wrap.classList.remove('is-bound');
      return;
    }
    const bound = !entry.raw && this._enemyByName(value);
    entry.ghost.innerHTML = bound
      ? `<span class="inc-bound-name">${esc(value)}</span>`
      : paint(value);
    entry.wrap.classList.toggle('is-bound', !!bound);
  }

  _markFocus() {
    for (const h of this.holeNodes) {
      const on = (h.raw ? 0 : h.index) === this.focusHole;
      h.wrap.classList.toggle('is-focus', on && !h.locked);
    }
  }

  _focusHoleAt(index, { select = false } = {}) {
    const usable = this.holeNodes.filter(h => !h.locked);
    if (!usable.length) return;
    const target = usable.find(h => (h.raw ? 0 : h.index) === index) || usable[0];
    this.focusHole = target.raw ? 0 : target.index;
    if (target.input && target.input.focus) target.input.focus();
    if (select && target.input && target.input.select) target.input.select();
    this._markFocus();
  }

  _stepHole(delta) {
    const usable = this.holeNodes.filter(h => !h.locked);
    if (usable.length < 2) return;
    let at = usable.findIndex(h => (h.raw ? 0 : h.index) === this.focusHole);
    if (at < 0) at = 0;
    const next = (at + delta + usable.length) % usable.length;
    this._focusHoleAt(usable[next].raw ? 0 : usable[next].index, { select: true });
  }

  focus() {
    const first = this.holeNodes.find(h => !h.locked);
    if (first && first.input && first.input.focus) {
      first.input.focus();
      this.focusHole = first.raw ? 0 : first.index;
      this._markFocus();
    } else if (this.castBtn && this.castBtn.focus) {
      this.castBtn.focus();
    }
    return this;
  }

  /* ------------------------------------------------------ enemies */

  _enemyByName(value) {
    const v = String(value || '').trim();
    if (!v) return null;
    return this.enemies.find(e => String(e.name) === v) || null;
  }

  /* A mouse is a shortcut for the impatient, never the intended path: clicking
   * a name types it for you, and nothing else about the cast changes. */
  insertEnemy(which) {
    const enemy = typeof which === 'number' ? this.enemies[which] : this._enemyByName(which);
    if (!enemy) return this;
    const entry = this.holeNodes.find(h => !h.locked
      && (h.raw ? 0 : h.index) === this.focusHole)
      || this.holeNodes.find(h => !h.locked);
    if (!entry) return this;
    if (entry.raw) {
      const at = typeof entry.input.selectionStart === 'number'
        ? entry.input.selectionStart : this.rawValue.length;
      this.rawValue = this.rawValue.slice(0, at) + enemy.name + this.rawValue.slice(at);
      entry.input.value = this.rawValue;
      if (entry.input.setSelectionRange) {
        const pos = at + enemy.name.length;
        entry.input.setSelectionRange(pos, pos);
      }
      this._syncHole(entry);
      if (entry.input.focus) entry.input.focus();
      return this;
    }
    this.holeValues[entry.index] = enemy.name;
    entry.input.value = enemy.name;
    this._mirrorHole(entry.index, entry.input);
    const nextEmpty = this.holeNodes.find(h => !h.locked
      && !(this.holeValues[h.index] || '').trim());
    if (nextEmpty) this._focusHoleAt(nextEmpty.index);
    else if (entry.input.focus) entry.input.focus();
    this._sfx('type');
    return this;
  }

  /* ------------------------------------------------------ casting */

  /* Enter casts. The only thing refused here is a line with nothing in it at
   * all, because that is a misclick and not an attempt — everything else goes
   * to the grader, including a line that is obviously wrong. Refusing a wrong
   * line would be the UI grading, and it would remove the very cost that makes
   * the next attempt effortful. */
  cast({ timeout = false } = {}) {
    if (this.destroyed || this.busy) return null;
    const m = this.move;
    if (!m) {
      this._say('locked', 'NOTHING EQUIPPED',
        'Choose an incantation from the bar below first.', '');
      return null;
    }
    const tier = this.tierOf(m);
    const raw = tier === TIER.NAME;
    const values = raw ? [] : this.holeValues.slice();
    const written = raw ? this.rawValue.trim() : values.join('').trim();

    if (!written && !timeout) {
      this._say('empty', 'THE LINE IS EMPTY',
        'Nothing to cast. Read the names in front of you and fill the blanks.',
        '');
      this.focus();
      return null;
    }

    const line = raw ? this.rawValue : assemble(m.template, values);
    const payload = {
      encounter_id: this.encounter ? this.encounter.id : null,
      move_id: m.id,
      move_name: m.name,
      template: m.template,
      tier,
      mode: this.mode,
      turn: this.turn,
      holes: values,
      raw: raw ? this.rawValue : null,
      line,
      /* A convenience for the caller, not a verdict: which enemy each hole
       * names, by exact match. Anything unmatched is null and the server
       * decides what that means. */
      bound: values.map(v => {
        const e = this._enemyByName(v);
        return e ? e.id : null;
      }),
      timeout: !!timeout,
      seconds: this.startedAt ? (Date.now() - this.startedAt) / 1000 : 0,
    };

    this.setBusy(true);
    this._say('casting', 'CASTING', line, '');
    this._sfx('cast');

    let result = null;
    if (this.onCast) result = this.onCast(payload, this);
    if (result && typeof result.then === 'function') {
      result.then((r) => this.resolveCast(r)).catch((err) => this.resolveCast({
        ok: false, layer: CAST_LAYER.SYNTAX,
        detail: (err && err.message) || 'the cast could not be sent',
      }));
      return payload;
    }
    if (result) this.resolveCast(result);
    /* No result and no promise: the caller will call resolveCast when the
     * server answers. The UI stays busy until then, which is honest. */
    return payload;
  }

  /* result = { ok, damage, enemy_id, effect, line, enemies, turn }
   *        | { ok:false, layer, detail, teach, hole, turn } */
  resolveCast(result) {
    if (this.destroyed || !this.el) return this;
    const r = result || {};
    this.setBusy(false);

    /* WHAT DIED ON THIS CAST, before the list is replaced.
     *
     * A name going down is not the same event as a line landing, and it was
     * silent: `hit` played over both, so clearing the last name on a field
     * sounded exactly like grazing the first. The diff is taken here because
     * this is the only moment both lists exist — after the swap the old one is
     * gone, and main.js sees the field only through this object. */
    const fell = [];
    if (Array.isArray(r.enemies)) {
      const before = new Map(this.enemies.map(e => [String(e.id), !!e.dead]));
      for (const e of r.enemies) {
        const was = before.get(String(e.id));
        if (e.dead && was === false) fell.push(e);
      }
      this.enemies = r.enemies.slice();
      this._renderEnemies();
    } else if (r.enemy_id !== undefined && r.hp !== undefined) {
      const was = this.enemies.find(e => String(e.id) === String(r.enemy_id));
      if (was && !was.dead && r.hp <= 0) fell.push(was);
      this.setEnemyHp(r.enemy_id, r.hp, r.hp_max);
    }

    if (r.ok) {
      const m = this.move;
      const bits = [];
      if (r.damage !== undefined) bits.push(`${r.damage} damage`);
      if (r.effect) bits.push(r.effect);
      this._say('good', 'IT LANDS', r.line || bits.join(' · ') || 'The line holds.',
        r.teach && this.mode !== 'interview' ? r.teach : '');
      this._pushLog(true, m ? m.name : '', r.line || '', bits.join(' · '));
      this._flash('good');
      this._sfx('hit');
      this._elementLands();
      /* The move stays selected on a hit. Repetition inside one fight is how
       * the pattern becomes fluent; the SRS across days is what makes it stick. */
      this._resetLine();
    } else {
      const layer = LAYER_META[r.layer] ? r.layer : CAST_LAYER.SEMANTICS;
      const meta = LAYER_META[layer];
      const detail = r.detail || meta.title;
      /* Adventure explains the layer. Timed Practical names it and stops — the run is
       * measuring, and a teaching line is help. */
      const teach = this.mode === 'interview' ? '' : (r.teach || meta.teach);
      this._say(`bad layer-${layer}`, `THE CAST FAILS · ${meta.label}`, detail, teach,
        'The turn passes.');
      this._pushLog(false, this.move ? this.move.name : '', r.line || '', meta.label);
      this._flash('bad');
      /* SEMANTICS is a line that parsed and bound and still did the wrong
       * thing — a whiff. SYNTAX and BINDING are the spell coming apart in the
       * hand, which is what `cast_fail` is for; it was authored as cast_ok's
       * counterpart and had no caller at all. */
      this._sfx(layer === CAST_LAYER.SEMANTICS ? 'miss' : 'cast_fail');
      if (typeof r.hole === 'number') this._focusHoleAt(r.hole, { select: true });
      else this.focus();
    }

    /* After the hit, not instead of it: the blow lands and THEN the thing
     * stops standing. Staggered because two names falling on one line are two
     * events, and audio.sfx has no throttle on `defeat`. */
    fell.forEach((e, i) => {
      if (i === 0) this._sfx('defeat');
      else setTimeout(() => { if (!this.destroyed) this._sfx('defeat'); }, i * 210);
    });

    if (r.turn !== undefined) this.setTurn(r.turn);
    else this.setTurn(this.turn + 1);
    if (r.tier !== undefined && this.move) this.setTier(r.tier, this.move.id);
    if (this.timerTotal > 0) this.setTimer(this.timerTotal);
    return this;
  }

  _resetLine() {
    this.holeValues = this.holeValues.map(() => '');
    this.rawValue = '';
    this._loadMove({ keepValues: false });
    this._renderLine();
    this.focus();
  }

  /* ------------------------------------------------------ rendering */

  _renderAll() {
    if (!this.el) return;
    this._renderEnemies();
    this._renderTier();
    this._renderLine();
    this._renderMoveset();
    this._renderTeach(this.move);
    this._renderLog();
    this.setTurn(this.turn);
  }

  _renderEnemies() {
    if (!this.enemyBar) return;
    this.enemyBar.innerHTML = '';
    if (!this.enemies.length) {
      this.enemyBar.appendChild(node('div', 'inc-empty', 'The field is clear.'));
      return;
    }
    this.enemies.forEach((enemy, i) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'inc-enemy'
        + (enemy.dead ? ' is-dead' : '')
        + (this._nameInUse(enemy.name) ? ' is-named' : '');
      card.setAttribute('role', 'listitem');
      card.setAttribute('aria-label',
        `${enemy.name}, ${enemy.type || 'value'}${enemy.value !== undefined
          ? `, currently ${enemy.value}` : ''}. Press to type this name.`);

      if (enemy.title) card.appendChild(node('span', 'inc-en-title', enemy.title));
      const nameRow = node('span', 'inc-en-row');
      nameRow.appendChild(node('code', 'inc-en-name', enemy.name));
      nameRow.appendChild(node('span', 'inc-en-type', enemy.type || '?'));
      card.appendChild(nameRow);

      const val = node('span', 'inc-en-value');
      val.textContent = enemy.value === undefined || enemy.value === null
        ? '—' : String(enemy.value);
      card.appendChild(val);

      if (enemy.hp_max) {
        const bar = node('span', 'bar hp inc-en-bar');
        const fill = node('i', '');
        const pct = clamp((Number(enemy.hp) || 0) / Number(enemy.hp_max) * 100, 0, 100);
        fill.style.width = `${pct}%`;
        bar.appendChild(fill);
        card.appendChild(bar);
        card.appendChild(node('span', 'inc-en-hp', `${enemy.hp}/${enemy.hp_max}`));
      }
      /* The note says what the structure is for, never which incantation to
       * use on it. That discrimination is the whole exercise. */
      if (enemy.note && this.mode !== 'interview') {
        card.appendChild(node('span', 'inc-en-note', enemy.note));
      }
      this._on(card, 'click', () => this.insertEnemy(i));
      this.enemyBar.appendChild(card);
    });
  }

  _nameInUse(name) {
    const n = String(name);
    return this.holeValues.some(v => String(v).trim() === n)
      || (this.rawValue || '').split(/[^A-Za-z0-9_]+/).includes(n);
  }

  /* The fade has to be legible or it is not a reward. Four rungs, the current
   * one lit, the ones already climbed struck through, and a plain sentence
   * saying what has stopped being shown. */
  _renderTier() {
    if (!this.tierBar) return;
    const m = this.move;
    const tier = this.tierOf(m);
    this.el.setAttribute('data-tier', String(tier));
    this.tierBar.innerHTML = '';

    const rungs = node('span', 'inc-rungs');
    TIER_META.forEach((meta, i) => {
      const r = node('span', 'inc-rung'
        + (i === tier ? ' is-now' : '')
        + (i < tier ? ' is-past' : ''), meta.label);
      r.setAttribute('title', meta.blurb);
      rungs.appendChild(r);
    });
    this.tierBar.appendChild(node('span', 'inc-tierlabel', 'SCAFFOLD'));
    this.tierBar.appendChild(rungs);

    const blurb = node('span', 'inc-tierblurb', TIER_META[tier].blurb);
    this.tierBar.appendChild(blurb);

    if (this.mode === 'interview') {
      this.tierBar.appendChild(node('span', 'tag red', 'MEASURED'));
    } else if (m && m.mastery !== undefined && m.mastery !== null) {
      const pct = clamp(Math.round(Number(m.mastery) * 100), 0, 100);
      this.tierBar.appendChild(node('span', 'inc-mastery', `${pct}% recalled unaided`));
    }
  }

  _renderMoveset() {
    if (!this.moveBar) return;
    this.moveBar.innerHTML = '';
    if (!this.moves.length) {
      this.moveBar.appendChild(node('div', 'inc-empty', 'No incantations learned yet.'));
      return;
    }
    this.moves.forEach((m, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'inc-move'
        + (i === this.moveIndex ? ' is-on' : '')
        + (m.locked ? ' is-locked' : '');
      b.setAttribute('aria-pressed', i === this.moveIndex ? 'true' : 'false');
      if (m.locked) b.setAttribute('aria-disabled', 'true');

      const key = node('span', 'inc-mv-key', i < MAX_HOTKEYS ? String(i + 1) : '·');
      const name = node('span', 'inc-mv-name', m.name);
      b.appendChild(key);
      b.appendChild(name);

      const tier = this.tierOf(m);
      const pips = node('span', 'inc-mv-pips',
        '▮'.repeat(tier + 1) + '▯'.repeat(TIER.NAME - tier));
      pips.setAttribute('title', `scaffold rung: ${TIER_META[tier].label}`);
      b.appendChild(pips);

      /* The template preview disappears at the rungs where remembering it is
       * the point. Showing it on the button would undo the fade. */
      if (tier <= TIER.BLANKS && this.mode !== 'interview') {
        b.appendChild(node('span', 'inc-mv-tmpl', m.template || ''));
      }
      if (m.teach) b.setAttribute('title', m.teach);

      this._on(b, 'click', () => this.selectMove(i));
      this._on(b, 'mouseenter', () => this._renderTeach(m));
      this._on(b, 'focus', () => this._renderTeach(m));
      this._on(b, 'mouseleave', () => this._renderTeach(this.move));
      this.moveBar.appendChild(b);
    });
  }

  /* Hover text alone is not accessible, so the note has a permanent home and
   * hover only changes which note is in it. */
  _renderTeach(m) {
    if (!this.teachBox) return;
    this.teachBox.innerHTML = '';
    if (this.mode === 'interview') {
      this.teachBox.appendChild(node('span', 'muted small',
        'Timed Practical Mode. No notes, no templates, no teaching lines.'));
      return;
    }
    if (!m) return;
    this.teachBox.appendChild(node('span', 'inc-teach-name', m.name));
    this.teachBox.appendChild(node('span', 'inc-teach-body',
      m.teach || 'No note recorded for this incantation.'));
  }

  _renderLog() {
    if (!this.logBox) return;
    this.logBox.innerHTML = '';
    for (const entry of this.log) {
      const row = node('div', 'inc-logrow ' + (entry.ok ? 'ok' : 'no'));
      row.appendChild(node('span', 'inc-logmark', entry.ok ? '✦' : '✕'));
      row.appendChild(node('span', 'inc-logname', entry.move));
      row.appendChild(node('code', 'inc-logline', entry.line));
      if (entry.tail) row.appendChild(node('span', 'inc-logtail', entry.tail));
      this.logBox.appendChild(row);
    }
  }

  _pushLog(ok, move, line, tail) {
    this.log.unshift({ ok, move, line, tail });
    if (this.log.length > LOG_LINES) this.log.length = LOG_LINES;
    this._renderLog();
  }

  _say(kind, title, detail, teach, tail) {
    if (!this.feedback) return;
    const [state, ...extra] = String(kind).split(' ');
    this.feedback.className = ['inc-feedback', `is-${state}`, ...extra].join(' ');
    this.feedback.innerHTML = '';
    this.feedback.appendChild(node('span', 'inc-fb-title', title));
    if (detail) this.feedback.appendChild(node('span', 'inc-fb-detail', detail));
    if (teach) this.feedback.appendChild(node('span', 'inc-fb-teach', teach));
    if (tail) this.feedback.appendChild(node('span', 'inc-fb-tail', tail));
  }

  _clearFeedback() {
    if (!this.feedback) return;
    this.feedback.className = 'inc-feedback';
    this.feedback.innerHTML = '';
  }

  _flash(kind) {
    if (!this.line || this.reducedMotion) return;
    this.line.classList.remove('flash-good', 'flash-bad');
    // force the class to re-apply on a repeat cast of the same outcome
    if (this._flashTimer) clearTimeout(this._flashTimer);
    this.line.classList.add(kind === 'good' ? 'flash-good' : 'flash-bad');
    this._flashTimer = setTimeout(() => {
      if (this.line) this.line.classList.remove('flash-good', 'flash-bad');
      this._flashTimer = 0;
    }, 420);
  }

  _applyMotion() {
    if (!this.el) return;
    this.el.classList.toggle('inc-still', this.reducedMotion);
    // Switching motion off mid-flash has to clear the flash that is already
    // running, or the setting appears not to have taken.
    if (this.reducedMotion && this.line) {
      if (this._flashTimer) { clearTimeout(this._flashTimer); this._flashTimer = 0; }
      this.line.classList.remove('flash-good', 'flash-bad');
    }
  }

  /* ONE LINE USED TO EAT THREE OF THE FOUR NAMES IN THIS FILE.
   *
   *     { cast: 'select', hit: 'hit', miss: 'error', select: 'select', type: <a
   *       name that no longer exists> }
   *
   * `cast` played the menu blip, `miss` played the refusal buzz and `type`
   * played a click borrowed from somewhere else — so a spell leaving the hand,
   * a whiff and a keystroke were three names for two sounds that belonged to
   * other events. Every one of those names now exists on its own in audio.js,
   * so there is no map left at all: a name asked for here is the name that
   * plays. Nothing here decides what a sound is; it decides which one is being
   * asked for.
   *
   * THE LAST THING THIS MAP ATE was `cast` itself. It was diverted to
   * castElement(this.element) and returned before audio.sfx() was reached, so
   * audio.js's `case 'cast'` could never fire from anywhere in the client.
   * They are not the same event and they do not sound alike — `cast` is the
   * THROW (0.26s, centroid 2545, tilt +1.00, everything in it opens) and
   * castElement is the ARRIVAL (0.19s, centroid 418, tilt -0.65). The throw
   * plays here, at cast time; the element lands in resolveCast()'s ok branch,
   * where the line actually holds. */
  _sfx(kind) {
    if (!this.audio) return;
    try {
      if (typeof this.audio.sfx !== 'function') return;
      this.audio.sfx(kind);
    } catch (e) { /* audio is never load-bearing */ }
  }

  /* The element arriving. Separate from _sfx() because it takes the element
   * rather than a name, and because it is a different moment in the turn. */
  _elementLands() {
    if (!this.audio || typeof this.audio.castElement !== 'function') return;
    try { this.audio.castElement(this.element); }
    catch (e) { /* audio is never load-bearing */ }
  }

  /* ------------------------------------------------------ timer */

  _tickTimer() {
    // A tick that arrives after the clock has already stopped is not a second
    // timeout. Without this, one expiry can waste two turns.
    if (!this.timerHandle) return;
    this.timerLeft = Math.max(0, this.timerLeft - 0.25);
    this._paintTimer();
    if (this.timerLeft <= 0) {
      this._stopTimer();
      if (this.onTimeout) this.onTimeout(this);
      if (this.castOnTimeout && !this.busy) this.cast({ timeout: true });
    }
  }

  _paintTimer() {
    if (!this.timerFill) return;
    const pct = this.timerTotal > 0 ? (this.timerLeft / this.timerTotal) * 100 : 0;
    this.timerFill.style.width = `${clamp(pct, 0, 100)}%`;
    this.timerText.textContent = fmtClock(this.timerLeft);
    this.timerBar.classList.toggle('is-low', pct < 25);
  }

  _stopTimer() {
    if (this.timerHandle) { clearInterval(this.timerHandle); this.timerHandle = 0; }
  }

  /* ------------------------------------------------------ keyboard */

  _onHoleKey(e, index) {
    const input = e.target;
    if (e.key === 'Enter') { e.preventDefault(); this.cast(); return; }
    if (e.key === 'Escape') {
      e.preventDefault();
      const first = this.moveBar && this.moveBar.firstChild;
      if (first && first.focus) first.focus();
      else if (this.castBtn && this.castBtn.focus) this.castBtn.focus();
      return;
    }
    if (e.key === 'Tab') {
      const usable = this.holeNodes.filter(h => !h.locked);
      if (usable.length < 2) return;          // let focus leave the widget
      e.preventDefault();
      this._stepHole(e.shiftKey ? -1 : 1);
      return;
    }
    if (e.key === 'ArrowLeft' && this._atStart(input)) {
      e.preventDefault(); this._stepHole(-1); return;
    }
    if (e.key === 'ArrowRight' && this._atEnd(input)) {
      e.preventDefault(); this._stepHole(1); return;
    }
    /* Alt + up/down walks the names on the battlefield into this hole, so the
     * keyboard has the same shortcut the mouse does. */
    if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && e.altKey) {
      e.preventDefault();
      this._cycleName(index, e.key === 'ArrowDown' ? 1 : -1);
    }
  }

  _atStart(input) {
    return typeof input.selectionStart !== 'number'
      || (input.selectionStart === 0 && input.selectionEnd === 0);
  }

  _atEnd(input) {
    const len = (input.value || '').length;
    return typeof input.selectionStart !== 'number'
      || (input.selectionStart === len && input.selectionEnd === len);
  }

  _cycleName(index, delta) {
    const live = this.enemies.filter(e => !e.dead);
    if (!live.length) return;
    const current = (this.holeValues[index] || '').trim();
    let at = live.findIndex(e => e.name === current);
    at = (at + delta + live.length * 2) % live.length;
    const entry = this.holeNodes.find(h => h.index === index && !h.locked);
    if (!entry) return;
    this.holeValues[index] = live[at].name;
    entry.input.value = live[at].name;
    this._mirrorHole(index, entry.input);
    this._renderEnemies();
  }

  _onRootKey(e) {
    /* Bare digits pick a move whenever the player is not typing into a hole.
     * While typing, Escape first — modifier+digit is a browser shortcut on too
     * many platforms to be the documented path. */
    const tag = (e.target && e.target.tagName) || '';
    const typing = tag === 'INPUT' || tag === 'TEXTAREA';
    if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && /^[1-8]$/.test(e.key)) {
      e.preventDefault();
      this.selectMove(Number(e.key) - 1);
      return;
    }
    if (!typing && e.key === 'Enter' && e.target === this.el) {
      e.preventDefault();
      this.cast();
    }
  }

  /* Alt+digit works from anywhere in the battle screen when the browser lets it
   * through. It is a convenience layered on top of the documented path, never
   * the only way to reach a move. */
  _onDocKey(e) {
    if (!this.el || !e.altKey || e.ctrlKey || e.metaKey) return;
    if (!/^[1-8]$/.test(e.key)) return;
    if (!this._isVisible()) return;
    e.preventDefault();
    this.selectMove(Number(e.key) - 1);
  }

  _isVisible() {
    if (!this.el) return false;
    if (typeof this.el.getClientRects !== 'function') return true;   // stub/test
    return this.el.getClientRects().length > 0;
  }

  /* ------------------------------------------------------ introspection */

  /* A plain snapshot, for tests and for a caller that wants to persist a
   * half-written line across a screen change. */
  getState() {
    const m = this.move;
    return {
      mode: this.mode,
      turn: this.turn,
      busy: this.busy,
      move_id: m ? m.id : null,
      tier: this.tierOf(m),
      tier_label: TIER_META[this.tierOf(m)].label,
      holes: this.holeValues.slice(),
      hole_names: m ? holeNames(m.template) : [],
      raw: this.rawValue,
      line: m ? (this.tierOf(m) === TIER.NAME
        ? this.rawValue : assemble(m.template, this.holeValues)) : '',
      focus_hole: this.focusHole,
      enemies: this.enemies.map(e => ({ id: e.id, name: e.name, hp: e.hp })),
      timer_left: this.timerLeft,
      reduced_motion: this.reducedMotion,
    };
  }

  get value() {
    const m = this.move;
    if (!m) return '';
    return this.tierOf(m) === TIER.NAME
      ? this.rawValue : assemble(m.template, this.holeValues);
  }

  /* ------------------------------------------------------ static */

  static _prefersReducedMotion() {
    try {
      if (typeof document !== 'undefined' && document.body
          && document.body.classList
          && document.body.classList.contains('reduced-motion')) return true;
      if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
        return !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) { /* a missing matchMedia is not a reason to fail to mount */ }
    return false;
  }

  /* Styles itself, the way fx.js does, so index.html and game.css never have to
   * know this screen exists. Every size is in the --scale unit game.css already
   * uses, so the player's text-scale setting moves this screen with the rest. */
  static _ensureStyle() {
    IncantationUI._refs = (IncantationUI._refs || 0) + 1;
    if (document.getElementById('incant-ui-style')) return;
    const s = document.createElement('style');
    s.id = 'incant-ui-style';
    s.textContent = INCANT_CSS;
    document.head.appendChild(s);
  }

  static _releaseStyle() {
    IncantationUI._refs = Math.max(0, (IncantationUI._refs || 1) - 1);
    if (IncantationUI._refs > 0) return;
    const s = document.getElementById('incant-ui-style');
    if (s && s.parentNode) s.parentNode.removeChild(s);
  }

  /* Internal: track every listener so destroy() leaves nothing behind. */
  _on(target, type, fn) {
    if (!target || !target.addEventListener) return;
    target.addEventListener(type, fn);
    this._listeners.push([target, type, fn]);
  }
}

const INCANT_CSS = `
.inc-root {
  display: flex; flex-direction: column; gap: 10px; height: 100%;
  padding: 12px 14px; overflow-y: auto; background: var(--bg);
  font-family: 'Courier New', ui-monospace, monospace;
}
.inc-root .inc-empty {
  color: var(--ink-faint); font-size: calc(12px * var(--scale)); font-style: italic;
}

/* --- the battlefield: the answer key, always on screen --- */
.inc-enemies { display: flex; gap: 8px; flex-wrap: wrap; align-items: stretch; }
.inc-enemy {
  flex: 1 1 150px; max-width: 240px; text-align: left; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; padding: 8px 9px;
  background: var(--panel-2); border: 2px solid var(--line);
  box-shadow: 0 3px 0 var(--shadow); color: var(--ink);
  font-family: inherit; font-size: calc(12px * var(--scale));
}
.inc-enemy:hover { border-color: var(--gold); background: var(--panel-3); }
.inc-enemy.is-named { border-color: var(--violet); }
.inc-enemy.is-dead { opacity: .35; }
.inc-en-title {
  font-family: 'Press Start 2P', monospace; font-size: calc(7px * var(--scale));
  color: var(--ink-faint); letter-spacing: .5px;
}
.inc-en-row { display: flex; align-items: baseline; gap: 8px; }
.inc-en-name {
  font-size: calc(17px * var(--scale)); color: var(--gold-hi);
  letter-spacing: .5px; font-family: inherit;
}
.inc-en-type {
  font-size: calc(10px * var(--scale)); color: var(--blue);
  border: 1px solid var(--line-hi); padding: 1px 5px;
}
.inc-en-value {
  color: var(--green); font-size: calc(12px * var(--scale));
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.inc-en-bar { display: block; height: 8px; }
.inc-en-hp { font-size: calc(10px * var(--scale)); color: var(--ink-faint); }
.inc-en-note {
  font-size: calc(11px * var(--scale)); color: var(--ink-dim); line-height: 1.5;
}

/* --- the incantation line --- */
.inc-stage {
  display: flex; flex-direction: column; gap: 8px; padding: 12px 14px;
  background: var(--panel); border: 3px solid var(--line);
  box-shadow: 0 3px 0 var(--shadow), inset 0 0 0 1px #000;
}
.inc-tier { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.inc-tierlabel {
  font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: var(--ink-faint);
}
.inc-rungs { display: flex; gap: 4px; }
.inc-rung {
  font-family: 'Press Start 2P', monospace; font-size: calc(7px * var(--scale));
  padding: 3px 6px; border: 1px solid var(--line); color: var(--ink-faint);
  background: #0d0b16;
}
.inc-rung.is-past { color: var(--line-hi); text-decoration: line-through; }
.inc-rung.is-now { color: var(--gold-hi); border-color: var(--gold); background: #2b2340; }
.inc-tierblurb { font-size: calc(11px * var(--scale)); color: var(--ink-dim); }
.inc-mastery { margin-left: auto; font-size: calc(11px * var(--scale)); color: var(--violet); }

.inc-movetitle { display: flex; align-items: baseline; gap: 10px; }
.inc-mtname {
  font-family: 'Press Start 2P', monospace; font-size: calc(11px * var(--scale));
  color: var(--violet);
}
.inc-mttier { font-size: calc(10px * var(--scale)); color: var(--ink-faint); }

.inc-line {
  background: #0d0b16; border: 2px solid var(--line); padding: 14px 14px;
  font-family: 'Courier New', ui-monospace, monospace;
  font-size: calc(19px * var(--scale)); line-height: 1.7;
  white-space: pre-wrap; word-break: break-word; min-height: calc(52px * var(--scale));
}
/* The template itself is grey ghost text. What the player writes is not. */
.inc-lit { color: #5c5878; }
.inc-lit .tok-keyword, .inc-lit .tok-builtin, .inc-lit .tok-op,
.inc-lit .tok-number, .inc-lit .tok-string, .inc-lit .tok-call {
  color: #6f6a92;
}
.inc-shape { color: #3f3b58; letter-spacing: 1px; }
.inc-hole {
  position: relative; display: inline-block; vertical-align: baseline;
  min-width: calc(4ch); border-bottom: 2px solid var(--line-hi);
  margin: 0 2px; padding: 0 2px;
}
.inc-hole.inc-raw { display: block; min-width: 100%; }
.inc-hole.is-focus { border-bottom-color: var(--gold-hi); background: #1a1630; }
.inc-hole.is-given { border-bottom-style: dotted; opacity: .78; }
.inc-hole.is-bound { border-bottom-color: var(--violet); }
.inc-ghost { white-space: pre; display: inline-block; min-width: 1ch; color: var(--ink); }
.inc-placeholder { color: #4a4665; }
.inc-bound-name { color: var(--gold-hi); }
.inc-input {
  position: absolute; inset: 0; width: 100%; height: 100%;
  background: transparent; color: transparent; caret-color: var(--gold-hi);
  border: 0; outline: none; padding: 0 2px; margin: 0;
  font: inherit; letter-spacing: inherit;
}
.inc-input::placeholder { color: transparent; }
.inc-input::selection { background: rgba(168,154,255,.35); color: transparent; }
.inc-hole.is-focus .inc-input { outline: none; }
.inc-root:not(.inc-still) .inc-line.flash-good { animation: incgood .42s steps(3); }
.inc-root:not(.inc-still) .inc-line.flash-bad { animation: incbad .42s steps(3); }
@keyframes incgood { 50% { border-color: var(--green); background: #10210e; } }
@keyframes incbad { 50% { border-color: var(--red); background: #24101a; } }

/* --- timer: absent in Adventure, present in Timed Practical --- */
.inc-timerwrap { display: flex; align-items: center; gap: 8px; }
.inc-timerbar {
  flex: 1; height: 10px; background: #0d0b16; border: 2px solid var(--line);
}
.inc-timerbar > i { display: block; height: 100%; background: var(--blue); }
.inc-root:not(.inc-still) .inc-timerbar > i { transition: width .25s linear; }
.inc-timerbar.is-low > i { background: var(--red); }
.inc-timertext {
  font-family: 'Press Start 2P', monospace; font-size: calc(10px * var(--scale));
  color: var(--orange);
}

/* --- feedback: never a bare "wrong" --- */
.inc-feedback { display: flex; flex-direction: column; gap: 4px; min-height: calc(30px * var(--scale)); }
.inc-fb-title {
  font-family: 'Press Start 2P', monospace; font-size: calc(10px * var(--scale));
  color: var(--ink-dim);
}
.inc-fb-detail { font-size: calc(13px * var(--scale)); color: var(--ink); line-height: 1.6; }
.inc-fb-teach { font-size: calc(12px * var(--scale)); color: var(--ink-dim); line-height: 1.6;
  border-left: 3px solid var(--violet); padding-left: 9px; }
.inc-fb-tail { font-size: calc(11px * var(--scale)); color: var(--ink-faint); }
.inc-feedback.is-good .inc-fb-title { color: var(--green); }
.inc-feedback.is-bad .inc-fb-title { color: var(--red); }
.inc-feedback.layer-binding .inc-fb-title { color: var(--gold); }
.inc-feedback.layer-semantics .inc-fb-title { color: var(--violet); }
.inc-feedback.is-empty .inc-fb-title, .inc-feedback.is-locked .inc-fb-title { color: var(--orange); }

.inc-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.inc-turn {
  font-family: 'Press Start 2P', monospace; font-size: calc(9px * var(--scale));
  color: var(--ink-faint);
}
.inc-keys { margin-left: auto; font-size: calc(11px * var(--scale)); color: var(--ink-faint); }
.inc-keys b {
  color: var(--gold); font-weight: normal; border: 1px solid var(--line-hi);
  padding: 0 4px; background: #0d0b16;
}

.inc-log { display: flex; flex-direction: column; gap: 3px; }
.inc-logrow {
  display: flex; gap: 8px; align-items: baseline;
  font-size: calc(11px * var(--scale)); color: var(--ink-faint);
}
.inc-logrow.ok .inc-logmark { color: var(--green); }
.inc-logrow.no .inc-logmark { color: var(--red); }
.inc-logname { color: var(--violet); }
.inc-logline { color: var(--ink-dim); }

/* --- the moveset bar --- */
.inc-moveset { display: flex; gap: 6px; flex-wrap: wrap; }
.inc-move {
  flex: 1 1 140px; display: flex; flex-direction: column; gap: 4px; cursor: pointer;
  text-align: left; padding: 8px 9px; color: var(--ink);
  background: var(--panel-2); border: 2px solid var(--line-hi);
  box-shadow: 0 3px 0 var(--shadow); font-family: inherit;
}
.inc-move:hover { background: var(--panel-3); }
.inc-move.is-on { background: #3b2f66; border-color: var(--violet); }
.inc-move.is-locked { opacity: .38; cursor: not-allowed; }
.inc-mv-key {
  font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: var(--ink-faint);
}
.inc-mv-name {
  font-family: 'Press Start 2P', monospace; font-size: calc(10px * var(--scale));
  color: var(--gold);
}
.inc-move.is-on .inc-mv-name { color: var(--gold-hi); }
.inc-mv-pips { font-size: calc(10px * var(--scale)); color: var(--violet); letter-spacing: 1px; }
.inc-mv-tmpl {
  font-size: calc(11px * var(--scale)); color: #6f6a92; white-space: pre;
  overflow: hidden; text-overflow: ellipsis;
}
.inc-teach {
  display: flex; gap: 10px; align-items: baseline; padding: 9px 11px;
  background: #17142a; border-left: 3px solid var(--violet);
  font-size: calc(12px * var(--scale)); line-height: 1.6; min-height: calc(34px * var(--scale));
}
.inc-teach-name {
  font-family: 'Press Start 2P', monospace; font-size: calc(9px * var(--scale));
  color: var(--violet); flex: 0 0 auto;
}
.inc-teach-body { color: var(--ink-dim); }

.inc-enemy:focus-visible, .inc-move:focus-visible, .inc-cast:focus-visible {
  outline: 2px solid var(--gold); outline-offset: 2px;
}
.inc-hole.is-focus { outline: 1px solid var(--line-hi); }
body.reduced-motion .inc-line, .inc-still .inc-line { animation: none !important; }
@media (max-width: 1100px) {
  .inc-line { font-size: calc(16px * var(--scale)); }
  .inc-enemy { flex-basis: 130px; }
}
`;

/* Convenience constructor for callers that would rather not use `new`, matching
 * createBattleFX in fx.js. */
export function createIncantationUI(host, opts = {}) {
  return new IncantationUI(host, opts);
}

export const TIER_LABELS = TIER_META.map(m => m.label);
export const INCANT_VERSION = '1.0.0';
