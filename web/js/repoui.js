/* MINI-REPO BATTLES — the working surface.
 *
 * Every other encounter in this game is one function and a blank body. This one
 * is somebody else's project: three to eight files, a suite that mostly passes,
 * and a ticket. So the interface is not a quiz with a bigger textarea — it is a
 * file tree, tabs, an editor, a RUN TESTS button and a clock, because that is
 * what the work actually looks like.
 *
 * Two rules this module is responsible for showing honestly:
 *
 *   The test files are READ ONLY. They are rendered as highlighted text with no
 *   textarea behind them and a lock on the tab. That is honesty in the
 *   interface and nothing more — the server cannot be fooled either way
 *   (minirepo.assemble lays the pristine suite down last, and the tamper check
 *   fails the attempt out loud), so this exists to stop a player wasting eight
 *   minutes on a trick that was never going to work.
 *
 *   Nothing here supplies an answer. The tree, the ticket and the suite are all
 *   the player was given, and the starting-file pointer is the server's to send
 *   or withhold — in Interview Mode it does not arrive at all, and this file
 *   never infers one.
 */
import { Editor, highlight } from './editor.js';

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};

const esc = (text) => String(text === undefined || text === null ? '' : text)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* A line diff of the actual player buffer. Large files use a lossless
 * delete/add block rather than allocating an unbounded quadratic matrix. */
export function lineDiff(before, after) {
  if (before === after) return [];
  const a = String(before).split('\n'), b = String(after).split('\n');
  let start = 0, endA = a.length, endB = b.length;
  while (start < endA && start < endB && a[start] === b[start]) start++;
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) { endA--; endB--; }
  const rows = [];
  let oldLine = 1, newLine = 1;
  const add = (kind, text) => rows.push({ kind, text,
    oldLine: kind === 'add' ? null : oldLine++, newLine: kind === 'remove' ? null : newLine++ });
  for (let i = 0; i < start; i++) add('same', a[i]);
  const n = endA - start, m = endB - start;
  if (n * m > 250000) {
    for (let i = start; i < endA; i++) add('remove', a[i]);
    for (let j = start; j < endB; j++) add('add', b[j]);
  } else {
    const lengths = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) {
      lengths[i][j] = a[start + i] === b[start + j] ? lengths[i + 1][j + 1] + 1
        : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
    let i = 0, j = 0;
    while (i < n || j < m) {
      if (i < n && j < m && a[start + i] === b[start + j]) { add('same', a[start + i]); i++; j++; }
      else if (i < n && (j >= m || lengths[i + 1][j] >= lengths[i][j + 1])) add('remove', a[start + i++]);
      else add('add', b[start + j++]);
    }
  }
  for (let i = endA; i < a.length; i++) add('same', a[i]);
  return rows;
}

export function investigationAllowed(payload) {
  const sealed = new Set([...(payload.sealed || []), ...((payload.seal || {}).sealed || [])]);
  return payload.mode !== 'interview' && !payload.interview_locked
    && !['HINTS', 'COACH', 'HOLDOUT'].some(cap => sealed.has(cap));
}

export function baselineFor(row) {
  return typeof row.original_body === 'string'
    ? { text: row.original_body, label: 'Original file supplied for this attempt.' }
    : { text: row.body, label: row.edited
      ? 'Saved draft loaded when this workspace opened. Earlier edits are not included in this comparison.'
      : 'Starting file supplied for this attempt.' };
}

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/* The brief is prose with blank lines in it, and it is the ticket. Paragraphs,
 * `code` and nothing else: a ticket is not a place for markup. */
function ticketHtml(text) {
  return String(text || '').split(/\n\s*\n/)
    .map(p => `<p>${esc(p).replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>')}</p>`).join('');
}

let nextPaneId = 0;
const STYLE_ID = 'repoui-style';
const STYLE = `
#screen-repo { flex-direction: column; }
.repo-shell { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.repo-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px; border-bottom: 2px solid var(--line, #333); }
.repo-head h2 { margin: 0; font-size: 13px; }
.repo-head .grow { flex: 1; }
.repo-clock { font-family: inherit; font-size: 12px; letter-spacing: 1px; }
.repo-clock.over { color: var(--orange, #e0a030); }
.repo-clock.out { color: var(--red, #d05050); }
.repo-body { display: flex; flex: 1; min-height: 0; }
.repo-tree { width: 210px; flex: none; overflow-y: auto; padding: 8px 0;
  border-right: 2px solid var(--line, #333); }
.repo-tree .dir { padding: 6px 10px 2px; font-size: 9px; letter-spacing: 1px;
  color: var(--ink-dim, #8a8a8a); }
.repo-tree .file { width: 100%; border: 0; background: none; color: inherit; text-align: left; font: inherit; display: flex; gap: 6px; align-items: baseline;
  padding: 9px 10px; min-height: 42px; cursor: pointer; font-size: 12px; }
.repo-tree .file:hover { background: rgba(255,255,255,.06); }
.repo-tree .file.active { background: rgba(255,255,255,.12); }
.repo-tree .file.locked { color: var(--ink-dim, #a4a4af); }
.repo-shell button:focus-visible, .repo-shell textarea:focus-visible, .repo-readonly:focus-visible { outline: 2px solid var(--gold, #d8b44a); outline-offset: -2px; }
.repo-tree .file .mark { width: 10px; flex: none; color: var(--gold, #d8b44a); }
.repo-work { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.repo-tabs { display: flex; overflow-x: auto; border-bottom: 2px solid var(--line, #333); }
.repo-tabs button { background: none; border: 0; border-right: 1px solid var(--line, #333);
  color: var(--ink-dim, #8a8a8a); padding: 7px 10px; font: inherit; font-size: 10px;
  cursor: pointer; white-space: nowrap; }
.repo-tabs button.active { color: var(--ink, #ddd); background: rgba(255,255,255,.08); }
.repo-pane { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.repo-readonly { flex: 1; min-height: 0; overflow: auto; margin: 0; padding: 10px 12px;
  font-family: 'Courier New', ui-monospace, monospace; font-size: 16px; line-height: 1.55; tab-size: 4; }
.repo-readonly-note { padding: 6px 12px; font-size: 10px;
  color: var(--ink-dim, #8a8a8a); border-bottom: 1px solid var(--line, #333); }
.repo-side { width: 330px; flex: none; overflow-y: auto; padding: 12px 14px;
  border-left: 2px solid var(--line, #333); }
.repo-side h3 { font-size: 10px; letter-spacing: 1px; margin: 14px 0 6px; }
.repo-side p { font-size: 11px; line-height: 1.6; }
.repo-side .rule { font-size: 10px; line-height: 1.7; color: var(--ink-dim, #8a8a8a); }
.repo-result { display: flex; gap: 8px; padding: 4px 0; font-size: 10px;
  line-height: 1.5; align-items: baseline; }
.repo-result .icon { width: 12px; flex: none; }
.repo-result.pass .icon { color: var(--green, #5aa050); }
.repo-result.fail .icon, .repo-result.exception .icon, .repo-result.missing .icon
  { color: var(--red, #d05050); }
.repo-result.timeout .icon { color: var(--orange, #e0a030); }
.repo-result .msg { color: var(--ink-dim, #8a8a8a); display: block; }
.repo-result .where { opacity: .65; }
.repo-editor-host { flex: 1; min-height: 0; display: flex; }
.repo-editor-host > .editor-shell { flex: 1; font-size: 16px; line-height: 1.55; }
.repo-editor-host .editor-input, .repo-editor-host .editor-highlight { font-size: 16px; line-height: 1.55; }
.repo-filebar { display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  border-bottom: 1px solid var(--line, #333); min-height: 42px; flex-wrap: wrap; }
.repo-filebar code { flex: 1; overflow-wrap: anywhere; font-size: 13px; }
.repo-diff { flex: 1; min-height: 0; overflow: auto; padding: 10px 0; }
.repo-diff-summary { margin: 0; padding: 4px 12px 10px; font-size: 12px; line-height: 1.5; }
.repo-diff-lines { display: table; min-width: 100%; border-collapse: collapse; font: 16px/1.55 'Courier New', ui-monospace, monospace; }
.repo-diff-line { display: table-row; }
.repo-diff-line.add { background: #153528; color: #c3edce; }
.repo-diff-line.remove { background: #44242c; color: #ffd0d5; }
.repo-diff-line .number, .repo-diff-line .sign, .repo-diff-line code { display: table-cell; white-space: pre; }
.repo-diff-line .number { color: #a6a4b2; padding: 0 8px; text-align: right; user-select: none; min-width: 28px; }
.repo-diff-line .sign { padding: 0 6px; user-select: none; }
.repo-diff-line code { padding: 0 12px 0 2px; font: inherit; tab-size: 4; }
.repo-investigation { border-top: 1px solid var(--line, #333); margin-top: 16px; padding-top: 8px; }
.repo-investigation label { display: block; margin: 12px 0 5px; font-size: 12px; }
.repo-investigation textarea { width: 100%; min-height: 90px; resize: vertical; box-sizing: border-box;
  background: #10121b; color: var(--ink, #eee); border: 1px solid var(--line, #555); padding: 8px;
  font: 16px/1.5 system-ui, sans-serif; }
.repo-investigation p { color: var(--ink-dim, #aaa); }
@media (max-width: 760px) {
  #screen-repo { overflow-y: auto; }
  .repo-shell { flex: none; min-height: 100%; }
  .repo-body { flex-direction: column; flex: none; }
  .repo-tree { width: auto !important; max-height: 170px; border-right: 0; border-bottom: 1px solid var(--line, #333); }
  .repo-work { min-height: 430px; height: 65vh; flex: none; }
  .repo-side { width: auto !important; border-left: 0; border-top: 1px solid var(--line, #333); overflow: visible; }
  .repo-head { padding: 10px; gap: 8px; }
  .repo-head button { min-height: 44px; }
  .repo-tabs button { min-height: 42px; font-size: 12px; }
  .repo-editor-host .editor-gutter { flex-basis: 32px; }
}

@media (max-width: 1100px) { .repo-side { width: 250px; } .repo-tree { width: 160px; } }
`;

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const node = document.createElement('style');
  node.id = STYLE_ID;
  node.textContent = STYLE;
  document.head.appendChild(node);
}

export class RepoUI {
  /* `payload` is exactly what /api/repo/start answered with. Nothing is
   * inferred from it: if the server withheld the starting-file pointer, the
   * pointer is not shown, and this file does not go looking for a substitute. */
  constructor(host, payload, hooks = {}) {
    ensureStyle();
    this.host = host;
    this.hooks = hooks;
    this.payload = payload;
    this.view = payload.repo || {};
    this.interview = payload.mode === 'interview';
    this.investigationOpen = investigationAllowed(payload);
    this.notes = { hypothesis: '', evidence: '', regression: '' };
    const started = (payload.encounter || {}).started_at;
    this.noteKey = this.investigationOpen && started ? `gauntlet:repo-notes:${this.view.id}:${started}` : null;
    if (this.noteKey) {
      try {
        const saved = JSON.parse(sessionStorage.getItem(this.noteKey) || '{}');
        for (const key of Object.keys(this.notes)) if (typeof saved[key] === 'string') this.notes[key] = saved[key].slice(0, 4000);
      } catch { /* Browser storage may be unavailable; the live worksheet still works. */ }
    }
    this.diffOpen = false;
    this.paneId = `repo-file-pane-${++nextPaneId}`;

    /* The model: one row per file, editable or not, with the body the player
     * currently has. A test body is kept verbatim and never touched, because it
     * is sent back with the submission and the server checks its hash. */
    this.files = [];
    for (const row of (this.view.files || [])) {
      // `original` is what this file looked like when the screen opened, which
      // on a resume is the player's own text. `resumed` remembers that the
      // server already considers it changed, so the dot cannot come off a file
      // that still differs from the one the repository handed out.
      this.files.push({ path: row.path, body: row.body, editable: true,
                        original: row.body, baseline: baselineFor(row), resumed: !!row.edited,
                        dirty: !!row.edited });
    }
    for (const row of (this.view.tests || [])) {
      this.files.push({ path: row.path, body: row.body, editable: false,
                        original: row.body, dirty: false });
    }
    this.byPath = new Map(this.files.map(f => [f.path, f]));
    this.open = [];
    this.active = null;
    this.results = null;
    this.busy = false;
    this.done = false;
    this.startedAt = Date.now() - (payload.elapsed_seconds || 0) * 1000;

    this.render();
    /* Where to start reading, when the server sent it. In Interview Mode it did
     * not, so the first editable file is opened instead — a neutral choice that
     * says nothing about where the defect is. */
    const first = this.view.start_file && this.byPath.has(this.view.start_file)
      ? this.view.start_file
      : (this.files.find(f => f.editable) || this.files[0] || {}).path;
    if (first) this.openFile(first);
    this.tick();
    this.timer = setInterval(() => this.tick(), 500);
  }

  destroy() {
    clearInterval(this.timer);
    this.timer = null;
    this.host.innerHTML = '';
  }

  /* ---------------- layout ---------------- */

  render() {
    const v = this.view;
    this.host.innerHTML = '';
    const shell = el('div', 'repo-shell');

    const head = el('div', 'repo-head');
    head.appendChild(el('h2', '', esc(v.title || 'MINI-REPO')));
    head.appendChild(el('span', 'tag gold', esc(v.difficulty || '')));
    head.appendChild(el('span', 'tag', `${v.file_count || this.files.length} FILES`));
    for (const shape of (v.shapes || [])) {
      head.appendChild(el('span', 'tag violet', shape.id.replace(/_/g, ' ')));
    }
    head.appendChild(el('span', 'grow'));
    this.clockEl = el('span', 'repo-clock', '00:00');
    head.appendChild(this.clockEl);
    this.runBtn = el('button', 'btn small', 'RUN TESTS ▶');
    this.runBtn.onclick = () => this.run();
    head.appendChild(this.runBtn);
    this.submitBtn = el('button', 'btn small primary', 'HAND IT BACK ✦');
    this.submitBtn.onclick = () => this.submit();
    head.appendChild(this.submitBtn);
    const leave = el('button', 'btn small danger', 'LEAVE');
    leave.onclick = () => this.hooks.onLeave && this.hooks.onLeave();
    head.appendChild(leave);
    shell.appendChild(head);

    const body = el('div', 'repo-body');
    this.treeEl = el('nav', 'repo-tree');
    this.treeEl.setAttribute('aria-label', 'Project files');
    body.appendChild(this.treeEl);

    const work = el('div', 'repo-work');
    this.tabsEl = el('div', 'repo-tabs');
    this.tabsEl.setAttribute('role', 'tablist');
    this.tabsEl.setAttribute('aria-label', 'Open files');
    work.appendChild(this.tabsEl);
    this.paneEl = el('div', 'repo-pane');
    this.paneEl.id = this.paneId;
    this.paneEl.setAttribute('role', 'tabpanel');
    work.appendChild(this.paneEl);
    body.appendChild(work);

    this.sideEl = el('aside', 'repo-side');
    body.appendChild(this.sideEl);
    shell.appendChild(body);
    this.host.appendChild(shell);

    this.paintTree();
    this.paintSide();
  }

  paintTree() {
    this.treeEl.innerHTML = '';
    this.treeButtons = [];
    const dirs = new Map();
    for (const f of this.files) {
      const cut = f.path.lastIndexOf('/');
      const dir = cut === -1 ? '.' : f.path.slice(0, cut);
      if (!dirs.has(dir)) dirs.set(dir, []);
      dirs.get(dir).push(f);
    }
    for (const [dir, rows] of dirs) {
      this.treeEl.appendChild(el('div', 'dir', esc(dir === '.' ? 'root' : dir + '/')));
      for (const f of rows) {
        const name = f.path.slice(f.path.lastIndexOf('/') + 1);
        const node = el('button', `file${f.editable ? '' : ' locked'}`
          + (this.active === f.path ? ' active' : ''),
          `<span class="mark">${f.dirty ? '●' : ''}</span>
           <span>${esc(name)}</span>
           <span class="grow"></span>
           ${f.editable ? '' : '<span class="where">🔒</span>'}`);
        node.type = 'button';
        node.setAttribute('aria-current', this.active === f.path ? 'true' : 'false');
        node.setAttribute('aria-label', f.path + (f.editable ? '' : ', read only') + (f.dirty ? ', modified' : ''));
        node.title = f.editable ? f.path : f.path + ' — read only';
        this.treeButtons.push(node);
        node.onkeydown = event => {
          const at = this.treeButtons.indexOf(node);
          const target = event.key === 'ArrowDown' ? Math.min(at + 1, this.treeButtons.length - 1)
            : event.key === 'ArrowUp' ? Math.max(at - 1, 0)
            : event.key === 'Home' ? 0 : event.key === 'End' ? this.treeButtons.length - 1 : -1;
          if (target >= 0) { event.preventDefault(); this.treeButtons[target].focus(); }
        };
        node.onclick = () => this.openFile(f.path);
        this.treeEl.appendChild(node);
      }
    }
  }

  paintTabs() {
    this.tabsEl.innerHTML = '';
    for (const path of this.open) {
      const f = this.byPath.get(path);
      const name = path.slice(path.lastIndexOf('/') + 1);
      const tab = el('button', path === this.active ? 'active' : '',
        `${f.editable ? '' : '🔒 '}${esc(name)}${f.dirty ? ' ●' : ''}`);
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      tab.id = `${this.paneId}-tab-${this.files.indexOf(f)}`;
      tab.setAttribute('aria-controls', this.paneId);
      if (path === this.active) this.paneEl.setAttribute('aria-labelledby', tab.id);
      tab.setAttribute('aria-selected', String(path === this.active));
      tab.tabIndex = path === this.active ? 0 : -1;
      tab.title = path;
      tab.onclick = () => this.openFile(path);
      tab.onkeydown = event => {
        const at = this.open.indexOf(path);
        const target = event.key === 'ArrowRight' ? (at + 1) % this.open.length
          : event.key === 'ArrowLeft' ? (at + this.open.length - 1) % this.open.length
          : event.key === 'Home' ? 0 : event.key === 'End' ? this.open.length - 1 : -1;
        if (target >= 0) {
          event.preventDefault(); this.openFile(this.open[target], { focus: false });
          this.tabsEl.children[target].focus();
        }
      };
      this.tabsEl.appendChild(tab);
    }
  }

  /* The ticket, the rules, and whatever the last run said. */
  paintSide() {
    const v = this.view;
    this.sideEl.innerHTML = '';
    this.sideEl.appendChild(el('div', 'section-title', 'THE TICKET'));
    this.sideEl.appendChild(el('div', '', ticketHtml(v.brief)));

    if (v.start_note) {
      this.sideEl.appendChild(el('div', 'section-title', 'WHERE TO START'));
      this.sideEl.appendChild(el('p', 'small',
        `<code>${esc(v.start_file)}</code> — ${esc(v.start_note)}`));
    }
    if ((v.targets || []).length) {
      this.sideEl.appendChild(el('div', 'section-title', 'WHAT DONE LOOKS LIKE'));
      const list = el('div', '');
      for (const id of v.targets) {
        list.appendChild(el('div', 'rule', `→ ${esc(id)}`));
      }
      this.sideEl.appendChild(list);
    } else if (this.interview) {
      this.sideEl.appendChild(el('p', 'rule',
        'Which tests are the acceptance criteria is not written down. Working '
        + 'that out from the ticket and the suite is the exercise.'));
    }

    this.sideEl.appendChild(el('div', 'section-title', 'THE RULES'));
    const rules = el('div', 'rule');
    for (const line of (v.rules || [])) rules.appendChild(el('div', '', '· ' + esc(line)));
    this.sideEl.appendChild(rules);

    if (this.investigationOpen) this.paintWorksheet();
    this.resultsEl = el('div', '');
    this.resultsEl.setAttribute('aria-live', 'polite');
    this.sideEl.appendChild(this.resultsEl);
    if (this.results) this.paintResults(this.results);
  }

  /* ---------------- files ---------------- */

  openFile(path, { focus = true } = {}) {
    const f = this.byPath.get(path);
    if (!f) return;
    this.stash();
    if (!this.open.includes(path)) this.open.push(path);
    this.active = path;
    this.paintTabs();
    this.paintTree();
    this.paintFile(f, focus);
  }

  paintFile(f, focus = false) {
    this.editor = null;
    this.paneEl.innerHTML = '';
    const bar = el('div', 'repo-filebar');
    bar.appendChild(el('code', '', esc(f.path)));
    if (f.editable) {
      const toggle = el('button', 'btn small', this.diffOpen ? 'BACK TO EDITOR' : 'VIEW CHANGES');
      toggle.type = 'button'; toggle.setAttribute('aria-pressed', String(this.diffOpen));
      toggle.onclick = () => { this.stash(); this.diffOpen = !this.diffOpen; this.paintFile(f, true); };
      bar.appendChild(toggle);
    }
    this.paneEl.appendChild(bar);
    if (f.editable && this.diffOpen) {
      this.paintDiff(f);
    } else if (f.editable) {
      const host = el('div', 'repo-editor-host');
      this.paneEl.appendChild(host);
      this.editor = new Editor(host, {
        onRun: () => this.run(),
        onSubmit: () => this.submit(),
        /* The contextual reminders are a teaching aid, and a measured run does
         * not get one. Same flag the ordinary battle editor honours. */
        assist: !this.interview,
      });
      this.editor.value = f.body;
      if (f.editorState) {
        this.editor.input.setSelectionRange(f.editorState.start, f.editorState.end);
        this.editor.input.scrollTop = f.editorState.top;
        this.editor.input.scrollLeft = f.editorState.left;
        this.editor.syncScroll();
      }
      this.editor.input.setAttribute('aria-label', `Edit ${f.path}`);
      this.editor.input.addEventListener('input', () => {
        const row = this.byPath.get(this.active);
        if (!row) return;
        row.body = this.editor.value;
        const dirty = row.resumed || row.body !== row.original;
        if (dirty !== row.dirty) { row.dirty = dirty; this.paintTabs(); this.paintTree(); }
      });
      if (focus) this.editor.focus();
    } else {
      this.editor = null;
      this.paneEl.appendChild(el('div', 'repo-readonly-note',
        'READ ONLY — this is the suite. Editing or deleting a test file ends '
        + 'the attempt; the server keeps its own copy and checks.'));
      const pre = el('pre', 'repo-readonly');
      pre.tabIndex = 0;
      pre.setAttribute('aria-label', `${f.path}, read-only test file`);
      pre.innerHTML = `<code>${highlight(f.body)}</code>`;
      this.paneEl.appendChild(pre);
      if (focus) pre.focus();
    }
  }

  paintWorksheet() {
    const section = el('section', 'repo-investigation');
    section.appendChild(el('h3', '', 'INVESTIGATION NOTES'));
    section.appendChild(el('p', '', 'Your own notes, not graded. Keep a hypothesis, cite what you observed, then name a regression check.'));
    const prompts = {
      hypothesis: 'Hypothesis — what may explain the failure?',
      evidence: 'Evidence — which file, line or test result supports it?',
      regression: 'Regression — what result would check the fix and preserve existing behavior?',
    };
    for (const [key, prompt] of Object.entries(prompts)) {
      const label = el('label', '', esc(prompt));
      const input = el('textarea', '');
      input.value = this.notes[key]; input.maxLength = 4000;
      input.setAttribute('aria-label', prompt);
      input.addEventListener('input', () => {
        this.notes[key] = input.value;
        if (this.noteKey) try { sessionStorage.setItem(this.noteKey, JSON.stringify(this.notes)); } catch { /* Remains in this open workspace. */ }
      });
      label.appendChild(input); section.appendChild(label);
    }
    section.appendChild(el('p', 'rule', 'Notes stay in this open workspace; this browser tab also retains them for this attempt when session storage is available.'));
    this.sideEl.appendChild(section);
  }

  paintDiff(f) {
    const host = el('div', 'repo-diff');
    host.tabIndex = 0; host.setAttribute('aria-label', `Changes in ${f.path}`);
    const changes = lineDiff(f.baseline.text, f.body);
    const added = changes.filter(r => r.kind === 'add').length;
    const removed = changes.filter(r => r.kind === 'remove').length;
    host.appendChild(el('p', 'repo-diff-summary', `${esc(f.baseline.label)}<br>`
      + (changes.length ? `${added} added, ${removed} removed. Left numbers: baseline; right numbers: current buffer.` : 'No changes relative to this baseline.')));
    if (changes.length) {
      const lines = el('div', 'repo-diff-lines');
      for (const row of changes) {
        const line = el('div', `repo-diff-line ${row.kind}`);
        line.appendChild(el('span', 'number', row.oldLine === null ? '' : String(row.oldLine)));
        line.appendChild(el('span', 'number', row.newLine === null ? '' : String(row.newLine)));
        line.appendChild(el('span', 'sign', row.kind === 'add' ? '+' : row.kind === 'remove' ? '−' : ' '));
        const code = el('code'); code.textContent = row.text || ' ';
        line.appendChild(code); lines.appendChild(line);
      }
      host.appendChild(lines);
    }
    this.paneEl.appendChild(host);
    host.focus();
  }

  /* Whatever is in the editor belongs to the file that is open, not to the one
   * about to be. Called before every tab change and before every request. */
  stash() {
    if (!this.editor || !this.active) return;
    const row = this.byPath.get(this.active);
    if (row && row.editable) {
      row.body = this.editor.value;
      row.editorState = { start: this.editor.input.selectionStart, end: this.editor.input.selectionEnd,
                          top: this.editor.input.scrollTop, left: this.editor.input.scrollLeft };
      row.dirty = row.resumed || row.body !== row.original;
    }
  }

  /* The whole working tree, which is what the server grades. Test bodies are
   * included exactly as they were handed out — the server needs them present to
   * tell an untouched suite from a deleted one. */
  tree() {
    this.stash();
    const out = {};
    for (const f of this.files) out[f.path] = f.body;
    return out;
  }

  /* ---------------- the clock ---------------- */

  tick() {
    const elapsed = (Date.now() - this.startedAt) / 1000;
    const limit = this.payload.clock_seconds;
    const target = this.payload.target_seconds || 0;
    // The shell has a clock of its own during a measured run, and two clocks
    // disagreeing is worse than one.
    if (this.hooks.onTick) this.hooks.onTick(elapsed, limit || 0);
    if (limit) {
      const left = limit - elapsed;
      this.clockEl.textContent = `${fmtTime(left)} left`;
      this.clockEl.className = 'repo-clock'
        + (left <= 0 ? ' out' : left < 300 ? ' over' : '');
    } else {
      this.clockEl.textContent = `${fmtTime(elapsed)} / ${fmtTime(target)}`;
      this.clockEl.className = 'repo-clock' + (elapsed > target ? ' over' : '');
    }
  }

  /* ---------------- running and handing back ---------------- */

  /* The fight is over: the server closed the encounter, so there is nothing
   * left to run against. Said here rather than left for the player to discover
   * by pressing a button that now answers "no mini-repo is open". */
  finish(message) {
    this.done = true;
    clearInterval(this.timer);
    this.timer = null;
    this.runBtn.disabled = true;
    this.submitBtn.disabled = true;
    this.clockEl.textContent = message || 'HANDED BACK';
    this.clockEl.className = 'repo-clock';
  }

  /* Both buttons go down together — a repository runs one suite at a time —
   * and only the one that is working says so. */
  lock(on, which) {
    if (this.done) return;
    this.busy = on;
    this.runBtn.disabled = on;
    this.submitBtn.disabled = on;
    this.runBtn.textContent = on && which === 'run' ? 'RUNNING…' : 'RUN TESTS ▶';
    this.submitBtn.textContent = on && which === 'submit'
      ? 'GRADING…' : 'HAND IT BACK ✦';
  }

  async run() {
    if (this.busy || this.done || !this.hooks.onRun) return;
    this.lock(true, 'run');
    try {
      const report = await this.hooks.onRun(this.tree());
      if (report) this.showRun(report);
    } finally {
      this.lock(false);
    }
  }

  async submit() {
    if (this.busy || this.done || !this.hooks.onSubmit) return;
    this.lock(true, 'submit');
    try {
      await this.hooks.onSubmit(this.tree());
    } finally {
      this.lock(false);
    }
  }

  /* An ungraded run. Same rows the grader will produce, minus the judgement. */
  showRun(report) {
    if (!report.tests) {
      /* Two different shapes arrive here: a refusal from the server, whose
       * `error` is a sentence, and a sandbox report, whose `error` is an
       * object. Both mean the same thing to the player. */
      const why = typeof report.error === 'string'
        ? (report.message || report.error)
        : ((report.error || {}).message || '');
      this.results = { headline: 'THE PROJECT DID NOT RUN',
                       tone: 'red', lines: [], note: why };
    } else {
      const passed = report.passed || 0;
      const total = report.total || 0;
      this.results = {
        headline: `${passed} / ${total} GREEN`,
        tone: passed === total && total ? 'green' : 'red',
        lines: (report.tests || []).map(t => ({
          name: t.name, status: t.status, message: t.message, ms: t.ms,
          target: !!t.target,
        })),
        note: report.stderr ? report.stderr.slice(-800) : '',
      };
    }
    this.paintResults(this.results);
  }

  paintResults(results) {
    const host = this.resultsEl;
    host.innerHTML = '';
    host.appendChild(el('div', 'section-title', 'THE SUITE'));
    const colour = results.tone === 'green' ? 'var(--green, #5aa050)'
      : 'var(--red, #d05050)';
    host.appendChild(el('div', 'small', `<b style="color:${colour}">`
      + `${esc(results.headline)}</b>`));
    for (const line of results.lines) {
      const icon = line.status === 'pass' ? '✔'
        : line.status === 'timeout' ? '⧗'
        : line.status === 'missing' ? '∅' : '✖';
      const cut = line.name.indexOf('::');
      const where = cut === -1 ? line.name : line.name.slice(0, cut);
      const what = cut === -1 ? '' : line.name.slice(cut + 2);
      host.appendChild(el('div', `repo-result ${line.status}`,
        `<span class="icon">${icon}</span>
         <span><span class="where">${esc(where)} ::</span> ${esc(what)}
         ${line.target ? '<span class="tag gold">TARGET</span>' : ''}
         ${line.message ? `<span class="msg">${esc(line.message)}</span>` : ''}</span>`));
    }
    if (results.note) {
      host.appendChild(el('pre', 'spell-body', esc(results.note)));
    }
  }
}
