/* A keyboard-first Python editor with syntax highlighting, built from a textarea
 * plus a highlight layer. No external editor library, so it works offline and
 * starts instantly.
 *
 * Interview Mode passes `assist: false`, which disables every completion and
 * contextual reminder. That flag is honoured here, and the server refuses hints
 * independently — the guarantee does not rest on the UI alone.
 */
/* The fill-in-the-blank marker. 59 starters ship with one and it is not Python:
 * it is a slot the player replaces. It is highlighted as such, the cursor lands
 * on it, and main.js explains it once the first time a player meets one. */
export const BLANK = '__BLANK__';

const KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break',
  'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
  'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal',
  'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
]);

const BUILTINS = new Set([
  'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float', 'int',
  'len', 'list', 'map', 'max', 'min', 'range', 'reversed', 'round', 'set',
  'sorted', 'str', 'sum', 'tuple', 'zip', 'print', 'isinstance', 'type',
  'Counter', 'defaultdict', 'deque', 'heapq', 'bisect', 'OrderedDict', 'self',
]);

function escapeHtml(text) {
  return text.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

export function highlight(source) {
  const out = [];
  let i = 0;
  const n = source.length;
  while (i < n) {
    const ch = source[i];

    if (ch === '#') {
      let j = i;
      while (j < n && source[j] !== '\n') j++;
      out.push(`<span class="tok-comment">${escapeHtml(source.slice(i, j))}</span>`);
      i = j;
      continue;
    }

    if (ch === '"' || ch === "'") {
      const triple = source.slice(i, i + 3);
      if (triple === '"""' || triple === "'''") {
        let j = source.indexOf(triple, i + 3);
        j = j === -1 ? n : j + 3;
        out.push(`<span class="tok-string">${escapeHtml(source.slice(i, j))}</span>`);
        i = j;
        continue;
      }
      let j = i + 1;
      while (j < n && source[j] !== ch) {
        if (source[j] === '\\') j++;
        if (source[j] === '\n') break;
        j++;
      }
      j = Math.min(j + 1, n);
      out.push(`<span class="tok-string">${escapeHtml(source.slice(i, j))}</span>`);
      i = j;
      continue;
    }

    if (/[0-9]/.test(ch)) {
      let j = i;
      while (j < n && /[0-9_.xXbBoOeE+-]/.test(source[j])) {
        if (/[+-]/.test(source[j]) && !/[eE]/.test(source[j - 1])) break;
        j++;
      }
      out.push(`<span class="tok-number">${escapeHtml(source.slice(i, j))}</span>`);
      i = j;
      continue;
    }

    if (/[A-Za-z_]/.test(ch)) {
      let j = i;
      while (j < n && /[A-Za-z0-9_]/.test(source[j])) j++;
      const word = source.slice(i, j);
      let cls = '';
      if (word === BLANK) cls = 'tok-blank';
      else if (KEYWORDS.has(word)) cls = 'tok-keyword';
      else if (BUILTINS.has(word)) cls = 'tok-builtin';
      else if (source[j] === '(') cls = 'tok-call';
      else if (source.slice(i - 4, i) === 'def ') cls = 'tok-def';
      out.push(cls ? `<span class="${cls}">${escapeHtml(word)}</span>` : escapeHtml(word));
      i = j;
      continue;
    }

    if ('+-*/%=<>!&|^~'.includes(ch)) {
      out.push(`<span class="tok-op">${escapeHtml(ch)}</span>`);
      i++;
      continue;
    }

    out.push(escapeHtml(ch));
    i++;
  }
  return out.join('');
}

export class Editor {
  constructor(root, { onRun, onSubmit, assist = true } = {}) {
    this.root = root;
    this.onRun = onRun;
    this.onSubmit = onSubmit;
    this.assist = assist;
    // The status line under the editor carries the caret position and the one
    // keyboard hint, and it was never on screen: .editor-shell is height:100%
    // of its host and the status bar flowed off the bottom of it, clipped by
    // #battle-main. The host is a column, the shell takes what is left and the
    // status line keeps its own row.
    this.root.classList.add('editor-root');
    this.root.innerHTML = `
      <div class="editor-shell">
        <div class="editor-gutter" aria-hidden="true"></div>
        <div class="editor-stack">
          <pre class="editor-highlight" aria-hidden="true"><code></code></pre>
          <textarea class="editor-input" spellcheck="false" autocomplete="off"
            autocapitalize="off" autocorrect="off" aria-label="Write your Python here"
            placeholder="Write your Python here…"></textarea>
        </div>
      </div>
      <div class="editor-status">
        <span class="editor-pos">Ln 1, Col 1</span>
        <span class="editor-hintline"></span>
      </div>`;
    this.gutter = root.querySelector('.editor-gutter');
    this.highlightEl = root.querySelector('.editor-highlight code');
    this.input = root.querySelector('.editor-input');
    this.posEl = root.querySelector('.editor-pos');
    this.hintEl = root.querySelector('.editor-hintline');

    this.input.addEventListener('input', () => this.refresh());
    this.input.addEventListener('scroll', () => this.syncScroll());
    this.input.addEventListener('keydown', (e) => this.onKey(e));
    this.input.addEventListener('click', () => this.updatePos());
    this.input.addEventListener('keyup', () => this.updatePos());
  }

  get value() { return this.input.value; }

  set value(text) {
    this.input.value = text;
    this.refresh();
  }

  focus() { this.input.focus(); }

  /* Drop a selection and leave the caret where it started.
   *
   * reset() SELECTS the __BLANK__ slot so the first keystroke replaces it, and
   * that is right while the player is typing on purpose. It is wrong when the
   * caret is being handed BACK — after a modal or a boss taunt — because the
   * first keystroke to arrive is then usually the tail of the SPACE taps that
   * dismissed the thing, and a space landing on a selected slot DELETES it,
   * silently, with no message and nothing left to say what used to be there.
   * main.js:focusEditor() collapses on the way back in for exactly that. The
   * marker survives, the caret is still sitting on it, and a stray key can at
   * worst insert next to it. */
  collapseSelection() {
    const at = this.input.selectionStart;
    this.input.setSelectionRange(at, at);
    return this;
  }

  setAssist(on) {
    this.assist = on;
    if (!on) this.hintEl.textContent = '';
  }

  reset(starter) {
    this.value = starter || '';
    // A starter with a slot in it is asking for exactly one thing. Select the
    // first slot so the very first keystroke replaces it.
    const slot = this.value.indexOf(BLANK);
    if (slot !== -1) {
      this.input.setSelectionRange(slot, slot + BLANK.length);
      if (this.assist) {
        this.hintEl.textContent = `${BLANK} is a slot, not Python — replace the `
          + 'marker with the expression that belongs there.';
      }
    } else {
      this.input.setSelectionRange(this.value.length, this.value.length);
    }
    this.focus();
  }

  /* True while an unreplaced slot is still sitting in the buffer. */
  hasBlank() { return this.input.value.includes(BLANK); }

  syncScroll() {
    const pre = this.root.querySelector('.editor-highlight');
    pre.scrollTop = this.input.scrollTop;
    pre.scrollLeft = this.input.scrollLeft;
    this.gutter.scrollTop = this.input.scrollTop;
  }

  refresh() {
    const text = this.input.value;
    this.highlightEl.innerHTML = highlight(text) + '\n';
    const lines = text.split('\n').length;
    let g = '';
    for (let i = 1; i <= lines; i++) g += i + '\n';
    this.gutter.textContent = g;
    this.updatePos();
    this.syncScroll();
  }

  updatePos() {
    const upto = this.input.value.slice(0, this.input.selectionStart);
    const lines = upto.split('\n');
    this.posEl.textContent = `Ln ${lines.length}, Col ${lines[lines.length - 1].length + 1}`;
    // An empty buffer is the moment a player is most likely to be looking for
    // the place to start, and it is the one moment the syntax reminders have
    // nothing to say. Say the two keys instead — Interview Mode included,
    // because where the keyboard is is not a hint about the answer.
    if (!this.input.value) {
      this.hintEl.textContent = 'This is the spell. Ctrl/⌘+Enter runs it against '
        + 'the visible trials; Shift+Ctrl/⌘+Enter casts it.';
      return;
    }
    if (this.assist) this.showContextualReminder(lines[lines.length - 1]);
  }

  /* Adventure Mode only: a one-line syntax reminder, never an algorithm hint. */
  showContextualReminder(line) {
    const reminders = [
      [/for\s+\w+\s*,\s*\w+\s+in\s+enumerate\s*\($/, 'enumerate(items, start=0) yields (index, value)'],
      [/\.get\($/, 'dict.get(key, default) never raises KeyError'],
      [/Counter\($/, 'Counter(iterable) counts occurrences; .most_common(k) ranks them'],
      [/defaultdict\($/, 'defaultdict(list) creates the empty list on first touch'],
      [/deque\($/, 'deque supports O(1) append / appendleft / pop / popleft'],
      [/heapq\.$/, 'heappush, heappop, nlargest(k, it), nsmallest(k, it)'],
      [/sorted\($/, 'sorted(it, key=lambda x: ..., reverse=False) — stable'],
      [/bisect\.$/, 'bisect_left is the first index >= x; bisect_right is the first > x'],
      [/while\s+$/, 'remember something inside the loop must change the condition'],
      [/def\s+\w+\($/, 'never use a mutable default such as []; use None'],
    ];
    for (const [re, text] of reminders) {
      if (re.test(line)) { this.hintEl.textContent = text; return; }
    }
    this.hintEl.textContent = '';
  }

  insert(text) {
    const { selectionStart: s, selectionEnd: e } = this.input;
    this.input.value = this.input.value.slice(0, s) + text + this.input.value.slice(e);
    const pos = s + text.length;
    this.input.setSelectionRange(pos, pos);
    this.refresh();
  }

  onKey(e) {
    const ta = this.input;

    /* THE WAY OUT. Tab and Shift+Tab are indent and dedent here, which means
     * this textarea swallows the one key the web gives a keyboard for leaving a
     * control — and main.js's window handler returns early for a TEXTAREA
     * target, so Escape never reached it either. Since a code fight now opens
     * with the caret in the editor, that left a keyboard-only player sealed in:
     * measured, ten Tab presses put forty spaces in the buffer and moved focus
     * nowhere, and RUN, CAST, RESET, RETREAT, the side tabs and the top nav
     * were mouse-only for the rest of the fight.
     *
     * Escape blurs. Tab still indents, which is what it is for, and the NEXT
     * Escape reaches the window handler with a non-TEXTAREA target and closes
     * whatever is open. The caption's key hints say so. */
    if (e.key === 'Escape') {
      ta.blur();
      return;
    }

    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (e.shiftKey) this.onSubmit && this.onSubmit();
      else this.onRun && this.onRun();
      return;
    }

    if (e.key === 'Tab') {
      e.preventDefault();
      if (e.shiftKey) {
        // dedent the current line
        const start = ta.value.lastIndexOf('\n', ta.selectionStart - 1) + 1;
        if (ta.value.slice(start, start + 4) === '    ') {
          const pos = ta.selectionStart;
          ta.value = ta.value.slice(0, start) + ta.value.slice(start + 4);
          ta.setSelectionRange(Math.max(start, pos - 4), Math.max(start, pos - 4));
          this.refresh();
        }
      } else {
        this.insert('    ');
      }
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      const start = ta.value.lastIndexOf('\n', ta.selectionStart - 1) + 1;
      const line = ta.value.slice(start, ta.selectionStart);
      let indent = (line.match(/^\s*/) || [''])[0];
      if (/:\s*$/.test(line)) indent += '    ';
      // a return/pass/break/continue ends a block: outdent the next line
      if (/^\s*(return|pass|break|continue|raise)\b/.test(line) && indent.length >= 4) {
        indent = indent.slice(4);
      }
      this.insert('\n' + indent);
      return;
    }

    if (e.key === 'Backspace' && ta.selectionStart === ta.selectionEnd) {
      const before = ta.value.slice(0, ta.selectionStart);
      if (/ {4}$/.test(before) && /^\s*$/.test(before.split('\n').pop())) {
        e.preventDefault();
        const pos = ta.selectionStart - 4;
        ta.value = ta.value.slice(0, pos) + ta.value.slice(ta.selectionStart);
        ta.setSelectionRange(pos, pos);
        this.refresh();
      }
      return;
    }

    const pairs = { '(': ')', '[': ']', '{': '}' };
    if (pairs[e.key] && ta.selectionStart === ta.selectionEnd) {
      e.preventDefault();
      const pos = ta.selectionStart;
      ta.value = ta.value.slice(0, pos) + e.key + pairs[e.key] + ta.value.slice(pos);
      ta.setSelectionRange(pos + 1, pos + 1);
      this.refresh();
      return;
    }
    if ((e.key === ')' || e.key === ']' || e.key === '}')
        && ta.value[ta.selectionStart] === e.key) {
      e.preventDefault();
      ta.setSelectionRange(ta.selectionStart + 1, ta.selectionStart + 1);
    }
  }
}
