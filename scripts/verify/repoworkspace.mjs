/* Model/DOM event checks for RepoUI. This minimal DOM exercises the shipped
 * component and Editor; it does not claim browser layout or accessibility audit. */
import assert from 'node:assert/strict';

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this.events = {}; this.style = {}; this.className = ''; this.value = ''; this.selectionStart = this.selectionEnd = 0; this.scrollTop = this.scrollLeft = 0; }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  setAttribute(name, value) { this.attrs[name] = String(value); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this.attrs[name] ?? null; }
  get classList() { return { add: (...items) => { this.className = [...new Set([...this.className.split(' '), ...items])].join(' '); } }; }
  set innerHTML(html) {
    this.children = []; this.html = String(html); const stack = [this];
    for (const match of String(html).matchAll(/<(\/?)([a-z][\w-]*)([^>]*)>/gi)) {
      if (match[1]) { if (stack.length > 1) stack.pop(); continue; }
      const child = new Element(match[2]);
      for (const attr of match[3].matchAll(/([\w-]+)="([^"]*)"/g)) child.setAttribute(attr[1], attr[2]);
      stack.at(-1).appendChild(child);
      if (!['input','br','hr','img'].includes(match[2])) stack.push(child);
    }
  }
  get innerHTML() { return this.html || ''; }
  querySelector(selector) {
    const parts = selector.split(' ');
    const match = (node, part) => part.startsWith('.') ? node.className.split(' ').includes(part.slice(1)) : node.tagName === part.toUpperCase();
    const walk = node => { for (const child of node.children) {
      if (match(child, parts[0])) { if (parts.length === 1) return child; const hit = child.querySelector(parts.slice(1).join(' ')); if (hit) return hit; }
      const hit = walk(child); if (hit) return hit;
    } return null; };
    return walk(this);
  }
  addEventListener(name, handler) { (this.events[name] ||= []).push(handler); }
  emit(name, props = {}) { const event = { target: this, preventDefault() { this.prevented = true; }, ...props }; for (const fn of this.events[name] || []) fn(event); this[`on${name}`]?.(event); return event; }
  focus() { document.activeElement = this; }
  setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
}
const head = new Element('head'), body = new Element('body');
globalThis.document = { createElement: tag => new Element(tag), head, body,
  getElementById: id => head.children.find(n => n.id === id) || null, activeElement: null };
const saved = new Map();
globalThis.sessionStorage = { getItem: k => saved.get(k) || null, setItem: (k, v) => saved.set(k, v) };
const { RepoUI, lineDiff, baselineFor, investigationAllowed } = await import('../../web/js/repoui.js');

// Independent reconstruction proves that every before/after line survives,
// including deletion, insertion, duplicate lines, final newlines and long files.
for (const [before, after] of [['a\nb\nc\n', 'a\nx\nc\n'], ['', 'x'], ['a', ''],
  ['same\nsame\nb', 'same\nb\nsame'], ['a\n', 'a'],
  [Array.from({length: 600}, (_, i) => `old${i}`).join('\n'), Array.from({length: 600}, (_, i) => `new${i}`).join('\n')]]) {
  const rows = lineDiff(before, after);
  assert.equal(rows.filter(r => r.kind !== 'add').map(r => r.text).join('\n'), before);
  assert.equal(rows.filter(r => r.kind !== 'remove').map(r => r.text).join('\n'), after);
}
assert.deepEqual(lineDiff('unchanged', 'unchanged'), []);
assert.match(baselineFor({body:'saved',edited:true}).label, /Earlier edits are not included/);
assert.equal(baselineFor({body:'saved',edited:true,original_body:'start'}).text, 'start');
assert.equal(investigationAllowed({mode:'interview'}), false);
assert.equal(investigationAllowed({mode:'adventure',seal:{sealed:['COACH']}}), false);
assert.equal(investigationAllowed({mode:'adventure',sealed:['HINTS']}), false);
assert.equal(investigationAllowed({mode:'adventure',sealed:['HOLDOUT']}), false);
assert.equal(investigationAllowed({mode:'adventure',sealed:[]}), true);

const payload = { mode:'adventure', encounter:{started_at:123}, target_seconds:300,
  repo:{id:'fixture', title:'Investigation', brief:'Find a regression.', files:[
    {path:'app/main.py',body:'x = 1\n'}, {path:'app/util.py',body:'def value():\n    return 2\n',edited:true}],
    tests:[{path:'tests/test_main.py',body:'def test_value():\n    assert True\n'}]}};
const host = new Element('div');
let submitted, handedBack;
const ui = new RepoUI(host, payload, {onRun: async files => { submitted = files; return {passed:1,total:1,tests:[{name:'tests/test_main.py::test_value',status:'pass'}]}; }, onSubmit: async files => { handedBack = files; }});
assert.equal(ui.treeButtons.length, 3);
assert.ok(ui.treeButtons.every(b => b.tagName === 'BUTTON'));
const event = ui.treeButtons[0].emit('keydown', {key:'ArrowDown'});
assert.ok(event.prevented); assert.equal(document.activeElement, ui.treeButtons[1]);
ui.treeButtons[2].emit('keydown', {key:'Home'}); assert.equal(document.activeElement, ui.treeButtons[0]);
ui.editor.value = 'x = 3\n'; ui.editor.input.emit('input');
assert.equal(ui.tree()['app/main.py'], 'x = 3\n');
const suite = ui.tree()['tests/test_main.py'];
ui.editor.input.setSelectionRange(3, 4);
ui.editor.input.scrollTop = 40;
ui.diffOpen = true; ui.openFile('app/main.py');
assert.equal(ui.editor, null); assert.ok(ui.paneEl.querySelector('.repo-diff'));
assert.ok(ui.paneEl.querySelector('.repo-diff-line').tagName === 'DIV');
assert.equal(ui.tree()['tests/test_main.py'], suite);
ui.openFile('app/util.py');
assert.match(ui.paneEl.querySelector('.repo-diff-summary').innerHTML, /Earlier edits are not included/);
ui.openFile('tests/test_main.py');
assert.equal(ui.editor, null); assert.ok(ui.paneEl.querySelector('.repo-readonly'));
assert.equal(ui.paneEl.querySelector('.repo-readonly').tabIndex, 0);
assert.equal(ui.paneEl.querySelector('.repo-readonly').querySelector('textarea'), null);
ui.diffOpen = false; ui.openFile('app/main.py');
assert.equal(ui.editor.value, 'x = 3\n');
assert.equal(ui.editor.input.selectionStart, 3);
assert.equal(ui.editor.input.scrollTop, 40);
const worksheet = ui.sideEl.querySelector('.repo-investigation');
assert.ok(worksheet); const note = worksheet.querySelector('textarea');
note.value = 'The count changes after reset.'; note.emit('input');
assert.equal(JSON.parse(saved.get(ui.noteKey)).hypothesis, note.value);
ui.tabsEl.children[0].emit('keydown', {key:'ArrowRight'});
assert.equal(ui.active, 'app/util.py');
assert.equal(document.activeElement, ui.tabsEl.children[1]);
assert.equal(ui.tabsEl.children[1].getAttribute('aria-selected'), 'true');
await ui.run(); assert.equal(submitted['tests/test_main.py'], suite); assert.equal(submitted['app/main.py'], 'x = 3\n');
await ui.submit(); assert.deepEqual(handedBack, submitted);
assert.equal(Object.keys(handedBack).length, 3, 'investigation notes must not enter the submitted working tree');
ui.destroy();
const resumed = new RepoUI(new Element('div'), payload);
assert.equal(resumed.notes.hypothesis, note.value); resumed.destroy();
const sealedUI = new RepoUI(new Element('div'), {...payload,mode:'interview'});
assert.equal(sealedUI.sideEl.querySelector('.repo-investigation'), null);
assert.equal(sealedUI.editor.assist, false); sealedUI.destroy();
console.log('Repo workspace: diff reconstruction, keyboard file buttons, real Editor edits, immutable suite submission, resumed baseline, local worksheet persistence and sealed-mode absence passed. Browser layout remains a separate check.');
