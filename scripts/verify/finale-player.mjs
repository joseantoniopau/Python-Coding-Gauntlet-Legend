/* The real shared UI player and main.js staged adapter, with a deterministic
 * DOM/rAF clock. No browser, HTTP server, audio device or save is touched. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { installStub } from './stub.mjs';
installStub();

const createElement = document.createElement.bind(document);
let now = 0, nextRaf = 0;
const frames = new Map(), listeners = new Map();
globalThis.performance = { now: () => now };
globalThis.requestAnimationFrame = fn => { frames.set(++nextRaf, fn); return nextRaf; };
globalThis.cancelAnimationFrame = id => frames.delete(id);
globalThis.addEventListener = (name, fn) => { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(fn); };
globalThis.removeEventListener = (name, fn) => listeners.get(name)?.delete(fn);
globalThis.fetch = () => { throw new Error('The cinematic test must never contact an API'); };
function frameAt(ms) {
  now = ms;
  const callbacks = [...frames.values()]; frames.clear();
  for (const fn of callbacks) fn(now);
}
class Node {
  constructor(tag) {
    this.tagName = tag; this.id = ''; this.children = []; this.parentElement = null;
    this.dataset = {}; this.style = { setProperty() {} }; this.attributes = {};
    const classes = new Set();
    this.classList = { add: c => classes.add(c), remove: c => classes.delete(c),
      contains: c => classes.has(c), toggle(c, value) { const use = value ?? !classes.has(c); if (use) classes.add(c); else classes.delete(c); } };
  }
  get isConnected() { return this === document.body || this === document.head || !!this.parentElement?.isConnected; }
  appendChild(node) { node.parentElement = this; this.children.push(node); return node; }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(n => n !== this); this.parentElement = null; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  focus() { document.activeElement = this; }
  scrollIntoView() {}
  set innerHTML(value) {
    this.html = value; this.children = [];
    for (const match of value.matchAll(/<(\w+)[^>]*id="([^"]+)"[^>]*>/g)) {
      const node = document.createElement(match[1]); node.id = match[2];
      if (match[1] === 'canvas') {
        node.width = Number(/width="(\d+)"/.exec(match[0])?.[1] || 960);
        node.height = Number(/height="(\d+)"/.exec(match[0])?.[1] || 540);
      }
      this.appendChild(node);
    }
  }
  get innerHTML() { return this.html || ''; }
  querySelector(selector) {
    for (const child of this.children) {
      if (selector === '#' + child.id) return child;
      const nested = child.querySelector?.(selector); if (nested) return nested;
    }
    return null;
  }
}
document.createElement = tag => tag === 'canvas' ? createElement(tag) : new Node(tag);
document.body = new Node('body'); document.head = new Node('head');
document.querySelector = selector => document.body.querySelector(selector) || document.head.querySelector(selector);
document.getElementById = id => document.querySelector('#' + id);
const { api } = await import('../../web/js/api.js');
const { audio } = await import('../../web/js/audio.js');
const { HOST } = await import('../../web/js/uikit.js');
const player = await import('../../web/js/finaleui.js');
let codas = 0, backs = 0;
api.markCodaSeen = () => { codas++; return Promise.resolve({}); };
audio.play = audio.stop = audio.sfx = () => {};
HOST.back = () => { backs++; }; HOST.sfx = () => {};
const scene = id => ({ title: 'Fictional player contract test', duration_ms: 200,
  beats: [
    { id: 'opening', at_ms: 0, duration_ms: 100, stage: ['black'], lines: [], camera: { move: 'HOLD' } },
    { id, at_ms: 100, duration_ms: 100, stage: ['black'], lines: [{ text: '>>> ', kind: 'code' }], camera: { move: 'HOLD' }, fx: ['cursor_blink'] },
  ] });

// A pause consumes wall time, while every beat and completion fires once.
for (const id of ['the_prompt_stays', 'the_prompt_waits']) {
  const prior = codas; let done = 0;
  now = 0;
  const run = player.playScene(scene(id), { reducedMotion: true }, () => done++);
  assert(run.active);
  assert.equal(document.body.children.at(-1).getAttribute('role'), 'dialog');
  frameAt(50);
  document.getElementById('fin-pause').onclick();
  frameAt(1000); assert.equal(codas, prior, 'Pause cannot reach the coda');
  document.getElementById('fin-pause').onclick();
  frameAt(1051); assert.equal(codas, prior + 1, id + ' marks the coda');
  frameAt(1075); assert.equal(codas, prior + 1, 'Repeated frames do not repeat bookkeeping');
  frameAt(1151); assert.equal(done, 1, 'Completion returns to the report exactly once');
  run.stop(); run.stop(); frameAt(2000); assert.equal(done, 1);
  assert(!run.active); assert.equal(document.getElementById('fin-art'), null);
  assert.equal(listeners.get('keydown')?.size || 0, 0, 'Completion disposes the key listener');
}

// Escape and explicit skip share the exact same cancellation path.
for (const kind of ['escape', 'button', 'stop']) {
  let done = 0; const prior = codas; now = 0;
  const run = player.playScene(scene('the_prompt_stays'), {}, ({ skipped }) => { assert(skipped); done++; });
  if (kind === 'escape') for (const listener of [...listeners.get('keydown')]) listener({ key: 'Escape', preventDefault() {} });
  if (kind === 'button') document.getElementById('fin-skip').onclick();
  if (kind === 'stop') run.stop();
  frameAt(1000); run.stop(); assert.equal(done, 1); assert.equal(codas, prior, 'Skipping cannot mark the coda');
}

// Demonstration payloads stay read-only even if accidentally handed to the UI.
now = 0; const beforeDemo = codas;
const demo = player.playScene({ ...scene('the_prompt_stays'), demonstration: true }, {}, () => {});
frameAt(201); demo.stop(); assert.equal(codas, beforeDemo);
let emptyDone = 0; player.playScene(null, {}, () => emptyDone++).stop(); assert.equal(emptyDone, 1);
now = 0; let teardownDone = 0;
player.playScene(scene('the_prompt_stays'), {}, () => teardownDone++);
player.leave(); frameAt(1000); assert.equal(teardownDone, 0, 'Navigation teardown cannot reopen an old report');

// Execute the actual bounded main.js adapter, not a second implementation of it.
const source = readFileSync(new URL('../../web/js/main.js', import.meta.url), 'utf8');
const start = source.indexOf('let ENDING = null;');
const end = source.indexOf('/* What just happened to the world', start);
assert(start >= 0 && end > start);
const look = { class_id: 'warden', _gear: { weapon: null } };
let handed = null;
const context = { G: { state: { hero: look, settings: { reduced_motion: true } } },
  finaleui: { playScene(s, opts, done) { handed = { s, opts }; return player.playScene(s, opts, done); } } };
vm.runInNewContext(source.slice(start, end) + '\nthis.adapter = { playEndingCutscene, stopEndingCutscene };', context);
let returned = 0; now = 0;
const staged = { cutscene: scene('the_prompt_waits') };
context.adapter.playEndingCutscene(staged, () => returned++);
assert.equal(handed.s, staged.cutscene, 'The staged script is passed through unchanged');
assert.equal(handed.opts.look, look); assert.equal(handed.opts.gear, look._gear);
assert.equal(handed.opts.reducedMotion, true);
frameAt(201); context.adapter.stopEndingCutscene(); assert.equal(returned, 1);
now = 0; context.adapter.playEndingCutscene(staged, () => returned++);
context.adapter.stopEndingCutscene(); context.adapter.stopEndingCutscene(); assert.equal(returned, 2);
player.leave(); frameAt(1000);
assert.equal(backs, 0, 'Staged endings return via their report callback, not a separate world navigation');
console.log(JSON.stringify({ ok: true, codas: 'success and failure; once each', dismissals: ['completion', 'Escape', 'skip button', 'controller stop', 'navigation teardown'], pause: 'wall time excluded', stagedAdapter: 'actual main.js functions executed', networkCalls: 0 }, null, 2));
