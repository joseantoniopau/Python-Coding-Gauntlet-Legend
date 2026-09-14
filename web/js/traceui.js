/* A recording of the player's Python, never a canned algorithm demonstration.
 * The server supplies one visible case. This module owns no API or save state.
 */
const CSS = `
.python-trace{font:16px/1.55 system-ui,sans-serif;color:#ede9dc;background:#10141e;border:1px solid #526077;border-radius:8px;overflow:hidden;max-width:100%;text-align:left}
.python-trace *{box-sizing:border-box}.python-trace header{padding:18px 20px;border-bottom:1px solid #465064;background:#191e2b}.python-trace h3{font:600 20px/1.3 system-ui,sans-serif;margin:0 0 8px;color:#f2d0a0}.python-trace p{margin:5px 0}.python-trace .trace-note{color:#c2c9d6;font-size:14px}
.python-trace .trace-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px 20px;border-bottom:1px solid #465064}.python-trace button{font:600 16px/1.3 system-ui,sans-serif;min-width:70px;min-height:44px;padding:10px 14px;color:#f5eddf;background:#283548;border:1px solid #7791aa;border-radius:4px;cursor:pointer}.python-trace button:disabled{opacity:.45;cursor:default}.python-trace button:focus-visible,.python-trace input:focus-visible,.python-trace .trace-source:focus-visible{outline:3px solid #f4be78;outline-offset:3px}.python-trace .trace-seek{display:flex;align-items:center;gap:12px;flex:1 1 230px}.python-trace input[type=range]{width:100%;min-width:100px;accent-color:#f4be78;min-height:44px}.python-trace .trace-progress{font-variant-numeric:tabular-nums;white-space:nowrap}
.python-trace .trace-caption{padding:12px 20px;margin:0;background:#212a39;color:#f4d9b4;min-height:49px}.python-trace .trace-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(240px,1fr)}.python-trace .trace-source{position:relative;max-height:440px;overflow:auto;padding:12px 0;background:#10141d;border-right:1px solid #465064;tab-size:4}.python-trace .trace-code-line{display:flex;min-width:max-content;line-height:1.65;border-left:3px solid transparent;padding-right:16px}.python-trace .trace-code-line.current{background:#473621;border-left-color:#ffc174}.python-trace .trace-code-line code{font:16px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre;color:#f0efe8;background:transparent;padding:0}.python-trace .trace-line-number{width:4ch;flex:none;box-sizing:content-box;padding:0 12px;color:#a9b8cd;text-align:right;user-select:none;font:16px/1.65 ui-monospace,monospace}.python-trace .trace-values{padding:16px;min-width:0;max-height:440px;overflow:auto}.python-trace h4{font:600 16px/1.4 system-ui,sans-serif;margin:0 0 10px}.python-trace table{border-collapse:collapse;width:100%;font-size:14px}.python-trace th,.python-trace td{padding:8px 5px;border-bottom:1px solid #3e4b60;text-align:left;vertical-align:top}.python-trace th{color:#c6cfdf}.python-trace td code{font:16px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;color:#ede9dc;background:transparent}.python-trace tr.changed{background:#273a35}.python-trace .trace-change{font-size:13px;color:#b7dec2}.python-trace tr.removed{color:#bcc3cf}.python-trace .trace-output{padding:16px 20px;border-top:1px solid #465064}.python-trace pre{font:16px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0;max-height:200px;overflow:auto;color:#e5e8ec;background:#0c1017;padding:12px}.python-trace .trace-result{padding:14px 20px;background:#182b26;border-top:1px solid #465064;overflow-wrap:anywhere}.python-trace .trace-result.limited{background:#392d22}.python-trace .trace-result.failed{background:#36242d}.python-trace .trace-frame-exception{color:#ffc3b9;margin-top:12px}.python-trace .trace-empty{padding:24px 20px;color:#d8dee8}@media(max-width:700px){.python-trace .trace-grid{grid-template-columns:minmax(0,1fr)}.python-trace .trace-source{max-height:300px;border-right:0;border-bottom:1px solid #465064}.python-trace .trace-values{max-height:300px}.python-trace header,.python-trace .trace-controls,.python-trace .trace-output{padding:14px}.python-trace .trace-line-number{padding:0 8px}.python-trace .trace-progress{width:100%}}
`;

const valueText = value => JSON.stringify(value, null, 2) ?? '—';

export function changedLocals(previous = {}, current = {}) {
  const rows = Object.entries(current).map(([name, value]) => ({name, value,
    change: !Object.hasOwn(previous, name) ? 'new' : valueText(previous[name]) !== valueText(value) ? 'changed' : ''}));
  for (const [name, value] of Object.entries(previous)) {
    if (!Object.hasOwn(current, name)) rows.push({name, value, change:'removed'});
  }
  return rows;
}

export function describeFrame(frame) {
  if (!frame) return 'No execution steps were recorded.';
  const scope = frame.function === '<module>' ? 'module' : `${frame.function}()`;
  const position = `Line ${frame.line} · ${scope} · call depth ${frame.depth || 0}`;
  if (frame.event === 'call') return `${position} — function entered; its body has not run yet.`;
  if (frame.event === 'return') return `${position} — function returned ${valueText(frame.value)}.`;
  if (frame.event === 'yield') return `${position} — yielded ${valueText(frame.value)}; this call can resume later.`;
  if (frame.event === 'suspend') return `${position} — execution suspended here; this call can continue later.`;
  if (frame.event === 'resume') return `${position} — execution resumed in the same call.`;
  if (frame.event === 'unwind') return `${position} — this call exited because of an exception.`;
  if (frame.event === 'exception') return `${position} — exception raised here.`;
  return `${position} — values before this line runs.`;
}

export function mount(host, payload = {}) {
  const doc = host.ownerDocument || document;
  const make = (tag, className = '', text = null) => {
    const el = doc.createElement(tag);
    if (className) el.className = className;
    if (text !== null) el.textContent = text;
    return el;
  };
  const root = make('section', 'python-trace');
  root.setAttribute('aria-label', 'Your Python execution trace');
  const style = make('style'); style.textContent = CSS; root.append(style);
  const header = make('header');
  header.append(make('h3', '', 'Trace your Python'),
    make('p', '', payload.case_label || 'One visible test case'),
    make('p', 'trace-note', 'Recorded from your code. Line steps show values before execution; changes compare the previous step in the same function call.'));
  root.append(header);
  const frames = Array.isArray(payload.frames) ? payload.frames : [];
  const previousCalls = new Map();
  const rows = frames.map(frame => {
    const key = frame.call_id ?? `${frame.function}:${frame.depth}`;
    const current = frame.locals || {};
    const changes = changedLocals(previousCalls.get(key), current);
    previousCalls.set(key, current);
    return changes;
  });
  let index = 0, timer = null, destroyed = false, playing = false;
  const events = [];
  function listen(el, event, fn) { el.addEventListener(event, fn); events.push(() => el.removeEventListener(event, fn)); }
  const controls = make('div', 'trace-controls');
  const prev = make('button', '', 'Previous'); prev.type = 'button';
  const next = make('button', '', 'Next'); next.type = 'button';
  const play = make('button', '', 'Play'); play.type = 'button'; play.setAttribute('aria-pressed', 'false');
  const seekLabel = make('label', 'trace-seek');
  const seek = make('input'); seek.type = 'range'; seek.min = '0'; seek.max = String(Math.max(0, frames.length - 1)); seek.step = '1';
  seek.setAttribute('aria-label', 'Execution step');
  const progress = make('span', 'trace-progress');
  seekLabel.append(seek); controls.append(prev, play, next, seekLabel, progress); root.append(controls);
  const caption = make('p', 'trace-caption'); caption.setAttribute('role', 'status'); caption.setAttribute('aria-live', 'polite'); root.append(caption);
  const grid = make('div', 'trace-grid');
  const source = make('div', 'trace-source'); source.tabIndex = 0; source.setAttribute('aria-label', 'Recorded Python source; current line highlighted');
  const lines = String(payload.source || '').split('\n').map((text, i) => {
    const row = make('div', 'trace-code-line');
    const number = make('span', 'trace-line-number', String(i + 1)); number.setAttribute('aria-hidden', 'true');
    row.setAttribute('aria-label', `Line ${i + 1}`);
    row.append(number, make('code', '', text || ' ')); source.append(row); return row;
  });
  const values = make('div', 'trace-values');
  values.append(make('h4', '', 'Local values'));
  const table = make('table');
  const thead = make('thead'); const tr = make('tr');
  for (const title of ['Name', 'Value', 'Change']) { const th = make('th', '', title); th.scope = 'col'; tr.append(th); }
  thead.append(tr); const tbody = make('tbody'); table.append(thead, tbody); values.append(table);
  const noLocals = make('p', 'trace-note', 'No local values at this step.'); values.append(noLocals);
  values.append(make('p', 'trace-note', 'Large containers are shortened. Custom objects are labeled without calling their code.'));
  const raised = make('p', 'trace-frame-exception'); values.append(raised);
  grid.append(source, values); root.append(grid);
  const output = make('div', 'trace-output'); output.append(make('h4', '', 'Printed output so far'));
  const stdout = make('pre'); output.append(stdout); root.append(output);
  const result = make('div', 'trace-result');
  if (payload.truncated) {
    result.classList.add('limited');
    result.append(make('p', '', `Partial recording: ${payload.truncation_reason || 'a recording limit was reached'}.`));
    result.append(make('p', 'trace-note', 'No completed result is inferred from this recording. Try a smaller visible input or fix the loop before tracing again.'));
  } else if (payload.exception) {
    result.classList.add('failed');
  }
  if (payload.exception) result.append(make('p', '', `${payload.exception.type || 'Exception'}${payload.exception.line ? ` on line ${payload.exception.line}` : ''}: ${payload.exception.message || ''}`));
  else if (payload.ok) result.append(make('p', '', `Program returned: ${valueText(payload.output)}`));
  if (payload.stdout_truncated) result.append(make('p', 'trace-note', 'Printed output is limited to the first 4,096 characters.'));
  result.append(make('p', 'trace-note', 'Tracing is ungraded practice on this visible case. It does not check hidden tests or establish mastery.'));
  root.append(result); host.append(root);

  function render(scroll = false) {
    const frame = frames[index];
    caption.textContent = describeFrame(frame);
    progress.textContent = frames.length ? `${index + 1} / ${frames.length}` : '0 steps';
    seek.value = String(index); seek.setAttribute('aria-valuetext', frames.length ? `Step ${index + 1} of ${frames.length}, line ${frame.line}` : 'No steps');
    prev.disabled = !frames.length || index === 0;
    next.disabled = !frames.length || index >= frames.length - 1;
    play.disabled = frames.length < 2;
    seek.disabled = !frames.length;
    for (let i = 0; i < lines.length; i++) {
      const current = i + 1 === frame?.line;
      lines[i].classList.toggle('current', current);
      if (current) lines[i].setAttribute('aria-current', 'step'); else lines[i].removeAttribute('aria-current');
    }
    if (scroll && frame && lines[frame.line - 1]) {
      const line = lines[frame.line - 1];
      // Scroll the source pane only; playback must never move the entire page.
      if (line.offsetTop < source.scrollTop || line.offsetTop + line.offsetHeight > source.scrollTop + source.clientHeight)
        source.scrollTop = Math.max(0, line.offsetTop - source.clientHeight / 2);
    }
    tbody.replaceChildren();
    for (const row of rows[index] || []) {
      const tr = make('tr', row.change === 'removed' ? 'removed' : row.change ? 'changed' : '');
      const name = make('td'); name.append(make('code', '', row.name));
      const value = make('td'); value.append(make('code', '', valueText(row.value)));
      tr.append(name, value, make('td', 'trace-change', row.change)); tbody.append(tr);
    }
    noLocals.hidden = !!rows[index]?.length;
    table.hidden = !rows[index]?.length;
    raised.textContent = frame?.exception ? `${frame.exception.type}: ${frame.exception.message}. A later step may catch this exception.` : '';
    raised.hidden = !frame?.exception;
    stdout.textContent = (index === frames.length - 1 ? payload.stdout : frame?.stdout) || '(nothing printed yet)';
  }
  function pause() {
    playing = false;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    play.textContent = 'Play'; play.setAttribute('aria-pressed', 'false');
  }
  function visible() {
    return !destroyed && !doc.hidden && root.isConnected && root.getClientRects().length > 0 && !root.closest('[hidden], [aria-hidden="true"]');
  }
  function tick() {
    timer = null;
    if (!visible() || index >= frames.length - 1) { pause(); return; }
    index++; render(true);
    if (index >= frames.length - 1) pause(); else timer = setTimeout(tick, 850);
  }
  listen(prev, 'click', () => { pause(); index = Math.max(0, index - 1); render(true); });
  listen(next, 'click', () => { pause(); index = Math.min(frames.length - 1, index + 1); render(true); });
  listen(seek, 'input', () => { pause(); index = Math.min(frames.length - 1, Math.max(0, Number(seek.value) || 0)); render(true); });
  listen(play, 'click', () => {
    if (playing) { pause(); return; }
    if (frames.length < 2 || !visible()) return;
    if (index >= frames.length - 1) { index = 0; render(true); }
    playing = true; play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true'); timer = setTimeout(tick, 850);
  });
  listen(doc, 'visibilitychange', () => { if (doc.hidden) pause(); });
  render();
  return {destroy() {
    if (destroyed) return;
    destroyed = true; pause(); events.splice(0).forEach(remove => remove()); root.remove();
  }};
}
