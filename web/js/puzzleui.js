/* Puzzle interfaces.
 *
 * Six encounter kinds that are not "type a function into an empty box". Each
 * returns { render(host), answer() } so the battle screen can treat them all
 * identically and the grader on the server does the real work.
 *
 * RUNE_ASSEMBLY is the important one. Ordering shuffled lines removes the typing
 * and the syntax recall and leaves only the structure of the solution, which is
 * the thing actually being learned — and it is the established bridge for a
 * player who freezes at a blank screen.
 */
const $ = (sel, root = document) => root.querySelector(sel);

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}

function escape(text) {
  return String(text).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

/* ------------------------------------------------------------ rune assembly */

function runeAssembly(problem, onChange) {
  const runes = (problem.mcq && problem.mcq.runes) || [];
  /* THE FALLBACK IS AN EMPTY PILE, NOT THE AUTHORED ORDER. The runes are cut
   * from the canonical solution in authored order, so `runes.map((_, i) => i)`
   * — the old fallback — renders THE ANSWER, in order, down the tray. It is
   * unreachable today — all 42 shipped assemblies carry a real shuffle,
   * measured (identity 0/42, sorted 0/42) — but only just: corpus/validate.py
   * checks the shuffle's LENGTH and nothing else, so `[0,1,2,...]` passes it.
   * tests/test_corpus.py's `test_the_rune_pile_is_never_the_solution_in_order`
   * is the assertion that closes that, and this line is the second lock,
   * because
   * gauntlet/tutorial.py's `rune` cue points a violet arrow at the head of
   * this pile and its whole licence to do so is that a shuffle carries no
   * ordering information. An empty pile is a visible bug somebody fixes in an
   * hour. The answer in order is a silent leak nobody sees. */
  const order = (problem.mcq && problem.mcq.shuffle) || [];
  const placed = [];          // [{index, indent}]
  let tray = order.slice();

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'Drag or click runes from the pile into the sequence, then set each one\'s '
      + 'depth with the arrows. Depth is meaning in Python — a line one step too '
      + 'far left runs at the wrong time. Some runes do not belong at all.'));

    const slots = el('div', 'rune-slots');
    if (!placed.length) {
      slots.appendChild(el('div', 'muted small', 'the sequence is empty'));
    }
    placed.forEach((entry, position) => {
      const rune = runes[entry.index];
      const row = el('div', 'rune placed');
      row.appendChild(el('span', 'rune-depth', '·'.repeat(entry.indent) || '—'));
      row.appendChild(el('span', '', escape('    '.repeat(entry.indent) + rune.text)));
      const ctl = el('div', 'indent-ctl');
      const out = el('button', '', '◀');
      out.title = 'less indent';
      out.onclick = (e) => {
        e.stopPropagation();
        entry.indent = Math.max(0, entry.indent - 1);
        build(host); onChange && onChange();
      };
      const inn = el('button', '', '▶');
      inn.title = 'more indent';
      inn.onclick = (e) => {
        e.stopPropagation();
        entry.indent = Math.min(6, entry.indent + 1);
        build(host); onChange && onChange();
      };
      const up = el('button', '', '▲');
      up.onclick = (e) => {
        e.stopPropagation();
        if (position === 0) return;
        [placed[position - 1], placed[position]] = [placed[position], placed[position - 1]];
        build(host); onChange && onChange();
      };
      const down = el('button', '', '▼');
      down.onclick = (e) => {
        e.stopPropagation();
        if (position === placed.length - 1) return;
        [placed[position + 1], placed[position]] = [placed[position], placed[position + 1]];
        build(host); onChange && onChange();
      };
      const back = el('button', '', '✕');
      back.title = 'back to the pile';
      back.onclick = (e) => {
        e.stopPropagation();
        placed.splice(position, 1);
        tray.push(entry.index);
        build(host); onChange && onChange();
      };
      ctl.append(up, down, out, inn, back);
      row.appendChild(ctl);
      slots.appendChild(row);
    });
    host.appendChild(el('div', 'section-title', 'THE SEQUENCE'));
    host.appendChild(slots);

    host.appendChild(el('div', 'section-title', 'THE PILE'));
    const pile = el('div', 'rune-tray');
    if (!tray.length) pile.appendChild(el('div', 'muted small', 'every rune is placed'));
    tray.forEach((index) => {
      const rune = runes[index];
      const row = el('div', 'rune');
      row.appendChild(el('span', 'grip', '⠿'));
      row.appendChild(el('span', '', escape(rune.text)));
      row.onclick = () => {
        // a sensible default depth: match the line before it
        const previous = placed[placed.length - 1];
        const guess = previous
          ? (/:\s*$/.test(runes[previous.index].text) ? previous.indent + 1 : previous.indent)
          : 0;
        placed.push({ index, indent: guess });
        tray = tray.filter(i => i !== index);
        build(host); onChange && onChange();
      };
      pile.appendChild(row);
    });
    host.appendChild(pile);
  }

  return {
    render: build,
    answer: () => placed.map(e => ({ index: e.index, indent: e.indent })),
    ready: () => placed.length > 0,
  };
}

/* ------------------------------------------------------------------- trace */

function trace(problem, onChange) {
  const spec = problem.mcq || {};
  const checkpoints = spec.checkpoints || [];
  const inputs = [];

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'Walk the spell one line at a time. At each mark, say what the variable '
      + 'holds at that moment. Formatting is forgiving; the value is not.'));
    if (spec.code) {
      const pre = el('pre', 'spell-body');
      pre.textContent = spec.code;
      host.appendChild(pre);
    }
    inputs.length = 0;
    checkpoints.forEach((cp) => {
      const row = el('div', 'trace-row');
      row.appendChild(el('label', '',
        `after line ${cp.after_line} — <code>${escape(cp.variable)}</code>`));
      const input = el('input');
      input.placeholder = 'its value here';
      input.addEventListener('input', () => onChange && onChange());
      inputs.push(input);
      row.appendChild(input);
      host.appendChild(row);
    });
  }

  return {
    render: build,
    answer: () => inputs.map(i => i.value),
    ready: () => inputs.some(i => i.value.trim()),
  };
}

/* ---------------------------------------------------------- spot the flaw */

function spotTheFlaw(problem, onChange) {
  const spec = problem.mcq || {};
  let chosen = -1;

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'Two spells, near identical. One is cursed. Click the line that breaks it.'));
    if (spec.reference_code) {
      host.appendChild(el('div', 'section-title', 'THE HONEST SPELL'));
      const pre = el('pre', 'spell-body');
      pre.textContent = spec.reference_code;
      host.appendChild(pre);
    }
    host.appendChild(el('div', 'section-title', 'THE CURSED SPELL'));
    const lines = (spec.code || '').split('\n');
    const pick = el('div', 'code-pick frame');
    pick.style.padding = '8px';
    lines.forEach((line, i) => {
      const row = el('div', `cl ${chosen === i + 1 ? 'picked' : ''}`);
      row.appendChild(el('span', 'n', String(i + 1)));
      row.appendChild(el('span', '', escape(line) || ' '));
      row.onclick = () => { chosen = i + 1; build(host); onChange && onChange(); };
      pick.appendChild(row);
    });
    host.appendChild(pick);
  }

  return { render: build, answer: () => chosen, ready: () => chosen > 0 };
}

/* -------------------------------------------------------- state prediction */

function statePredict(problem, onChange) {
  const spec = problem.mcq || {};
  let input = null;

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'The operations are given. Replay them in your head, one at a time, and '
      + 'write down exactly what the structure holds when they finish.'));
    if (spec.code) {
      const pre = el('pre', 'spell-body');
      pre.textContent = spec.code;
      host.appendChild(pre);
    }
    if (spec.operations) {
      host.appendChild(el('div', 'section-title', 'OPERATIONS'));
      host.appendChild(el('pre', 'spell-body', escape(spec.operations)));
    }
    host.appendChild(el('div', 'section-title', 'FINAL STATE'));
    input = el('input', 'puzzle-input');
    input.placeholder = "e.g. [3, 1] or {'a': 2}";
    input.addEventListener('input', () => onChange && onChange());
    host.appendChild(input);
  }

  return { render: build, answer: () => (input ? input.value : ''),
           ready: () => !!(input && input.value.trim()) };
}

/* ---------------------------------------------------------------- break it */

function breakIt(problem, onChange) {
  const spec = problem.mcq || {};
  let input = null;

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'This spell looks correct. It is not. Find one input that proves it — the '
      + 'game will run both the flawed spell and the honest one on whatever you '
      + 'give it, and you win if they disagree.'));
    host.appendChild(el('div', 'section-title', 'THE SUSPECT SPELL'));
    const pre = el('pre', 'spell-body');
    pre.textContent = spec.flawed_code || '';
    host.appendChild(pre);
    host.appendChild(el('div', 'section-title', 'YOUR INPUT'));
    host.appendChild(el('div', 'muted small',
      `arguments as a JSON array, matching <code>${escape(
        (problem.entry && problem.entry.signature) || '')}</code>`));
    input = el('input', 'puzzle-input');
    input.placeholder = '[[]]  or  [[1, 1], 2]';
    input.addEventListener('input', () => onChange && onChange());
    host.appendChild(input);
    const quick = el('div', 'row');
    quick.style.cssText = 'flex-wrap:wrap;margin-top:8px';
    for (const [label, value] of [['empty', '[[]]'], ['one item', '[[1]]'],
      ['duplicates', '[[2, 2]]'], ['negatives', '[[-1, -2]]'],
      ['all same', '[[5, 5, 5]]'], ['zero', '[0]']]) {
      const b = el('button', 'btn small', label);
      b.onclick = () => { input.value = value; input.focus(); onChange && onChange(); };
      quick.appendChild(b);
    }
    host.appendChild(quick);
  }

  return {
    render: build,
    answer: () => {
      try { return JSON.parse(input.value); } catch (e) { return null; }
    },
    ready: () => !!(input && input.value.trim()),
  };
}

/* ---------------------------------------------------------- complexity match */

function complexityMatch(problem, onChange) {
  const spec = problem.mcq || {};
  const snippets = spec.snippets || [];
  const options = spec.options
    || ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)', 'O(n^2)', 'O(2^n)'];
  const chosen = {};

  function build(host) {
    host.innerHTML = '';
    host.appendChild(el('div', 'puzzle-help',
      'Price every spell. All of them, at once — the cost of one tells you '
      + 'nothing until you can compare it with the others.'));
    snippets.forEach((snippet, i) => {
      host.appendChild(el('div', 'section-title',
        escape(snippet.label || `SNIPPET ${i + 1}`)));
      const pre = el('pre', 'spell-body');
      pre.textContent = snippet.code || '';
      host.appendChild(pre);
      const row = el('div', 'row');
      row.style.flexWrap = 'wrap';
      options.forEach((option) => {
        const b = el('button', `btn small ${chosen[i] === option ? 'primary' : ''}`, option);
        b.onclick = () => { chosen[i] = option; build(host); onChange && onChange(); };
        row.appendChild(b);
      });
      host.appendChild(row);
    });
  }

  return {
    render: build,
    answer: () => {
      const out = {};
      Object.keys(chosen).forEach(k => { out[String(k)] = chosen[k]; });
      return out;
    },
    ready: () => Object.keys(chosen).length === snippets.length && snippets.length > 0,
  };
}

const BUILDERS = {
  RUNE_ASSEMBLY: runeAssembly,
  TRACE: trace,
  SPOT_THE_FLAW: spotTheFlaw,
  STATE_PREDICT: statePredict,
  BREAK_IT: breakIt,
  COMPLEXITY_MATCH: complexityMatch,
};

export const PUZZLE_KINDS = Object.keys(BUILDERS);

export function isPuzzle(kind) {
  return Object.prototype.hasOwnProperty.call(BUILDERS, kind);
}

export function createPuzzle(problem, onChange) {
  const builder = BUILDERS[problem.encounter_kind];
  return builder ? builder(problem, onChange) : null;
}

export const PUZZLE_VERB = {
  RUNE_ASSEMBLY: 'ASSEMBLE ✦',
  TRACE: 'DECLARE ✦',
  SPOT_THE_FLAW: 'ACCUSE ✦',
  STATE_PREDICT: 'DECLARE ✦',
  BREAK_IT: 'STRIKE ✦',
  COMPLEXITY_MATCH: 'PRICE ✦',
};
