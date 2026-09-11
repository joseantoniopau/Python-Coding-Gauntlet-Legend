/* Python Coding Gauntlet Legend — the party screens.
 *
 * Four things the player owns and one thing that owns the player:
 *
 *   CLASS SELECTION   the six disciplines, offered once, as a real choice
 *   THE SKILL TREE    three branches, seven tiers, drawn with its wires showing
 *   COMPANIONS        nine animals, found or silhouetted, two in the field
 *   THE RELIC CODEX   twenty-two artifacts and the history of each
 *   THE OBLIGING HAND offered sincerely, taken freely, charged permanently
 *
 * Everything on these screens is server truth. Nothing here recomputes a cost,
 * a rank, a bond or a refusal — a second source of truth for "can I spend this
 * point" is how a UI ends up disagreeing with the save file. Where the server
 * says no it also says why, in a `refusal` / `requirement` / `how` string, and
 * that string is what gets drawn. The one thing this file decides for itself is
 * the two-companion limit, because the server silently truncates a third rather
 * than erroring and a silently-ignored click is the worst answer available.
 *
 * It styles itself, like fx.js and incantui.js do, so game.css never has to
 * learn that these screens exist.
 */
import { api } from './api.js';
import { audio } from './audio.js';
import * as sprites from './sprites.js';
import * as lootart from './lootart.js';

export const PARTY_UI_VERSION = '1.0.0';

/* ------------------------------------------------------------ dom helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}

/* Every string on these screens goes through this. It is all server prose and
 * none of it is trusted markup. */
function esc(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

const lines = (arr) => (Array.isArray(arr) ? arr : [arr]).filter(Boolean);

/* --------------------------------------------------------------- the host
 *
 * main.js owns the chrome — one #modal node, one toast stack, one panel body,
 * one modal timer. This module borrows them rather than growing its own, so a
 * modal opened here is closed by the same backdrop click that closes every
 * other modal. configure() is how main.js hands them over; the defaults below
 * drive the same DOM directly so the screens still work if it never does.
 */
const HOST = {
  panel: defaultPanel,
  modal: defaultModal,
  closeModal: defaultCloseModal,
  toast: defaultToast,
  refresh: async () => null,
  state: () => null,
  back: defaultBack,
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

/* The way back off every screen. main.js wires [data-nav="world"] to the one
 * function that also restarts the overworld loop, so pressing it is strictly
 * better than anything this module could do on its own. */
function defaultBack() {
  const nav = $('[data-nav="world"]');
  if (nav) nav.click();
}

/* ------------------------------------------------------------ disposables
 *
 * A previous pass in this codebase fixed four leaked timers. Everything with a
 * clock or a listener registers its teardown here, every screen disposes
 * before it repaints, and every dismissal path disposes too. The rule is that
 * nothing this module starts can outlive the node it was writing to.
 */
/* Three bags, because they die at different times. A modal closing must not
 * stop the sprites breathing on the panel behind it, and a companion speaking
 * mid-fight belongs to the encounter rather than to either. Everything with a
 * clock or a listener lands in whichever bag is current when it is made. */
const SCREEN_BAG = new Set();
const CARD_BAG = new Set();
let MODAL_BAG = new Set();
let BAG = SCREEN_BAG;

function keep(dispose) {
  BAG.add(dispose);
  return dispose;
}

function release(bag) {
  for (const dispose of Array.from(bag)) {
    bag.delete(dispose);
    try { dispose(); } catch (e) { /* a teardown that throws still gets dropped */ }
  }
}

/* Run `fn` with a different bag current, then put the old one back. Used
 * wherever a node is built after its container already exists — a canvas
 * appended into a modal, for instance, which must die with that modal. */
function inBag(bag, fn) {
  const previous = BAG;
  BAG = bag;
  try { return fn(); } finally { BAG = previous; }
}

/* An interval that stops itself the moment its node leaves the document. Both
 * halves matter: the isConnected check catches a repaint, the disposer catches
 * a screen change that leaves the node connected but invisible. */
function loop(node, ms, tick) {
  const bag = BAG;
  const id = setInterval(() => {
    if (!node.isConnected) { clearInterval(id); bag.delete(stop); return; }
    tick();
  }, ms);
  const stop = () => clearInterval(id);
  return keep(stop);
}

function onWindow(event, handler) {
  window.addEventListener(event, handler);
  return keep(() => window.removeEventListener(event, handler));
}

/* Open the shared modal on a fresh bag, so whatever it starts is exactly what
 * dismiss() later stops. */
function openModal(html, opts) {
  release(MODAL_BAG);
  MODAL_BAG = new Set();
  return HOST.modal(html, opts);
}

/* Close the shared modal AND drop whatever it was running. Every button that
 * dismisses a modal in this file goes through here. */
function dismiss() {
  release(MODAL_BAG);
  HOST.closeModal();
}

/* Leaving these screens altogether: the panel's clocks and the modal's clocks,
 * both. The encounter card is deliberately not in here — it belongs to the
 * fight, and beginEncounter() is what ends it.
 *
 * Exported because main.js has to be able to say it: every screen here calls it
 * on the way in, but the shell leaving for the world screen is a dismissal too,
 * and nothing in this file would ever hear about it. */
export function leave() {
  release(MODAL_BAG);
  release(SCREEN_BAG);
}

/* ------------------------------------------------------------- refusals
 *
 * A sealed refusal is HTTP 409 with {error:"sealed", capability, message}.
 * api.js turns it into a resolved body rather than an exception, so the whole
 * of "no, and here is why" arrives as data. `message` is written to be shown to
 * the player exactly as it is; it never gets rewritten here, and a raw status
 * code never reaches a screen.
 */
function refusal(result) {
  if (!result || typeof result !== 'object') return '';
  if (result.error === 'sealed') {
    return result.message || 'That is sealed here.';
  }
  return result.message || result.error || '';
}

function isSealed(result) {
  return Boolean(result && result.error === 'sealed');
}

/* The title over a sealed refusal. The sentence is the exam's and is shown as
 * it was written; the capability belongs in the title, because a player told
 * only "SEALED" does not know which of the six doors just shut. */
function sealedTitle(result) {
  const cap = (result && result.capability) || '';
  return cap ? `SEALED · ${cap.replace(/_/g, ' ')}` : 'SEALED';
}

/* One place that says the bad news, so every screen says it the same way. */
function refuse(result, heading = 'NO') {
  const why = refusal(result);
  if (!why) return false;
  HOST.toast(isSealed(result) ? sealedTitle(result) : heading, why, 'red');
  return true;
}

/* A thrown error is a genuine fault — the server fell over or the page lost
 * it. The player still gets a sentence. */
function broke(heading, err) {
  HOST.toast(heading, err && err.message ? err.message : 'the world went quiet', 'red');
}

/* ------------------------------------------------------------------- style */

const PARTY_CSS = `
.pt-lead { color:var(--ink-dim); font-size:12px; line-height:1.7; margin:0 0 12px }
.pt-strip { display:flex; gap:10px; flex-wrap:wrap; align-items:center;
  margin-bottom:12px }
.pt-pill { border:1px solid var(--line); background:var(--panel);
  padding:5px 9px; font-size:10px; letter-spacing:.06em; color:var(--ink-dim) }
.pt-pill b { color:var(--gold-hi); font-weight:normal }
.pt-pill.hot { border-color:var(--gold); color:var(--gold-hi) }

/* ---- class selection ---- */
.pt-classes { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:12px }
.pt-class { border:1px solid var(--line); background:var(--panel); padding:14px;
  display:flex; flex-direction:column; gap:8px; text-align:left; cursor:pointer;
  color:var(--ink); font:inherit }
.pt-class:hover, .pt-class:focus-visible { border-color:var(--line-hi) }
.pt-class.chosen { border-color:var(--gold); box-shadow:inset 0 0 0 1px var(--gold) }
.pt-class .pt-c-head { display:flex; gap:10px; align-items:flex-start }
.pt-class canvas { image-rendering:pixelated; flex:0 0 auto }
.pt-class .pt-c-name { font-size:13px; letter-spacing:.05em }
.pt-class .pt-c-epithet { color:var(--ink-dim); font-size:11px; line-height:1.6 }
.pt-class .pt-c-habit { color:var(--gold-hi); font-size:11px; line-height:1.7 }
.pt-class .pt-c-body { font-size:11px; line-height:1.7; color:var(--ink-dim) }
.pt-class .pt-c-body b { color:var(--ink); font-weight:normal }
.pt-branches-mini { display:flex; flex-direction:column; gap:3px;
  border-top:1px solid var(--line); padding-top:8px }
.pt-branches-mini span { font-size:10px; color:var(--ink-faint) }
.pt-branches-mini span i { color:var(--violet); font-style:normal }
.pt-attrs { display:flex; gap:6px; flex-wrap:wrap }
.pt-attrs i { font-style:normal; font-size:10px; border:1px solid var(--line);
  padding:2px 5px; color:var(--ink-dim) }

/* ---- the tree ---- */
.pt-tree-wrap { position:relative; overflow-x:auto; padding-bottom:6px }
.pt-tree { position:relative; display:flex; gap:14px; min-width:min-content }
.pt-wires { position:absolute; inset:0; pointer-events:none; z-index:0;
  overflow:visible }
.pt-branch { position:relative; z-index:1; flex:1 1 0; min-width:250px;
  border:1px solid var(--line); background:var(--panel); padding:12px }
.pt-branch > header { border-bottom:1px solid var(--line); padding-bottom:8px;
  margin-bottom:10px }
.pt-branch .pt-b-name { color:var(--violet); font-size:11px; letter-spacing:.08em }
.pt-branch .pt-b-blurb { color:var(--ink-faint); font-size:10px; line-height:1.6;
  margin-top:4px }
.pt-branch .pt-b-count { float:right; color:var(--gold); font-size:10px }
.pt-tier { display:flex; gap:8px; margin-bottom:10px }
.pt-tier-label { writing-mode:vertical-rl; font-size:9px; color:var(--ink-faint);
  letter-spacing:.14em; flex:0 0 auto; padding:2px 0 }
.pt-node { position:relative; flex:1 1 0; border:1px solid var(--line);
  background:#12101f; padding:8px; text-align:left; color:var(--ink);
  font:inherit; cursor:pointer; display:flex; flex-direction:column; gap:3px }
.pt-node:hover:not(:disabled) { border-color:var(--gold) }
.pt-node:disabled { cursor:default; opacity:.72 }
.pt-node.held { border-color:var(--green) }
.pt-node.maxed { border-color:var(--gold); background:#191327 }
.pt-node.locked { border-style:dashed; border-color:var(--line) }
.pt-node.capstone { box-shadow:inset 0 0 0 1px var(--line-hi) }
.pt-n-name { font-size:11px; line-height:1.4; letter-spacing:.03em }
.pt-node.locked .pt-n-name { color:var(--ink-faint) }
.pt-n-tags { display:flex; gap:5px; flex-wrap:wrap; font-size:9px }
.pt-n-tags i { font-style:normal; border:1px solid var(--line); padding:1px 4px;
  color:var(--ink-dim) }
.pt-n-tags i.rank { color:var(--green); border-color:var(--green) }
.pt-n-tags i.cost { color:var(--gold) }
.pt-n-tags i.cap { color:var(--orange); border-color:var(--orange) }
.pt-n-measure { font-size:9px; color:var(--ink-faint); letter-spacing:.04em }
.pt-n-now { font-size:10px; color:var(--green); line-height:1.5 }
.pt-n-why { font-size:10px; color:var(--red); line-height:1.5 }
.pt-pips { display:flex; gap:2px; margin-top:2px }
.pt-pips span { width:7px; height:5px; border:1px solid var(--line);
  background:transparent }
.pt-pips span.on { background:var(--green); border-color:var(--green) }

/* ---- what a point buys ---- */
.pt-delta { display:grid; grid-template-columns:1fr auto 1fr; gap:10px;
  align-items:start; margin:10px 0 }
.pt-delta .col { border:1px solid var(--line); padding:10px; font-size:11px;
  line-height:1.7 }
.pt-delta .col.after { border-color:var(--green) }
.pt-delta .arrow { align-self:center; color:var(--gold); font-size:16px }
.pt-delta h4 { margin:0 0 6px; font-size:10px; letter-spacing:.08em;
  color:var(--ink-faint); font-weight:normal }
.pt-delta .col.after li { color:var(--green) }
.pt-delta ul { margin:0; padding-left:14px }

/* ---- companions ---- */
.pt-pets { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:12px }
.pt-pet { border:1px solid var(--line); background:var(--panel); padding:12px;
  display:flex; flex-direction:column; gap:7px }
.pt-pet.active { border-color:var(--gold) }
.pt-pet.unfound { border-style:dashed }
.pt-pet .pt-p-head { display:flex; gap:10px; align-items:flex-start }
.pt-pet canvas { image-rendering:pixelated; flex:0 0 auto }
.pt-p-name { font-size:12px; letter-spacing:.04em }
.pt-pet.unfound .pt-p-name { color:var(--ink-faint) }
.pt-p-tag { font-size:10px; color:var(--ink-dim); line-height:1.6 }
/* The cost sits on the same row as the counter, ahead of anything the animal
 * says. See renderIntervention() — this is the same rule at rest. */
.pt-p-cost { display:flex; gap:6px; align-items:center; flex-wrap:wrap;
  border:1px solid var(--line); padding:5px 7px; font-size:10px }
.pt-p-cost .lab { color:var(--ink-faint); letter-spacing:.06em }
.pt-p-cost .ceil { color:var(--orange) }
.pt-p-cost .kind { color:var(--blue) }
.pt-bond { display:flex; align-items:center; gap:7px; font-size:10px }
.pt-bond .track { flex:1; height:6px; border:1px solid var(--line);
  background:#0d0b16 }
.pt-bond .track i { display:block; height:100%; background:var(--violet) }
.pt-bond .rank { color:var(--violet); letter-spacing:.06em }
.pt-bond .next { color:var(--ink-faint) }
.pt-p-line { font-size:11px; color:var(--ink); line-height:1.7; font-style:italic }
.pt-p-passive { font-size:10px; color:var(--green); line-height:1.6 }
.pt-checks { display:flex; flex-direction:column; gap:3px }
.pt-check { display:flex; align-items:center; gap:6px; font-size:10px;
  color:var(--ink-faint) }
.pt-check .mark { width:10px; color:var(--ink-faint) }
.pt-check.met { color:var(--green) }
.pt-check.met .mark { color:var(--green) }
.pt-check .track { flex:1; height:4px; border:1px solid var(--line);
  background:#0d0b16 }
.pt-check .track i { display:block; height:100%; background:var(--ink-faint) }
.pt-check.met .track i { background:var(--green) }
.pt-pet .actions { margin-top:auto; padding-top:6px }

/* ---- the intervention card ---- */
.pt-speak { border:1px solid var(--line-hi); background:var(--panel);
  padding:10px; display:flex; flex-direction:column; gap:8px;
  box-shadow:0 4px 18px var(--shadow) }
.pt-speak .pt-s-meter { display:flex; gap:8px; align-items:center;
  border-bottom:1px solid var(--line); padding-bottom:7px; font-size:10px;
  letter-spacing:.05em; flex-wrap:wrap }
.pt-speak .pt-s-meter .count { color:var(--gold) }
.pt-speak .pt-s-meter .ceil { color:var(--orange) }
.pt-speak .pt-s-meter .rule { color:var(--ink-faint); flex-basis:100%;
  letter-spacing:0; line-height:1.6 }
.pt-speak .pt-s-body { display:flex; gap:10px; align-items:flex-start }
.pt-speak canvas { image-rendering:pixelated; flex:0 0 auto }
.pt-speak .pt-s-who { font-size:11px; letter-spacing:.05em }
.pt-speak .pt-s-open { font-size:11px; line-height:1.7; font-style:italic;
  color:var(--ink-dim) }
.pt-speak .pt-s-said { font-size:12px; line-height:1.8; color:var(--ink);
  margin-top:5px }
.pt-speak .actions { display:flex; justify-content:flex-end; margin:0 }

/* ---- the codex ---- */
.pt-relics { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  gap:10px }
.pt-relic { border:1px solid var(--line); background:var(--panel); padding:11px;
  display:flex; gap:10px; text-align:left; color:var(--ink); font:inherit;
  cursor:pointer; align-items:flex-start }
.pt-relic:hover, .pt-relic:focus-visible { border-color:var(--line-hi) }
.pt-relic canvas { image-rendering:pixelated; flex:0 0 auto }
.pt-relic .pt-r-name { font-size:11px; line-height:1.5 }
.pt-relic.locked .pt-r-name { color:var(--ink-faint) }
.pt-relic .pt-r-sig { font-size:10px; color:var(--green); line-height:1.6 }
.pt-relic .pt-r-why { font-size:10px; color:var(--ink-faint); line-height:1.6 }
.pt-relic .pt-r-slot { font-size:9px; color:var(--ink-faint); letter-spacing:.06em }
.pt-history { display:flex; flex-direction:column; gap:8px; margin:10px 0 }
.pt-history div { font-size:11px; line-height:1.8; color:var(--ink-dim);
  border-left:1px solid var(--line); padding-left:10px }
.pt-history div b { color:var(--gold); font-weight:normal; letter-spacing:.06em;
  display:block; font-size:9px; margin-bottom:2px }
.pt-chances { display:flex; gap:6px; flex-wrap:wrap; font-size:10px }
.pt-chances i { font-style:normal; border:1px solid var(--line); padding:2px 5px;
  color:var(--ink-dim) }

/* ---- the hand ---- */
.pt-hand { border:1px solid var(--gold); background:#120f1c; padding:14px;
  margin-top:12px }
.pt-hand .pt-h-lines p { font-size:12px; line-height:1.9; margin:0 0 10px }
.pt-hand .pt-h-note { color:var(--ink-faint); font-size:11px; line-height:1.7 }
.pt-notice { border:1px solid var(--line); padding:12px; font-size:12px;
  line-height:1.9; color:var(--ink) }
.pt-mentor { color:var(--ink-dim); font-size:11px; line-height:1.8;
  margin-top:10px; font-style:italic }
.pt-ledger { display:flex; flex-direction:column; gap:4px; margin-top:8px }
.pt-ledger div { font-size:10px; color:var(--ink-dim);
  display:flex; justify-content:space-between; gap:10px }
.pt-ledger div span:last-child { color:var(--orange) }
`;

function ensureStyle() {
  if (document.getElementById('party-ui-style')) return;
  const s = document.createElement('style');
  s.id = 'party-ui-style';
  s.textContent = PARTY_CSS;
  document.head.appendChild(s);
}

/* =========================================================================
 * COMPANION ART
 * =========================================================================
 * sprites.js has heroes, enemies, bosses and faces; it has no animals, and a
 * companion drawn as a recoloured slime would be a lie about how much the game
 * cares about them. So the nine are authored here, in sprites.js's own glyph
 * vocabulary, and run through its rim light so they sit in the same world as
 * everything else: o outline, B body, a marking, w/k eye, g beak-or-claw.
 *
 * Every one is authored for its SILHOUETTE first, because eight of the nine are
 * a dark shape with a hint under it for most of a playthrough. If you cannot
 * tell the tortoise from the nautilus in black, the unfound card is a smudge.
 */
const PET_W = 20;
const PET_H = 16;

const PET_SHAPES = {
  jaguar: [
    '....................',
    '.oo.............oo..',
    '.oBo...........oBBo.',
    '.oBo..........oBBBBo',
    '.oBo........ooBBBBBo',
    '.oBo.......oBBBwkBBo',
    '.oBo.....ooBBBBBBBBo',
    '.oBooooooBBBBBBBBggo',
    '.oBaBBaBBaBBBBBBBoo.',
    '.oBBBBBBBBBBBBBBo...',
    '..oBaBBaBBaBBBBo....',
    '..oBBBBBBBBBBBBo....',
    '..oBo.oBo..oBBo.....',
    '..oBo.oBo..oBBo.....',
    '..ooo.ooo..ooo......',
    '....................',
  ],
  snake: [
    '....................',
    '............oooo....',
    '...........oBBBBo...',
    '...........oBwkBo...',
    '...........oBBBBBoo.',
    '...........oBBBBo.a.',
    '..........oBBBo.....',
    '.........oBBBo......',
    '........oBBBo.......',
    '.....ooooBBo........',
    '...ooBBBBBBoooo.....',
    '..oBBaBBaBBBBBBoo...',
    '..oBBBBBBBBBBBBBBo..',
    '..oBaBBaBBaBBaBBBo..',
    '...oooooooooooooo...',
    '....................',
  ],
  llama: [
    '.............oo..oo.',
    '.............oBoooBo',
    '.............oBBBBBo',
    '.............oBwkBBo',
    '.............oBBBBgo',
    '..............oBBBo.',
    '..............oBBo..',
    '.....ooooooooooBBo..',
    '....oBBBBBBBBBBBBo..',
    '...oBBaBBBBBBaBBBo..',
    '...oBBBBBBBBBBBBBo..',
    '...oBBBBBBBBBBBBo...',
    '...oBo.oBo..oBo.....',
    '...oBo.oBo..oBo.....',
    '...ooo.ooo..ooo.....',
    '....................',
  ],
  penguin: [
    '.......oooo.........',
    '......oBBBBBo.......',
    '.....oBBBBBBBo......',
    '.....oBwkBBwkBo.....',
    '.....oBBBggBBBo.....',
    '.....oBBBggBBBo.....',
    '....oBBBBBBBBBBo....',
    '....oBaaaaaaaaBo....',
    '...oBBaaaaaaaaBBo...',
    '...oBBaaaaaaaaBBo...',
    '...oBBaaaaaaaaBBo...',
    '...oBBaaaaaaaaBBo...',
    '....oBBaaaaaaBBo....',
    '.....oBBBBBBBBo.....',
    '.....oggo..oggo.....',
    '.....oooo..oooo.....',
  ],
  raptor: [
    '....................',
    '...............oooo.',
    '..............oBBBBo',
    '..............oBwkBo',
    '.....ooo......oBBBgo',
    '..oooBBBoo...ooBBBo.',
    'ooBBBBBBBBoooBBBBo..',
    'oBBaBBaBBBBBBBBBo...',
    '.ooBBBBBBBBBBBBo....',
    '...oBBBBBBBBBBo.....',
    '....oBBo.oBBo.......',
    '....oBBo.oBBo.......',
    '....oBo...oBo.......',
    '...ooBo..ooBo.......',
    '...oggo..oggo.......',
    '....................',
  ],
  axolotl: [
    '....................',
    '.............aa.a...',
    '.aa.........oaoaoo..',
    '.aaa..ooooooooBBBoo.',
    '.aaaooBBBBBBBBBBBBBo',
    '.aaaoBBBBBBBBwkBBBBo',
    '.aaaoBBBBBBBBBBBBgBo',
    '.aaaooBBBBBBBBBBBBBo',
    '.aa...oBBBBBBBBBBoo.',
    '.......ooBBBBBBoo...',
    '.......oBo..oBo.....',
    '.......ooo..ooo.....',
    '....................',
    '....................',
    '....................',
    '....................',
  ],
  tortoise: [
    '....................',
    '......oooooooo......',
    '....ooBaBBBBaBoo....',
    '...oBBBaBBBBaBBBo...',
    '..oBBaaBBBBBBaaBBo..',
    '..oBBBBBBBBBBBBBBo..',
    '.oBBaBBBBBBBBBBaBBo.',
    '.oBBBBBBBBBBBBBBBBo.',
    '.oooooooooooooooo...',
    '.oBBBBBBBBBBBBBBoo..',
    '.oBBo..oBBo..oBwkBo.',
    '.oBBo..oBBo..oBBBgo.',
    '.oooo..oooo..oBBBo..',
    '..............ooo...',
    '....................',
    '....................',
  ],
  nautilus: [
    '......oooooo........',
    '....ooBBBBBBoo......',
    '...oBBaBBBBaBBo.....',
    '..oBBBBoooBBBBBo....',
    '..oBaBoBBBoBaBBo....',
    '.oBBBoBBBBBoBBBBo...',
    '.oBaBoBBoBBoBBaBo...',
    '.oBBBoBBBBBoBBBBoaa.',
    '.oBBBBoooooBBBBBoaa.',
    '..oBaBBBBBBBaBBowko.',
    '..oBBBBBBBBBBBBoaaa.',
    '...oBBaBBBBaBBo.aa..',
    '....ooBBBBBBoo..a...',
    '......oooooo........',
    '....................',
    '....................',
  ],
  crow: [
    '....................',
    '.............oooo...',
    '............oBBBBo..',
    '............oBwkBoo.',
    '...........oBBBBggo.',
    '..........oBBBBBBo..',
    '.....ooooooBBBBBo...',
    '...ooBBBBBBBBBBo....',
    '..oBBaBBBBBBBBBo....',
    'ooBBBBBBBBBBBBBo....',
    '.ooBaBBBBBBBBBo.....',
    '..ooBBBBBBBBoo......',
    '....oBo.oBo.........',
    '....ooo.ooo.........',
    '....ggg.ggg.........',
    '....................',
  ],
};

export const PET_SPRITE_KEYS = Object.keys(PET_SHAPES);

/* The same five-step ladder enemies use, so a companion and a monster standing
 * in the same frame are lit by the same lamp. */
function petPalette(colour) {
  const r = sprites.ramp(colour || '#9b96b8');
  const a = sprites.ramp(sprites.shade(colour || '#9b96b8', 46));
  return {
    o: sprites.mix(r.outline, '#0b0912', 0.45), O: r.rim,
    D: r.shadow2, d: r.shadow1, B: r.base, L: r.light1, H: r.light2,
    a: a.light1, A: a.light2,
    w: '#f2f6ff', W: '#ffffff', k: '#120f1c',
    g: sprites.mix(r.light2, '#e8e2d0', 0.7),
  };
}

/* An animal nobody has met is a shape and nothing else. The eye stays lit —
 * one pixel of white is the difference between "not found yet" and "not drawn
 * yet", and the second reads as a bug. */
const SILHOUETTE_PALETTE = {
  o: '#0d0b16', O: '#1c1830',
  D: '#151223', d: '#181428', B: '#1d1930', L: '#221d38', H: '#272140',
  a: '#201b34', A: '#241e3a',
  w: '#5a4f95', W: '#6a5fa5', k: '#0d0b16',
  g: '#231d38',
};

const petCache = new Map();

export function petSprite(spriteKey, colour, frame = 0, { silhouette = false } = {}) {
  const key = PET_SHAPES[spriteKey] ? spriteKey : 'crow';
  const f = frame & 1;
  const ck = `${key}:${silhouette ? 'sil' : colour}:${f}`;
  if (petCache.has(ck)) return petCache.get(ck);
  const base = sprites.normalise(PET_SHAPES[key], PET_W);
  // The off frame is the whole animal one pixel higher: a breath, not a walk.
  // Anything more elaborate would need a second authored pose per species and
  // these are decoration on a card, not a battle sprite.
  const grid = sprites.applyRim(f ? sprites.bobGrid(base, -1) : base);
  const canvas = sprites.gridSprite(
    grid, silhouette ? SILHOUETTE_PALETTE : petPalette(colour), PET_W, PET_H);
  petCache.set(ck, canvas);
  return canvas;
}

/* A live canvas at `scale`, breathing unless the player asked us not to. */
function petCanvas(pet, scale = 2, { silhouette = false } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = PET_W; canvas.height = PET_H;
  canvas.style.width = `${PET_W * scale}px`;
  canvas.style.height = `${PET_H * scale}px`;
  canvas.style.imageRendering = 'pixelated';
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  let frame = 0;
  const paint = () => {
    ctx.clearRect(0, 0, PET_W, PET_H);
    ctx.drawImage(petSprite(pet.sprite, pet.colour, frame, { silhouette }), 0, 0);
  };
  paint();
  if (!reducedMotion()) loop(canvas, 420, () => { frame ^= 1; paint(); });
  return canvas;
}

function reducedMotion() {
  const s = HOST.state();
  return Boolean(s && s.settings && s.settings.reduced_motion);
}

/* ------------------------------------------------------------ screen shell
 *
 * Every screen in this file gets the same header: a way back to the world and
 * a way across to its siblings. Nobody arrives at the codex and finds that the
 * only exit is the browser's back button.
 */
const SCREENS = [
  { key: 'tree', label: 'SKILL TREE', open: () => paintSkillTree() },
  { key: 'pets', label: 'COMPANIONS', open: () => paintCompanions() },
  { key: 'relics', label: 'RELIC CODEX', open: () => paintRelicCodex() },
];

function shell(title, here, html) {
  const nav = SCREENS.map(s =>
    `<button class="btn small${s.key === here ? ' primary' : ''}"
       data-pt-go="${s.key}">${s.label}</button>`).join('');
  HOST.panel(title, `
    <div class="pt-strip">
      <button class="btn small" data-pt-back="1">◀ THE WORLD</button>
      ${nav}
    </div>
    ${html}`);
  bind('[data-pt-back]', () => { leave(); HOST.back(); });
  for (const s of SCREENS) {
    bind(`[data-pt-go="${s.key}"]`, () => { HOST.sfx('select'); s.open(); });
  }
}

function bind(selector, handler, root = document) {
  for (const node of $$(selector, root)) {
    node.onclick = (e) => handler(node, e);
  }
}

/* Modal buttons, with the dismissal path wired once so no caller forgets the
 * timers. */
function modalActions(m, map) {
  for (const [selector, handler] of Object.entries(map)) {
    bind(selector, (node, e) => handler(node, e), m);
  }
}

/* =========================================================================
 * CLASS SELECTION
 * =========================================================================
 * Six cards, once, at the start. This is the first thing the player decides
 * that the game does not decide back, so it gets the room: what the discipline
 * believes, what it trains, how a fight feels, and the one signature move that
 * is the whole argument compressed. Nothing here is reversible by accident —
 * the card opens a page, and the page has the button.
 */

/* sprites.js indexes portraits by role, not by class id, and an unknown key
 * silently falls back to `scholar` — which would draw all six disciplines with
 * the same face. These are the nearest authored faces, picked so the six read
 * apart in a row at 24px. */
const CLASS_FACE = {
  analyst: 'cartographer',
  berserker: 'ranger',
  archivist: 'scribe',
  warden: 'warden',
  artificer: 'smith',
  seer: 'oracle',
};

function faceCanvas(kind, scale = 2) {
  const img = sprites.portrait(CLASS_FACE[kind] || kind || 'scholar');
  const canvas = document.createElement('canvas');
  canvas.width = img.width; canvas.height = img.height;
  canvas.style.width = `${img.width * scale}px`;
  canvas.style.height = `${img.height * scale}px`;
  canvas.style.imageRendering = 'pixelated';
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, 0, 0);
  return canvas;
}

export async function paintClassSelection() {
  ensureStyle();
  leave();
  let payload;
  try {
    payload = await api.classes();
  } catch (e) { broke('THE GUILD IS NOT ANSWERING', e); return; }
  if (payload.error && !payload.selection) {
    HOST.toast('NO', refusal(payload), 'red');
    return;
  }

  const selection = payload.selection || [];
  const chosen = payload.chosen || '';
  // Only asked for once the player already has a class: it decides whether the
  // other five read as "not mine" or as "a second discipline, at a price".
  let tree = null;
  if (chosen) {
    const t = await api.classTree().catch(() => null);
    if (t && !t.error) tree = t;
  }

  const cards = selection.map(c => {
    const mine = c.id === chosen;
    const dual = tree && tree.dual === c.id;
    const attrs = Object.entries(c.attributes || {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<i>${esc(k)} ${v}</i>`).join('');
    return `<button class="pt-class${mine || dual ? ' chosen' : ''}"
        data-pt-class="${esc(c.id)}">
      <span class="pt-c-head">
        <span data-pt-face="${esc(c.id)}"></span>
        <span class="grow">
          <span class="pt-c-name" style="color:${esc(c.colour)}">
            ${esc(c.name.toUpperCase())}</span>
          ${mine ? '<span class="pt-c-name" style="color:var(--green)"> ✔ YOURS</span>'
                 : dual ? '<span class="pt-c-name" style="color:var(--violet)"> · SECOND</span>' : ''}
          <span class="pt-c-epithet">${esc(c.epithet)}</span>
        </span>
      </span>
      <span class="pt-c-habit">${esc(c.habit)}</span>
      <span class="pt-c-body"><b>Rewards</b> ${esc(c.trains)}</span>
      <span class="pt-c-body"><b>Plays like</b> ${esc(c.plays_like)}</span>
      <span class="pt-attrs">${attrs}</span>
      <span class="pt-branches-mini">
        ${(c.branches || []).map(b =>
          `<span><i>${esc(b.name)}</i> — ${esc(b.blurb)}</span>`).join('')}
      </span>
      <span class="pt-c-body"><b>${esc((c.move || {}).name || '')}</b>
        — ${esc((c.move || {}).blurb || '')}</span>
    </button>`;
  }).join('');

  shell('CHOOSE A DISCIPLINE', null, `
    <p class="pt-lead">${chosen
      ? 'You are one of these already. The other five are still here because at '
        + 'level twenty you may keep a second one — a seasoning, never a second build.'
      : 'Six ways of being wrong on the way to being right. None of them is the '
        + 'strong one. Each rewards a different habit, and the habit is the point: '
        + 'the tree behind it only ever pays out on evidence you actually produced.'}</p>
    <div class="pt-classes">${cards}</div>`);

  for (const node of $$('[data-pt-face]')) {
    node.appendChild(faceCanvas(node.dataset.ptFace));
  }
  bind('[data-pt-class]', (node) => {
    const spec = selection.find(c => c.id === node.dataset.ptClass);
    if (spec) showClassPage(spec, { chosen, tree });
  });
}

function showClassPage(spec, { chosen, tree }) {
  HOST.sfx('select');
  const move = spec.move || {};
  const mine = spec.id === chosen;
  const isDual = tree && tree.dual === spec.id;
  const cost = Object.entries(move.cost || {})
    .map(([k, v]) => `${v} ${k}`).join(' · ') || 'nothing';

  // The three states this page can be in, and the sentence each one owes the
  // player. The refusal for the third comes from the server on the attempt —
  // this only has to say that a door exists and is shut.
  let action = '';
  if (!chosen) {
    action = `<button class="btn primary" data-pt-take>TAKE THIS DISCIPLINE</button>`;
  } else if (mine) {
    action = `<button class="btn primary" data-pt-tree>OPEN THE TREE</button>`;
  } else if (isDual) {
    action = `<span class="pt-c-body">Kept as your second discipline. Its first
      rank of nodes is open to you and nothing deeper is.</span>`;
  } else {
    const open = tree && tree.dual_open;
    const taken = tree && tree.dual;
    action = `<button class="btn" data-pt-dual>KEEP AS SECOND DISCIPLINE</button>
      <span class="pt-c-body">${open && !taken
        ? 'One seasoning, first ranks only, and the Armorer is the only way back.'
        : 'Not open yet — ask and the Guild will tell you why.'}</span>`;
  }

  const m = openModal(`
    <h2 style="color:${esc(spec.colour)}">${esc(spec.name.toUpperCase())}</h2>
    <p class="pt-c-epithet">${esc(spec.epithet)}</p>
    <div class="grid2" style="margin-top:12px">
      <div class="frame" style="padding:12px">
        <div class="section-title">THE HABIT</div>
        <p class="small" style="color:var(--gold-hi);line-height:1.8">
          ${esc(spec.habit)}</p>
        <div class="section-title">WHAT IT REWARDS</div>
        <p class="small">${esc(spec.trains)}</p>
        <div class="section-title">HOW IT PLAYS</div>
        <p class="small muted">${esc(spec.plays_like)}</p>
      </div>
      <div class="frame" style="padding:12px">
        <div class="section-title">SIGNATURE — ${esc(move.name || '')}</div>
        <p class="small">${esc(move.blurb || '')}</p>
        <p class="small muted">Window: ${esc(move.window || '—')} · Costs ${esc(cost)}
          ${move.wager ? ' · it is a wager' : ''}</p>
        <p class="small" style="color:var(--green)">Right: ${esc(move.on_right || '—')}</p>
        <p class="small" style="color:var(--red)">Wrong: ${esc(move.on_wrong || '—')}</p>
        <div class="section-title">AFFINITY</div>
        <p class="small muted">${esc(spec.affinity_set_name || '')} gear, and the
          ${esc(spec.signature_set_name || '')} set is the one this discipline is
          eventually asked for by name.</p>
      </div>
    </div>
    <div class="frame" style="padding:12px;margin-top:12px">
      <div class="section-title">THREE BRANCHES</div>
      ${(spec.branches || []).map(b => `<div class="list-item">
        <span class="t">${esc(b.name.toUpperCase())}</span>
        <span class="d">${esc(b.blurb)}</span></div>`).join('')}
    </div>
    <div class="actions">
      ${action}
      <button class="btn" data-pt-close>LOOK AGAIN</button>
    </div>`, { wide: true });
  if (!m) return;

  modalActions(m, {
    '[data-pt-close]': () => dismiss(),
    '[data-pt-tree]': () => { dismiss(); paintSkillTree(); },
    '[data-pt-take]': async () => {
      let r;
      try { r = await api.chooseClass(spec.id); } catch (e) { broke('NOT TAKEN', e); return; }
      if (refuse(r, 'NOT TAKEN')) return;
      HOST.sfx('levelup');
      HOST.toast('SWORN', `${spec.name}. ${spec.habit}`, '');
      dismiss();
      await HOST.refresh();
      paintSkillTree();
    },
    '[data-pt-dual]': async () => {
      let r;
      try { r = await api.chooseDual(spec.id); } catch (e) { broke('THE GUILD DECLINES', e); return; }
      // choose_dual answers its own refusals in full sentences — level, already
      // holding one, or the discipline you already are. Show the sentence.
      if (refuse(r, 'THE GUILD DECLINES')) return;
      HOST.sfx('unlock');
      HOST.toast('SECOND DISCIPLINE', `${spec.name}, first ranks only.`, 'violet');
      dismiss();
      await HOST.refresh();
      paintClassSelection();
    },
  });
}

/* =========================================================================
 * THE SKILL TREE
 * =========================================================================
 * Three branches, seven tiers, and the prerequisite lines drawn where you can
 * see them. The lines are the point: a tree rendered as three independent
 * lists is a shopping menu, and the thing that makes a tree a decision is
 * being able to see, before you spend, which three nodes this one is standing
 * on top of.
 *
 * Every legality question — cost, rank ceiling, parent depth, branch
 * investment, capstone level — is answered by node_view() on the server and
 * read off the payload here. `refusal` is shown on the node itself rather than
 * only in a tooltip, because a disabled button with no visible reason is the
 * same as content that is simply missing.
 */
const TIERS = [1, 2, 3, 4, 5, 6, 7];

export async function paintSkillTree() {
  ensureStyle();
  leave();
  let tree;
  try {
    tree = await api.classTree();
  } catch (e) { broke('THE TREE WILL NOT OPEN', e); return; }

  // The server answers "no class chosen" with the selection screen attached,
  // which is exactly the screen the player needs next.
  if (tree.error === 'no class chosen') { paintClassSelection(); return; }
  if (tree.error) { HOST.toast('THE TREE WILL NOT OPEN', refusal(tree), 'red'); return; }

  const spec = tree.class || {};
  const points = tree.points || 0;
  const branches = tree.branches || [];

  const branchHtml = branches.map(branch => {
    const byTier = new Map();
    for (const node of branch.nodes || []) {
      if (!byTier.has(node.tier)) byTier.set(node.tier, []);
      byTier.get(node.tier).push(node);
    }
    const tiers = TIERS.filter(t => byTier.has(t)).map(t => `
      <div class="pt-tier" data-tier="${t}">
        <span class="pt-tier-label">T${t}</span>
        ${byTier.get(t).map(nodeHtml).join('')}
      </div>`).join('');
    return `<div class="pt-branch" data-branch="${esc(branch.id)}">
      <header>
        <span class="pt-b-count">${branch.invested}/${branch.capacity}</span>
        <div class="pt-b-name">${esc(branch.name.toUpperCase())}</div>
        <div class="pt-b-blurb">${esc(branch.blurb)}</div>
      </header>
      ${tiers}
      <div class="actions">
        <button class="btn small" data-pt-respec-branch="${esc(branch.id)}"
          ${branch.invested ? '' : 'disabled title="nothing invested here yet"'}>
          UNPICK THIS BRANCH</button>
      </div>
    </div>`;
  }).join('');

  const dualHtml = tree.dual
    ? `<div class="frame" style="padding:12px;margin-top:12px">
        <div class="section-title">SECOND DISCIPLINE</div>
        <p class="small muted">First ranks only, and only these:</p>
        <div class="pt-tier">${(tree.dual_nodes || []).map(nodeHtml).join('')}</div>
      </div>`
    : '';

  shell('THE TREE', 'tree', `
    <div class="pt-strip">
      <span class="pt-pill${points ? ' hot' : ''}"><b>${points}</b> POINT${
        points === 1 ? '' : 'S'} UNSPENT</span>
      <span class="pt-pill">SPENT <b>${tree.spent || 0}</b> / ${tree.capacity || 0}</span>
      <span class="pt-pill" style="color:${esc(spec.colour || 'var(--gold)')}">
        ${esc((spec.name || '').toUpperCase())}</span>
      ${tree.respecs ? `<span class="pt-pill">REBUILDS <b>${tree.respecs}</b></span>` : ''}
      ${tree.grip ? `<span class="pt-pill hot">UNFAMILIAR FOR <b>${tree.grip}</b>
        MORE ENCOUNTER${tree.grip === 1 ? '' : 'S'}</span>` : ''}
    </div>
    <p class="pt-lead">${esc(spec.habit || '')} Every node below pays out on one
      named measure and nothing else, which is why a point here is a statement
      about how you intend to play rather than a number going up.</p>
    ${(tree.effect_text || []).length ? `<div class="frame" style="padding:12px;
      margin-bottom:12px">
      <div class="section-title">WHAT THE TREE IS DOING FOR YOU</div>
      <p class="small" style="color:var(--green);line-height:1.8">
        ${(tree.effect_text || []).map(esc).join('<br>')}</p></div>` : ''}
    <div class="pt-tree-wrap">
      <div class="pt-tree" id="pt-tree">
        <svg class="pt-wires" aria-hidden="true"></svg>
        ${branchHtml}
      </div>
    </div>
    ${dualHtml}
    <div class="actions" style="margin-top:12px">
      <button class="btn" data-pt-respec-all>REBUILD THE WHOLE TREE</button>
      <button class="btn small" data-pt-classes>THE SIX DISCIPLINES</button>
    </div>`);

  drawWires();
  // Measured boxes, so: once now, and once more after the browser has settled
  // the fonts and decided whether the tree needs a horizontal scrollbar. The
  // second pass costs one frame and fixes wires that are otherwise a few
  // pixels out on first paint.
  requestAnimationFrame(drawWires);
  // Anything that reflows the page invalidates them too. The listener is
  // registered, so leaving the screen takes it with us.
  onWindow('resize', drawWires);

  const nodeById = new Map();
  for (const branch of branches) {
    for (const node of branch.nodes || []) nodeById.set(node.id, node);
  }
  for (const node of tree.dual_nodes || []) nodeById.set(node.id, node);

  bind('[data-pt-node]', (el_) => {
    const node = nodeById.get(el_.dataset.ptNode);
    if (node) showNodePage(node, tree);
  });
  bind('[data-pt-classes]', () => paintClassSelection());
  bind('[data-pt-respec-all]', () => confirmRespec('all', '', tree));
  bind('[data-pt-respec-branch]', (el_) => {
    const branch = branches.find(b => b.id === el_.dataset.ptRespecBranch);
    confirmRespec('branch', el_.dataset.ptRespecBranch, tree, branch);
  });
}

function nodeHtml(node) {
  const held = node.rank > 0;
  const maxed = node.rank >= node.max_rank;
  /* `locked` is the server's own word for the three refusals the TREE makes —
   * parent depth, branch investment, capstone level — and those get a genuinely
   * disabled button, because no amount of clicking changes them today. The
   * other refusals (no points, already full) leave the node pressable so its
   * page can still be read, since "come back with a point" is not the same
   * answer as "this door is not yours yet". Both say why on the card. */
  const dead = Boolean(node.locked);
  const cls = [];
  if (maxed) cls.push('maxed');
  else if (held) cls.push('held');
  if (node.locked) cls.push('locked');
  if (node.capstone) cls.push('capstone');
  const disabled = dead;
  const why = node.can_spend ? '' : (node.refusal || '');

  const pips = Array.from({ length: node.max_rank }, (_, i) =>
    `<span class="${i < node.rank ? 'on' : ''}"></span>`).join('');

  return `<button class="pt-node ${cls.join(' ')}" data-pt-node="${esc(node.id)}"
      data-parent="${esc(node.parent || '')}"
      data-parent-ranks="${node.parent_ranks || 0}"
      ${disabled ? `disabled title="${esc(why || 'not yet')}"` : ''}>
    <span class="pt-n-name">${esc(node.name)}</span>
    <span class="pt-n-tags">
      <i class="rank">${node.rank}/${node.max_rank}</i>
      <i class="cost">${node.cost} PT</i>
      ${node.capstone ? '<i class="cap">CAPSTONE</i>' : ''}
    </span>
    <span class="pt-pips">${pips}</span>
    <span class="pt-n-measure">MEASURED ON ${esc(node.measure_label || node.measure)}</span>
    ${held && (node.current_text || []).length
      ? `<span class="pt-n-now">${(node.current_text || []).map(esc).join(' · ')}</span>`
      : ''}
    ${why ? `<span class="pt-n-why">${esc(why)}</span>` : ''}
  </button>`;
}

/* The prerequisite lines. Drawn from measured boxes rather than from a layout
 * this module assumes, so a branch with four nodes on one tier and one on the
 * next still joins up. A lit line means the parent is deep enough; a dim one
 * is the reason the child below it is refusing. */
function drawWires() {
  const tree = $('#pt-tree');
  if (!tree) return;
  const svg = $('.pt-wires', tree);
  if (!svg) return;
  const base = tree.getBoundingClientRect();
  svg.setAttribute('viewBox', `0 0 ${Math.round(base.width)} ${Math.round(base.height)}`);
  svg.setAttribute('width', Math.round(base.width));
  svg.setAttribute('height', Math.round(base.height));

  const parts = [];
  for (const child of $$('[data-pt-node]', tree)) {
    const parentId = child.dataset.parent;
    if (!parentId) continue;
    const parent = tree.querySelector(`[data-pt-node="${CSS.escape(parentId)}"]`);
    if (!parent) continue;
    const a = parent.getBoundingClientRect();
    const b = child.getBoundingClientRect();
    const x1 = Math.round(a.left - base.left + a.width / 2);
    const y1 = Math.round(a.bottom - base.top);
    const x2 = Math.round(b.left - base.left + b.width / 2);
    const y2 = Math.round(b.top - base.top);
    const mid = Math.round(y1 + (y2 - y1) / 2);
    // A parent that is deep enough lights its wire. The number of ranks the
    // child wants is on the wire itself when it is more than one, because
    // "the node above it is not deep enough yet" is a better sentence with a
    // number attached to it.
    const lit = parent.classList.contains('held') || parent.classList.contains('maxed');
    const want = Number(child.dataset.parentRanks || 0);
    const colour = lit ? 'var(--gold)' : 'var(--line)';
    parts.push(`<path d="M${x1} ${y1} V${mid} H${x2} V${y2}" fill="none"
      stroke="${colour}" stroke-width="1" shape-rendering="crispEdges"></path>`);
    parts.push(`<rect x="${x2 - 1}" y="${y2 - 2}" width="3" height="3"
      fill="${colour}"></rect>`);
    if (want > 1) {
      parts.push(`<text x="${x2 + 5}" y="${mid + 3}" font-size="8"
        fill="${lit ? 'var(--gold)' : 'var(--ink-faint)'}">${want}</text>`);
    }
  }
  svg.innerHTML = parts.join('');
}

/* Spending a point is a decision, so it gets a page that says what changes.
 * NOW and AFTER side by side, from the server's own describe() output — no
 * client-side arithmetic on effects, because a UI that computes the delta
 * itself is a second balance sheet waiting to disagree with the first. */
function showNodePage(node, tree) {
  HOST.sfx('select');
  const maxed = node.rank >= node.max_rank;
  const disabled = node.locked || !node.can_spend;
  const now = lines(node.current_text);
  const after = lines(node.next_text);
  const left = (tree.points || 0) - (node.cost || 0);

  const m = openModal(`
    <h2>${esc(node.name.toUpperCase())}</h2>
    <p class="small muted">Tier ${node.tier} · ${esc(node.branch.replace(/_/g, ' '))}
      ${node.capstone ? ' · <span style="color:var(--orange)">CAPSTONE</span>' : ''}
      · rank ${node.rank} of ${node.max_rank}</p>
    <p class="small" style="line-height:1.9;margin-top:10px">${esc(node.blurb)}</p>
    ${node.rule ? `<p class="small" style="color:var(--gold-hi);line-height:1.8">
      ${esc(node.rule)}</p>` : ''}
    <p class="small muted">It pays out on one measure and nothing else:
      <b style="color:var(--violet)">${esc(node.measure_label || node.measure)}</b>
      — ${esc(node.measure_signal || '')}</p>
    <div class="pt-delta">
      <div class="col">
        <h4>NOW — RANK ${node.rank}</h4>
        ${now.length ? `<ul>${now.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`
                     : '<span class="muted">nothing yet</span>'}
      </div>
      <div class="arrow">▸</div>
      <div class="col after">
        <h4>${maxed ? 'FULL RANK' : `AFTER — RANK ${node.rank + 1}`}</h4>
        ${after.length ? `<ul>${after.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`
                       : '<span class="muted">this is as far as it goes</span>'}
      </div>
    </div>
    ${disabled && node.refusal
      ? `<p class="small" style="color:var(--red);line-height:1.8">
          ${esc(node.refusal)}</p>`
      : `<p class="small muted">Costs ${node.cost} point${node.cost === 1 ? '' : 's'}.
          ${left >= 0 ? `${left} left afterwards.` : ''} The Armorer can unpick it
          later, at a price, and the first rebuild is free.</p>`}
    <div class="actions">
      ${disabled ? '' : `<button class="btn primary" data-pt-spend>
        SPEND ${node.cost} POINT${node.cost === 1 ? '' : 'S'}</button>`}
      <button class="btn" data-pt-close>${disabled ? 'BACK' : 'NOT YET'}</button>
    </div>`);
  if (!m) return;

  modalActions(m, {
    '[data-pt-close]': () => dismiss(),
    '[data-pt-spend]': async () => {
      let r;
      try { r = await api.spendNode(node.id); } catch (e) { broke('NOT SPENT', e); return; }
      if (refuse(r, 'NOT SPENT')) return;
      HOST.sfx('levelup');
      const gained = lines(after);
      HOST.toast(`${node.name.toUpperCase()} — RANK ${r.rank}`,
                 gained.join(' · ') || 'held', 'violet');
      dismiss();
      await HOST.refresh();
      paintSkillTree();
    },
  });
}

function confirmRespec(scope, branchId, tree, branch) {
  HOST.sfx('select');
  const what = scope === 'branch'
    ? `every point in ${esc((branch && branch.name) || 'this branch')}`
    : `all ${tree.spent || 0} points`;
  const m = openModal(`
    <h2>THE ARMORER</h2>
    <p class="small" style="line-height:1.9">She will pull ${what} back out and
      hand them to you loose. She quotes when you ask, not before — the first
      rebuild is free and after that the price is the number of points you are
      undoing.</p>
    <p class="small muted">A rebuilt tree feels unfamiliar for a few encounters:
      your crit bonus is suppressed while your hands catch up with the new build.
      ${tree.respecs ? `You have rebuilt ${tree.respecs} time${
        tree.respecs === 1 ? '' : 's'} already.` : 'You have not done this before.'}</p>
    <div class="actions">
      <button class="btn danger" data-pt-do>ASK HER</button>
      <button class="btn" data-pt-close>LEAVE IT</button>
    </div>`);
  if (!m) return;

  modalActions(m, {
    '[data-pt-close]': () => dismiss(),
    '[data-pt-do]': async () => {
      let r;
      try {
        r = await api.respecTree(scope, branchId);
      } catch (e) { broke('THE ARMORER DECLINES', e); return; }
      if (refuse(r, 'THE ARMORER DECLINES')) return;
      HOST.sfx('unlock');
      const quote = r.quote || {};
      HOST.toast('REBUILT',
        `${r.points || quote.points || 0} points back`
        + `${quote.free ? ', free this once' : ` for ${r.gold || quote.gold || 0} gold`}.`,
        'violet');
      dismiss();
      await HOST.refresh();
      paintSkillTree();
    },
  });
}

/* =========================================================================
 * COMPANIONS
 * =========================================================================
 * Nine animals. You will meet perhaps three of them in a first playthrough,
 * and the other six are drawn anyway — as a silhouette with the deed that
 * finds them written underneath, and a progress bar under that. A hidden thing
 * with no visible progress is indistinguishable from a bug, which is the
 * server's own comment on undiscovered_hints() and it is right.
 *
 * The rank ceiling is printed beside the hint kind everywhere a companion
 * appears — on the card at rest, and above the line in the field. What a
 * companion costs is never further down the page than what it says.
 */

export async function paintCompanions() {
  ensureStyle();
  leave();
  let payload;
  let discovery;
  try {
    [payload, discovery] = await Promise.all([api.pets(), api.petDiscovery()]);
  } catch (e) { broke('THE ANIMALS ARE ELSEWHERE', e); return; }
  if (payload.error) { HOST.toast('NO', refusal(payload), 'red'); return; }

  const roster = payload.pets || [];
  const limit = payload.limit || 2;
  const progressById = new Map(
    ((discovery && discovery.progress) || []).map(row => [row.pet, row]));
  const active = roster.filter(p => p.active).map(p => p.id);
  const found = roster.filter(p => p.found);

  const cards = roster.map(pet => {
    const prog = progressById.get(pet.id) || {};
    const cost = `<span class="pt-p-cost">
      <span class="lab">COSTS</span>
      <span>1 hint</span>
      <span class="lab">·</span>
      <span class="kind">${esc(pet.hint_label)}</span>
      <span class="lab">·</span>
      <span class="ceil">best rank afterwards: ${esc(pet.rank_ceiling)}</span>
    </span>`;

    if (!pet.found) {
      const checks = (prog.checks || []).map(checkHtml).join('')
        || '<span class="pt-check">no trail yet</span>';
      return `<div class="pt-pet unfound">
        <div class="pt-p-head">
          <span data-pt-pet-art="${esc(pet.id)}"></span>
          <span class="grow">
            <span class="pt-p-name">??? — ${esc(pet.species.toUpperCase())}</span>
            <div class="pt-p-tag">${esc(pet.where || 'somewhere you have not been')}</div>
          </span>
        </div>
        <div class="pt-p-tag" style="color:var(--ink)">${esc(pet.how)}</div>
        ${cost}
        <div class="pt-checks">${checks}</div>
      </div>`;
    }

    const next = pet.next
      ? `<span class="next">${esc(pet.next)} at ${pet.next_at}
          (${Math.max(0, pet.next_at - pet.bond)} to go)</span>`
      : '<span class="next">nothing further to earn</span>';
    return `<div class="pt-pet${pet.active ? ' active' : ''}">
      <div class="pt-p-head">
        <span data-pt-pet-art="${esc(pet.id)}"></span>
        <span class="grow">
          <span class="pt-p-name" style="color:${esc(pet.colour)}">
            ${esc(pet.name.toUpperCase())}</span>
          <div class="pt-p-tag">${esc(pet.species)} · teaches ${esc(pet.skill)}</div>
          <div class="pt-p-tag">${esc(pet.tagline)}</div>
        </span>
      </div>
      ${cost}
      <div class="pt-bond">
        <span class="rank">${esc(pet.rank_label.toUpperCase())}</span>
        <span class="track"><i style="width:${Math.round((pet.fraction || 0) * 100)}%"></i></span>
        ${next}
      </div>
      <div class="pt-p-line">“${esc(pet.line)}”</div>
      <div class="pt-p-tag">${esc(pet.method)}</div>
      ${(pet.passive || []).length
        ? `<div class="pt-p-passive">${(pet.passive || []).map(esc).join(' · ')}</div>`
        : '<div class="pt-p-tag">no passive yet — bond buys one</div>'}
      <div class="actions">
        <button class="btn small${pet.active ? ' good' : ''}"
          data-pt-pet-toggle="${esc(pet.id)}">
          ${pet.active ? 'IN THE FIELD ✔' : 'TAKE ALONG'}</button>
        <button class="btn small" data-pt-pet-page="${esc(pet.id)}">READ</button>
      </div>
    </div>`;
  }).join('');

  const near = (payload.hints || []).filter(h => h.checks && h.checks.length);

  shell('COMPANIONS', 'pets', `
    <div class="pt-strip">
      <span class="pt-pill${active.length ? ' hot' : ''}">
        IN THE FIELD <b>${active.length}</b> / ${limit}</span>
      <span class="pt-pill">MET <b>${found.length}</b> / ${roster.length}</span>
    </div>
    <p class="pt-lead">Two walk with you, never three — at three there is a
      companion for every kind of trouble and choosing stops being a choice.
      None of them can be pressed like a button. They speak when the encounter
      shows the thing they know about, and speaking costs a hint and lowers the
      best rank you can still earn. That price is printed on every card before
      anything any of them has to say.</p>
    <div class="pt-pets">${cards}</div>
    ${near.length ? `<div class="frame" style="padding:12px;margin-top:12px">
      <div class="section-title">NEAREST</div>
      <p class="small muted">The trails with the most progress on them right now.</p>
      ${near.map(h => `<div class="list-item">
        <span class="t">${esc(h.species.toUpperCase())} — ${esc(h.where)}</span>
        <span class="d">${esc(h.how)}</span></div>`).join('')}
    </div>` : ''}`);

  for (const node of $$('[data-pt-pet-art]')) {
    const pet = roster.find(p => p.id === node.dataset.ptPetArt);
    if (pet) node.appendChild(petCanvas(pet, 2, { silhouette: !pet.found }));
  }

  bind('[data-pt-pet-page]', (node) => {
    const pet = roster.find(p => p.id === node.dataset.ptPetPage);
    if (pet) showPetPage(pet, progressById.get(pet.id));
  });

  bind('[data-pt-pet-toggle]', async (node) => {
    const id = node.dataset.ptPetToggle;
    const next = active.includes(id)
      ? active.filter(x => x !== id)
      : active.concat([id]);
    // set_active() truncates past the limit in silence, which from in here
    // looks like a click that did nothing. So the limit is enforced where the
    // player can see it, naming who is already out there.
    if (next.length > limit) {
      const names = active
        .map(a => (roster.find(p => p.id === a) || {}).name)
        .filter(Boolean).join(' and ');
      HOST.toast('TWO, NOT THREE',
        `${names} are already with you. Send one home first.`, 'red');
      return;
    }
    let r;
    try { r = await api.setPets(next); } catch (e) { broke('THEY STAYED PUT', e); return; }
    if (refuse(r, 'THEY STAYED PUT')) return;
    HOST.sfx('pet');
    await HOST.refresh();
    paintCompanions();
  });
}

function checkHtml(row) {
  const pct = row.need ? Math.min(100, Math.round((row.have / row.need) * 100)) : 0;
  return `<div class="pt-check${row.met ? ' met' : ''}">
    <span class="mark">${row.met ? '✔' : '·'}</span>
    <span>${esc(row.label)}</span>
    <span class="track"><i style="width:${pct}%"></i></span>
    <span>${row.have}/${row.need}</span>
  </div>`;
}

function showPetPage(pet, prog) {
  HOST.sfx('select');
  const m = openModal(`
    <h2 style="color:${esc(pet.colour)}">${esc(pet.name.toUpperCase())}</h2>
    <p class="small muted">${esc(pet.species)} · ${esc(pet.skill)} ·
      ${esc(pet.rank_label)} (${pet.bond} bond)</p>
    <div class="pt-p-cost" style="margin:10px 0">
      <span class="lab">WHEN IT SPEAKS IT COSTS</span>
      <span>1 hint</span><span class="lab">·</span>
      <span class="kind">${esc(pet.hint_label)}</span><span class="lab">·</span>
      <span class="ceil">best rank afterwards: ${esc(pet.rank_ceiling)}</span>
    </div>
    <p class="small" style="line-height:1.9">${esc(pet.blurb)}</p>
    <p class="small" style="color:var(--gold-hi);line-height:1.8">${esc(pet.method)}</p>
    <div class="grid2" style="margin-top:10px">
      <div class="frame" style="padding:12px">
        <div class="section-title">IT SPEAKS WHEN</div>
        <p class="small muted">${(pet.speaks_when || [])
          .map(k => esc(String(k).replace(/_/g, ' '))).join('<br>') || 'unrecorded'}</p>
        <p class="small muted">Bond buys earlier, then more often, then a passive.
          It never decays.</p>
      </div>
      <div class="frame" style="padding:12px">
        <div class="section-title">BOND — ${esc(pet.rank_label.toUpperCase())}</div>
        <div class="pt-bond"><span class="track">
          <i style="width:${Math.round((pet.fraction || 0) * 100)}%"></i></span></div>
        <p class="small muted">${pet.next
          ? `${pet.into_rank} into this rank. ${esc(pet.next)} at ${pet.next_at}.`
          : 'The last rank. There is nothing further to earn and it stays anyway.'}</p>
        <p class="small" style="color:var(--green)">
          ${(pet.passive || []).map(esc).join('<br>') || 'no passive yet'}</p>
      </div>
    </div>
    ${prog && (prog.checks || []).length ? `<div class="frame"
      style="padding:12px;margin-top:10px">
      <div class="section-title">HOW YOU MET</div>
      <p class="small muted">${esc(prog.how || '')}</p>
      <div class="pt-checks">${(prog.checks || []).map(checkHtml).join('')}</div>
    </div>` : ''}
    <div class="actions"><button class="btn" data-pt-close>CLOSE</button></div>`,
    { wide: true });
  if (!m) return;
  modalActions(m, { '[data-pt-close]': () => dismiss() });
}

/* ---------------------------------------------------- the field, mid-fight
 *
 * petTick() is called by the battle screen as the player works. It hands the
 * server the signals it collects anyway and gets back either nothing — the
 * usual answer — or one companion with something to say.
 *
 * The cost has already been charged by the time this returns: the engine adds
 * the hint and lowers the rank ceiling inside /api/pet/intervene. So the card
 * does not pretend to gate anything. What it does is put the meter FIRST, in
 * the DOM and on the screen: how many interventions this is of how many, what
 * kind of help it is, and the best rank still reachable afterwards — and only
 * then the animal, and only then what the animal said. Reading the price after
 * reading the hint is not a price.
 */
let saidSealedOnce = false;
let standingCard = null;

/* Called when a new encounter opens. Drops the previous card and re-arms the
 * one-time sealed notice, so a measured run says it once rather than on every
 * keystroke. */
export function beginEncounter() {
  saidSealedOnce = false;
  clearIntervention();
}

export function clearIntervention() {
  if (standingCard && standingCard.dispose) standingCard.dispose();
  standingCard = null;
}

export async function petTick(signals, host, opts = {}) {
  if (!host) return null;
  let r;
  try {
    r = await api.petIntervene(signals || {});
  } catch (e) {
    // This runs on a timer. Saying it every tick would bury the battle screen,
    // so it is said once and then the companions are quietly absent.
    if (!saidSealedOnce) { saidSealedOnce = true; broke('NO COMPANION ANSWERED', e); }
    return null;
  }
  if (isSealed(r) || (r && r.error)) {
    if (!saidSealedOnce) {
      saidSealedOnce = true;
      HOST.toast(isSealed(r) ? sealedTitle(r) : 'NO COMPANION', refusal(r), 'red');
    }
    return null;
  }
  const event = r && r.pet;
  if (!event) return null;
  renderIntervention(event, host, opts);
  return event;
}

export function renderIntervention(event, host, { linger = 0 } = {}) {
  if (!event || !host) return null;
  ensureStyle();
  clearIntervention();
  HOST.sfx('pet');

  const total = (event.spoken || 1) + (event.remaining || 0);
  const card = el('div', 'pt-speak');
  card.innerHTML = `
    <div class="pt-s-meter">
      <span class="count">INTERVENTION ${event.spoken} OF ${total}</span>
      <span>·</span>
      <span>COSTS ${event.hint_weight} HINT</span>
      <span>·</span>
      <span class="ceil">BEST RANK FROM HERE: ${esc(event.rank_ceiling)}</span>
      <span class="rule">${esc(event.hint_label)} — ${esc(event.rule)}</span>
    </div>
    <div class="pt-s-body">
      <span data-pt-speaker></span>
      <span class="grow">
        <span class="pt-s-who" style="color:${esc(event.colour)}">
          ${esc(event.name.toUpperCase())}</span>
        <div class="pt-s-open">“${esc(event.opening)}”</div>
        <div class="pt-s-said">${esc(event.body)}</div>
      </span>
    </div>
    <div class="actions">
      <button class="btn small" data-pt-noted>NOTED</button>
    </div>`;
  host.appendChild(card);

  const art = $('[data-pt-speaker]', card);
  if (art) inBag(CARD_BAG, () => art.appendChild(petCanvas(event, 2)));

  const dispose = () => {
    release(CARD_BAG);
    card.remove();
    standingCard = null;
  };
  // A card that dismisses itself still has to hand its timer back, and the
  // timer has to be in the bag its own dispose empties.
  if (linger > 0) {
    inBag(CARD_BAG, () => {
      const id = setTimeout(dispose, linger);
      keep(() => clearTimeout(id));
    });
  }
  bind('[data-pt-noted]', () => dispose(), card);
  standingCard = { node: card, dispose };
  return card;
}

/* The moment one of them decides to stay. engine.submit() returns these in
 * `found_pets` as full discovery payloads so the meeting can be shown properly
 * rather than logged. */
export function showPetFound(row, { onClose } = {}) {
  if (!row) return;
  ensureStyle();
  const pet = { id: row.pet, sprite: SPRITE_BY_PET[row.pet] || 'crow',
                colour: COLOUR_BY_PET[row.pet] || '#9b96b8' };
  const m = openModal(`
    <h2>SOMETHING DECIDED TO STAY</h2>
    <div class="pt-s-body" style="margin:12px 0">
      <span data-pt-found-art></span>
      <span class="grow">
        <span class="pt-p-name">${esc(row.name.toUpperCase())}</span>
        <div class="pt-p-tag">${esc(row.species)} · ${esc(row.where)}</div>
        <div class="pt-s-said">“${esc(row.first_words)}”</div>
      </span>
    </div>
    <p class="small muted">${esc(row.how)}</p>
    <div class="actions">
      <button class="btn small" data-pt-pets>THE ROSTER</button>
      <button class="btn primary" data-pt-close>GOOD</button>
    </div>`);
  if (!m) return;
  const art = $('[data-pt-found-art]', m);
  if (art) inBag(MODAL_BAG, () => art.appendChild(petCanvas(pet, 3)));
  HOST.sfx('unlock');
  modalActions(m, {
    '[data-pt-close]': () => { dismiss(); if (onClose) onClose(); },
    '[data-pt-pets]': () => { dismiss(); paintCompanions(); },
  });
}

/* The sprite and colour of a companion live on the server, and every payload
 * that carries a pet carries them — except discovery_progress, which is about
 * a pet you have not met. These two tables are the only place this module
 * keeps its own copy of anything, and they exist so the meeting has a picture. */
const SPRITE_BY_PET = {
  jaguar: 'jaguar', python: 'snake', llama: 'llama', penguin: 'penguin',
  velociraptor: 'raptor', axolotl: 'axolotl', tortoise: 'tortoise',
  nautilus: 'nautilus', crow: 'crow',
};
const COLOUR_BY_PET = {
  jaguar: '#e8a33d', python: '#4fb783', llama: '#d8c8a8', penguin: '#7ec8ff',
  velociraptor: '#c4553f', axolotl: '#f2a0b5', tortoise: '#6b8f3f',
  nautilus: '#a89aff', crow: '#9b96b8',
};

/* =========================================================================
 * THE RELIC CODEX
 * =========================================================================
 * Twenty-two artifacts, in the order they become reachable rather than by
 * power, because the interesting ones are not the strongest ones. Each has
 * four lines of history — who made it, who it was made for, how it failed, and
 * how it was found — and those come first on the page, ahead of the numbers,
 * because the history is the reason and the numbers are the consequence.
 *
 * A relic you do not own is still drawn. lootart.js resolves its real shape
 * from its own id and slot, and then it is painted out to a silhouette: the
 * outline is true, the gold is not yours yet, and the condition that would
 * make it yours is printed underneath.
 */

function relicCanvas(item, scale = 2, { locked = false } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = lootart.ITEM_SIZE;
  canvas.height = lootart.ITEM_SIZE;
  canvas.style.width = `${lootart.ITEM_SIZE * scale}px`;
  canvas.style.height = `${lootart.ITEM_SIZE * scale}px`;
  canvas.style.imageRendering = 'pixelated';
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const paint = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    lootart.drawItem(ctx, item, 0, 0, { scale: 1, time: performance.now() });
    if (!locked) return;
    // source-atop paints only where the item already is, so what is left is
    // the artifact's true silhouette rather than a grey rectangle.
    ctx.save();
    ctx.globalCompositeOperation = 'source-atop';
    ctx.fillStyle = 'rgba(13,11,22,0.84)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  };
  paint();
  if (lootart.itemFrameCount(item) > 1 && !reducedMotion() && !locked) {
    loop(canvas, lootart.FRAME_MS, paint);
  }
  return canvas;
}

export async function paintRelicCodex() {
  ensureStyle();
  leave();
  let payload;
  let handState;
  try {
    [payload, handState] = await Promise.all([api.legendaries(), api.hand()]);
  } catch (e) { broke('THE CODEX IS SHUT', e); return; }
  if (payload.error) { HOST.toast('THE CODEX IS SHUT', refusal(payload), 'red'); return; }

  const catalogue = payload.catalogue || [];
  const owned = new Set(payload.owned || []);

  const cards = catalogue.map(art => {
    const have = owned.has(art.id);
    const acq = art.acquisition || {};
    return `<button class="pt-relic${have ? '' : ' locked'}"
        data-pt-relic="${esc(art.id)}">
      <span data-pt-relic-art="${esc(art.id)}"></span>
      <span class="grow">
        <span class="pt-r-name" style="${have ? `color:${esc(art.rarity_colour)}` : ''}">
          ${esc(art.name.toUpperCase())}</span>
        <span class="pt-r-slot">${esc(art.rarity)} · ${esc(art.slot)}
          ${have ? '· <span style="color:var(--green)">HELD</span>' : ''}</span>
        ${have
          ? `<span class="pt-r-sig">${(art.signature_text || []).map(esc).join(' · ')}</span>`
          : `<span class="pt-r-why">${esc(acq.text || 'nobody knows how this one turns up')}</span>`}
      </span>
    </button>`;
  }).join('');

  shell('THE CODEX', 'relics', `
    <div class="pt-strip">
      <span class="pt-pill${owned.size ? ' hot' : ''}">HELD <b>${owned.size}</b>
        / ${catalogue.length}</span>
      ${(handState && handState.owned)
        ? `<span class="pt-pill">THE HAND · <b>${
            (handState.summary || {}).uses || 0}</b> USES</span>` : ''}
    </div>
    <p class="pt-lead">None of these is rolled out of nothing. Every one of them
      has a condition, the condition is written on the page, and until you have
      met it the drop chance is exactly zero. That is the whole of the loot
      design and it is stated here rather than hidden in a table.</p>
    <div class="pt-relics">${cards}</div>
    ${handSection(handState)}`);

  for (const node of $$('[data-pt-relic-art]')) {
    const art = catalogue.find(a => a.id === node.dataset.ptRelicArt);
    if (art) node.appendChild(relicCanvas(art, 2, { locked: !owned.has(art.id) }));
  }
  bind('[data-pt-relic]', (node) => showRelic(node.dataset.ptRelic, owned));
  bindHand(handState);
}

async function showRelic(id, owned) {
  HOST.sfx('select');
  let entry;
  try { entry = await api.legendary(id); } catch (e) { broke('NO SUCH PAGE', e); return; }
  if (entry.error) { HOST.toast('NO SUCH PAGE', refusal(entry), 'red'); return; }

  const have = entry.owned !== undefined ? entry.owned : (owned && owned.has(id));
  const prog = entry.progress || {};
  const h = entry.history || {};
  const chances = Object.entries(entry.chances || {})
    .filter(([, v]) => v > 0)
    .map(([d, v]) => `<i>${esc(d)} ${Math.round(v * 100)}%</i>`).join('');

  const m = openModal(`
    <h2>${esc(entry.name.toUpperCase())}</h2>
    <p class="small muted">${esc(entry.rarity)} · ${esc(entry.slot)}
      ${have ? '· <span style="color:var(--green)">HELD</span>' : ''}</p>
    <div class="center" style="margin:12px 0" data-pt-relic-big></div>
    <div class="pt-history">
      <div><b>MADE BY</b>${esc(h.made_by || '')}</div>
      <div><b>MADE FOR</b>${esc(h.made_for || '')}</div>
      <div><b>HOW IT FAILED</b>${esc(h.failed || '')}</div>
      <div><b>HOW IT WAS FOUND</b>${esc(h.found || '')}</div>
    </div>
    <p class="small" style="color:var(--ink-dim);font-style:italic;line-height:1.8">
      ${esc(entry.flavour)}</p>
    <div class="grid2" style="margin-top:10px">
      <div class="frame" style="padding:12px">
        <div class="section-title">WHAT IT DOES</div>
        <p class="small" style="color:var(--green);line-height:1.8">
          ${(entry.effects || []).map(esc).join('<br>') || 'nothing it will admit to'}</p>
        ${entry.affinity ? `<p class="small muted">Signature for the
          ${esc(entry.affinity)} build${entry.dissonance
            ? `, and it fights the ${esc(entry.dissonance)} one` : ''}.</p>` : ''}
      </div>
      <div class="frame" style="padding:12px">
        <div class="section-title">${have ? 'HOW IT CAME TO YOU' : 'HOW IT IS EARNED'}</div>
        <p class="small" style="line-height:1.8">${esc((prog.text
          || (entry.acquisition || {}).text) || '')}</p>
        ${(prog.checks || []).length
          ? `<div class="pt-checks">${(prog.checks || []).map(checkHtml).join('')}</div>`
          : ''}
        ${prog.conditions && prog.conditions.length && !prog.conditions_met
          ? `<p class="small" style="color:var(--red)">Also wants: ${
              prog.conditions.map(c => esc(String(c).replace(/_/g, ' '))).join(' or ')}</p>`
          : ''}
        ${chances ? `<div class="pt-chances" style="margin-top:8px">${chances}</div>
          <p class="small muted">Chance per clear, once the conditions above are
            met. Before that it is zero at every difficulty.</p>` : ''}
      </div>
    </div>
    <div class="actions"><button class="btn" data-pt-close>CLOSE THE PAGE</button></div>`,
    { wide: true });
  if (!m) return;
  const big = $('[data-pt-relic-big]', m);
  // eligible() carries the full item dict; codex_entry() on its own does not.
  // lootart resolves a shape from id, name and slot, so the fallback is enough
  // to draw the right silhouette when the progress half is absent.
  const art = prog.item
    || { id: entry.id, name: entry.name, slot: entry.slot, rarity: entry.rarity };
  if (big) inBag(MODAL_BAG, () => big.appendChild(relicCanvas(art, 4, { locked: !have })));
  modalActions(m, { '[data-pt-close]': () => dismiss() });
}

/* =========================================================================
 * THE OBLIGING HAND
 * =========================================================================
 * Story bible §3. The King offers it in person, sincerely, and means every
 * word of the offer. It solves any encounter and pays full loot. Each use
 * permanently lowers the ceiling of the skill it solved. Nobody stops you.
 *
 * So nothing in this section warns, confirms twice, greys itself out, asks
 * "are you sure", or attaches an adjective to the notice afterwards. The
 * mechanic is the argument. A UI that editorialises over it is a UI that does
 * not trust the mechanic, and it would turn the best idea in the game into a
 * lecture with a button underneath.
 *
 * The one thing shown, once, afterwards, is the server's own `notice`: two
 * sentences of arithmetic with no opinion in them.
 */

function handSection(hand) {
  if (!hand || hand.error) return '';
  const summary = hand.summary || {};
  const rows = (summary.rows || []).map(r =>
    `<div><span>${esc(r.skill)}</span>
      <span>ceiling ${r.ceiling}</span></div>`).join('');
  if (!hand.owned) {
    return `<div class="pt-hand">
      <div class="section-title">THE OBLIGING HAND</div>
      <p class="small muted">Offered in person, at the edge of the Highlands,
        by someone who is not in a hurry.</p>
      <div class="actions">
        <button class="btn small" data-pt-hand-offer>HEAR THE OFFER</button>
      </div>
    </div>`;
  }
  return `<div class="pt-hand">
    <div class="section-title">THE OBLIGING HAND</div>
    <p class="small">Worn ${summary.uses || 0} time${
      (summary.uses || 0) === 1 ? '' : 's'}${summary.skills_touched
        ? ` across ${summary.skills_touched} skill${
            summary.skills_touched === 1 ? '' : 's'}` : ''}.</p>
    ${rows ? `<div class="pt-ledger">${rows}</div>` : ''}
    ${summary.mentor ? `<p class="pt-mentor">“${esc(summary.mentor.line)}”
      — ${esc(summary.mentor.npc)}</p>` : ''}
    <div class="actions">
      <button class="btn small" data-pt-hand-offer>READ THE OFFER AGAIN</button>
    </div>
  </div>`;
}

function bindHand(hand) {
  bind('[data-pt-hand-offer]', () => offerHand(hand));
}

/* The offer itself, verbatim, with both of its choices. Neither choice does
 * anything mechanical — the note says so in the King's own words — and that is
 * exactly why it is worth showing: the decision is not made here, it is made
 * later, alone, in the middle of a problem nobody can see you failing. */
export async function offerHand(prefetched) {
  ensureStyle();
  let hand = prefetched;
  if (!hand || hand.error) {
    try { hand = await api.hand(); } catch (e) { broke('NOBODY IS THERE', e); return; }
  }
  if (hand.error) { HOST.toast('NOBODY IS THERE', refusal(hand), 'red'); return; }

  const choices = hand.choices || ['Take it.', 'Leave it.'];
  const m = openModal(`
    <h2>${esc(hand.speaker || 'The Null King')}</h2>
    <div class="pt-h-lines" style="margin-top:12px">
      ${lines(hand.lines).map(l => `<p>${esc(l)}</p>`).join('')}
    </div>
    <p class="pt-h-note">${esc(hand.note || '')}</p>
    <div class="actions">
      <button class="btn primary" data-pt-hand-take>${esc(choices[0])}</button>
      <button class="btn" data-pt-hand-leave>${esc(choices[1] || 'Leave it.')}</button>
    </div>`);
  if (!m) return;

  // Both buttons close the modal and nothing else, because both of them do
  // exactly that in the fiction. The gauntlet is in the pack either way.
  modalActions(m, {
    '[data-pt-hand-take]': () => dismiss(),
    '[data-pt-hand-leave]': () => dismiss(),
  });
}

/* Whether the battle screen should show the button at all, and the sentence to
 * put in its place when it should not. The seal is the server's answer, never
 * a guess from the mode string. */
export async function handStatus() {
  let hand;
  try { hand = await api.hand(); } catch (e) { return { owned: false, sealed: true,
    message: 'The Hand is not answering.' }; }
  if (hand.error) return { owned: false, sealed: true, message: refusal(hand) };
  return {
    owned: Boolean(hand.owned),
    sealed: Boolean(hand.sealed),
    summary: hand.summary || {},
    /* hand_sealed() is true in every measured mode. The Hand does not refuse
     * there so much as fail to be present, and the server says that in one
     * line when it is actually used. */
    message: hand.sealed ? 'It is open and empty here.' : '',
  };
}

/* Wear it. Solves the encounter, pays loot and XP in full, and lowers the
 * skill's ceiling for good. `onSolved` gets the whole result so the battle
 * screen can run its normal victory path — this function's only job is the
 * notice, shown once, plainly, with nothing added to it. */
export async function useObligingHand({ onSolved } = {}) {
  ensureStyle();
  let r;
  try { r = await api.useHand(); } catch (e) { broke('NOTHING HAPPENS', e); return null; }
  if (isSealed(r)) { HOST.toast(sealedTitle(r), refusal(r), 'red'); return null; }
  if (r.error) { HOST.toast('NOTHING HAPPENS', refusal(r), 'red'); return null; }
  if (!r.solved) {
    // The sealed-mode answer is prose rather than an error, and it is good
    // prose. It gets shown as written.
    HOST.toast('THE HAND', r.reason || 'Nothing happens.', '');
    return r;
  }

  HOST.sfx('cast_ok');
  const m = openModal(`
    <h2>SOLVED</h2>
    <p class="small muted">Full loot. Full experience. Rank ${esc(r.rank)}, as
      promised.</p>
    <div class="pt-notice" style="margin-top:12px">${esc(r.notice)}</div>
    <div class="actions">
      <button class="btn primary" data-pt-close>GO ON</button>
    </div>`);
  if (m) {
    modalActions(m, {
      '[data-pt-close]': () => { dismiss(); if (onSolved) onSolved(r); },
    });
  } else if (onSolved) {
    onSolved(r);
  }
  return r;
}

/* ------------------------------------------------------------------ exports
 *
 * paintClassSelection / paintSkillTree / paintCompanions / paintRelicCodex are
 * the four screens. The rest is what the battle screen needs: beginEncounter()
 * at the top of enterBattle, petTick() on the signal tick, clearIntervention()
 * on the way out, showPetFound() and handStatus()/useObligingHand() from the
 * result path.
 */
export const partyScreens = Object.freeze({
  classes: paintClassSelection,
  tree: paintSkillTree,
  companions: paintCompanions,
  relics: paintRelicCodex,
});
