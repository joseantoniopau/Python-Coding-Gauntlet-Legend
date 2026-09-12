/* Python Coding Gauntlet Legend — the shared shell adapter.
 *
 * Four screen modules landed at once — the town, the hunt, the sages and the
 * finale — and every one of them needed the same six things: main.js's single
 * modal node, its single toast rail, its single panel body, a way to escape a
 * server sentence into HTML, a way to read a refusal, and somewhere to put a
 * timer so it cannot outlive the node it was writing to.
 *
 * Four copies of that is four places to fix the fifth timer leak. This is one.
 *
 * WHAT IT IS NOT. It holds no game state, makes no requests and decides no
 * rules. Every sentence it draws was written by a Python module; every refusal
 * it renders is the server's own. If you are looking for a number, it is not
 * in here, and that is the point.
 */
import { audio } from './audio.js';

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}

/* Every string these screens draw is server prose — an NPC's line, a smith's
 * complaint, a refusal. None of it is player input and none of it is trusted
 * markup: a module author writing an apostrophe should not be able to break a
 * panel, and an em dash should not become an entity. */
export function esc(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

export const lines = (arr) => (Array.isArray(arr) ? arr : [arr]).filter(Boolean);

/* A number the server may not have sent. Reading `undefined` into a template is
 * how a panel ends up saying "NaN gold". */
/* Number(null) is 0 and Number('') is 0, so a plain isFinite check quietly turns
 * "the server has not measured this yet" into a confident zero — which is how a
 * panel ends up printing "0% of what you make" directly under the server's own
 * sentence saying fourteen. Absent is absent. */
export const num = (v, fallback = 0) => {
  if (v === null || v === undefined || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/* ---------------------------------------------------------------- the host
 *
 * main.js owns the chrome. These borrow it rather than growing their own, so a
 * modal opened here closes on the same backdrop click as every other modal and
 * a panel painted here is torn down by the same destroyChild(). The defaults
 * drive the same DOM directly, so a module still works if configure() is never
 * called — which is what makes each of these testable on its own.
 */
export const HOST = {
  panel: defaultPanel,
  modal: defaultModal,
  closeModal: defaultCloseModal,
  toast: defaultToast,
  say: () => {},
  refresh: async () => null,
  state: () => null,
  back: defaultBack,
  go: () => {},
  /* An encounter payload a screen opened but does not own. main.js owns the
   * battle screen; a module that tried to draw one would be the second one. */
  onEncounter: () => {},
  sfx: (kind) => audio.sfx(kind),
};

export function configure(ctx = {}) {
  for (const key of Object.keys(HOST)) {
    if (typeof ctx[key] === 'function') HOST[key] = ctx[key];
  }
  return HOST;
}

function defaultPanel(title, html) {
  const body = $('#panel-body');
  if (!body) return;
  body.innerHTML = `<h2 class="pixel" style="color:var(--gold);
    font-size:15px;margin:0 0 16px">${title}</h2>${html}`;
  for (const s of $$('.screen')) s.classList.remove('active');
  const screen = $('#screen-panel');
  if (screen) screen.classList.add('active');
}

function defaultModal(html, { wide = false } = {}) {
  const m = $('#modal');
  if (!m) return null;
  m.innerHTML = html;
  m.style.width = wide ? 'min(1040px,96vw)' : 'min(900px,94vw)';
  $('#modal-bg').classList.add('show');
  return m;
}

function defaultCloseModal() {
  const bg = $('#modal-bg');
  if (bg) bg.classList.remove('show');
}

function defaultToast(title, body, kind = '') {
  const host = $('#toasts');
  if (!host) return;
  const t = el('div', `toast ${kind}`, `<span class="tt">${esc(title)}</span>${esc(body)}`);
  host.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; }, 4200);
  setTimeout(() => t.remove(), 4800);
}

function defaultBack() {
  const nav = $('[data-nav="world"]');
  if (nav) nav.click();
}

/* ------------------------------------------------------------- disposables
 *
 * A previous pass in this codebase fixed five leaked timers. The rule that came
 * out of it: NOTHING A SCREEN STARTS MAY OUTLIVE THE NODE IT WRITES TO, and the
 * only way to hold that is to make registering a teardown cheaper than
 * forgetting one.
 *
 * Two bags, because they die at different times — a modal closing must not stop
 * a canvas breathing on the panel behind it. Each module gets its own pair, so
 * leaving the town does not stop the hunt's banner.
 */
export function makeDisposer() {
  const SCREEN = new Set();
  let MODAL = new Set();
  let bag = SCREEN;

  function keep(dispose) { bag.add(dispose); return dispose; }

  function release(which) {
    for (const dispose of Array.from(which)) {
      which.delete(dispose);
      try { dispose(); } catch (e) { /* a teardown that throws is still done */ }
    }
  }

  /* Run `fn` with a different bag current. Used where a node is built after its
   * container exists — a canvas appended into a modal, which must die with it. */
  function inBag(which, fn) {
    const previous = bag;
    bag = which;
    try { return fn(); } finally { bag = previous; }
  }

  /* An interval that stops itself the moment its node leaves the document.
   * Both halves matter: isConnected catches a repaint, the disposer catches a
   * screen change that leaves the node connected but invisible. */
  function loop(node, ms, tick) {
    const owner = bag;
    const id = setInterval(() => {
      if (!node || !node.isConnected) { clearInterval(id); owner.delete(stop); return; }
      try { tick(); } catch (e) { clearInterval(id); owner.delete(stop); }
    }, ms);
    const stop = () => clearInterval(id);
    return keep(stop);
  }

  /* requestAnimationFrame with the same contract. A cutscene and a breathing
   * sprite both want one and neither may survive its screen. */
  function frames(node, tick) {
    const owner = bag;
    let raf = 0;
    let alive = true;
    const step = (t) => {
      if (!alive) return;
      if (!node || !node.isConnected) { stop(); owner.delete(stop); return; }
      try { tick(t); } catch (e) { stop(); owner.delete(stop); return; }
      raf = requestAnimationFrame(step);
    };
    const stop = () => { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; };
    raf = requestAnimationFrame(step);
    return keep(stop);
  }

  function timeout(ms, fn) {
    const owner = bag;
    const id = setTimeout(() => { owner.delete(stop); fn(); }, ms);
    const stop = () => clearTimeout(id);
    return keep(stop);
  }

  function onWindow(event, handler) {
    window.addEventListener(event, handler);
    return keep(() => window.removeEventListener(event, handler));
  }

  /* Open the shared modal on a fresh bag, so dismiss() later stops exactly what
   * this modal started and nothing else. */
  function openModal(html, opts) {
    release(MODAL);
    MODAL = new Set();
    const node = HOST.modal(html, opts);
    return node;
  }

  /* Every button in these files that closes a modal goes through here. */
  function dismiss() {
    release(MODAL);
    HOST.closeModal();
  }

  /* Leaving the screen altogether: both bags. main.js calls this through the
   * mounted-child contract, and every repaint calls it on the way in. */
  function leave() {
    release(MODAL);
    release(SCREEN);
  }

  return {
    keep, release, inBag, loop, frames, timeout, onWindow,
    openModal, dismiss, leave,
    screenBag: SCREEN,
    modalBag: () => MODAL,
  };
}

/* ----------------------------------------------------------------- refusals
 *
 * A sealed refusal is HTTP 409 with {error:'sealed', capability, name, message}.
 * api.js hands it back as a resolved body rather than an exception, so the whole
 * of "no, and here is why" arrives as data. `message` is the exam's own sentence
 * and is shown exactly as written — a screen that paraphrases it is a screen
 * inventing a rule.
 */
export function isSealed(result) {
  return Boolean(result && result.error === 'sealed');
}

export function refusal(result) {
  if (!result || typeof result !== 'object') return '';
  if (result.error === 'sealed') return result.message || 'That is sealed here.';
  return result.message || result.text || result.error || '';
}

/* "SEALED" alone does not tell a player WHICH door shut. The capability goes in
 * the title; the number never reaches a screen. */
export function sealedTitle(result) {
  const cap = (result && result.capability) || '';
  return cap ? `SEALED · ${String(cap).replace(/_/g, ' ')}` : 'SEALED';
}

/* One refusal, drawn as a card rather than swallowed. Used wherever a whole
 * screen is unavailable: the player still gets the sentence and the way out. */
export function refusalCard(result, { title = 'NOT HERE, NOT NOW' } = {}) {
  const sealed = isSealed(result);
  return `<div class="frame" style="padding:16px;border-left:4px solid var(${
    sealed ? '--orange' : '--line-hi'})">
    <div class="section-title" style="margin-top:0">${
      esc(sealed ? sealedTitle(result) : title)}</div>
    <p class="small">${esc(refusal(result) || 'No answer came back.')}</p>
    ${sealed ? '<p class="small muted">Nothing is lost. It is waiting on the '
      + 'other side of the run.</p>' : ''}
  </div>`;
}

/* A section heading plus a body, in the frame every other panel uses. */
export function card(title, html, { accent = '' } = {}) {
  return `<div class="frame" style="padding:15px;margin-bottom:12px${
    accent ? `;border-left:4px solid ${accent}` : ''}">
    <div class="section-title" style="margin-top:0">${esc(title)}</div>
    ${html}</div>`;
}

/* A labelled bar. `value` and `max` are the server's; nothing here rescales. */
export function meter(label, value, max, colour, note = '') {
  const v = num(value), m = Math.max(1, num(max, 1));
  return `<div class="skill-row">
    <span class="sn">${esc(label)}</span>
    <span class="bar"><i style="width:${Math.max(0, Math.min(100, (v / m) * 100))}%${
      colour ? `;background:${colour}` : ''}"></i></span>
    <span class="sv">${Math.round(v)}</span>
    ${note ? `<span class="stage">${esc(note)}</span>` : ''}</div>`;
}

/* Prose out of a module, as paragraphs. */
export function prose(arr, cls = 'small') {
  return lines(arr).map(l => `<p class="${cls}" style="margin:6px 0">${esc(l)}</p>`).join('');
}

/* ------------------------------------------------------------------- faces
 *
 * banter.py names thirty-five trades; sprites.js authored thirteen faces. The
 * unknown ones already fall back to the scholar rather than throwing, which is
 * safe and makes a whole town look like one man. This maps each trade onto the
 * nearest authored face instead — a ferrier gets the smith, a surveyor gets the
 * cartographer — so the square reads as a square. It decides nothing; when
 * somebody draws the other twenty-two, delete the row and it starts using them.
 */
export const FACE_FOR = {
  apprentice: 'scholar', armorer: 'armorer', automaton_small: 'automaton_small',
  captain: 'architect', cartographer: 'cartographer', child: 'scholar',
  clerk: 'scribe', climber: 'ranger', cook: 'armorer', druid: 'druid',
  engineer: 'architect', ferrier: 'smith', forager: 'druid', forester: 'ranger',
  interviewer: 'interviewer', keeper: 'oracle', lamplighter: 'chronomancer',
  mage: 'mage', messenger: 'ranger', miner: 'smith', oracle: 'oracle',
  porter: 'armorer', quartermaster: 'scribe', raker: 'druid', ranger: 'ranger',
  runner: 'ranger', scholar: 'scholar', scribe: 'scribe', smith: 'smith',
  soldier: 'architect', steward: 'scribe', surveyor: 'cartographer',
  villager: 'scholar', warden: 'ranger',
  assayer: 'oracle', mender: 'druid',
};

export function faceFor(kind) {
  return FACE_FOR[String(kind || '')] || 'scholar';
}
