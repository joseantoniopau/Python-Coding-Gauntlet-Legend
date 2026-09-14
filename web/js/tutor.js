/* Optional, non-blocking interface guidance. Curriculum and cue retirement are
 * server-owned; this module only observes visible controls, use, and idle time.
 *
 * configure({state, show, hide, api?, now?})
 *   state() -> current dashboard + {screen, encounterId, busy}
 *   show(lesson) -> true ONLY after rendering a non-blocking lesson card.
 *                  false leaves the lesson pending. Do not return a Promise.
 *   hide() -> remove that card when navigation or the measured-run gate changes.
 * sync(dashboard) after every authoritative state refresh. Call enterEncounter
 * after the battle is visible, leaveEncounter on exit, tick from the existing
 * battle interval. Native clicks are counted here; call used(id) for shortcuts
 * which invoke RUN/CAST without clicking their buttons.
 */
import { api as defaultApi } from './api.js';

let hooks = { state: () => ({}), show: () => false, hide: () => {}, api: defaultApi,
  now: () => performance.now() };
let runOpen = true, panel = null, registry = [], policy = null;
let listening = false, encounter = false, epoch = 0, lastActivity = 0;
let appearances = 0, cueNode = null, cueHost = null, cueId = '', checking = false;
let lessonContext = null, lessonId = '', lessonValid = () => true;
const pending = new Set(), shownHere = new Set(), usedHere = new Set(), cuedHere = new Set();

function current() {
  try { return hooks.state() || {}; } catch { return {}; }
}
function context() {
  const s = current();
  return JSON.stringify([epoch, s.screen || '', s.encounterId || '',
    s.player?.created_at || '', s.player?.region || '']);
}
function allowed() { return runOpen === false && current().run_open === false && !current().busy; }
function hideCue() {
  cueNode?.remove();
  cueHost?.classList.remove('has-cue');
  cueNode = cueHost = null; cueId = '';
}
function hideLesson() {
  if (lessonContext !== null) {
    try { hooks.hide(); } catch { /* Guidance must not interrupt play. */ }
    lessonContext = null;
    lessonId = '';
    lessonValid = () => true;
  }
}
function activity() { lastActivity = hooks.now(); hideCue(); }
function visible(node) {
  if (!node?.isConnected || node.disabled || node.getAttribute('aria-disabled') === 'true' ||
      node.closest('#editor-host') || node.getClientRects().length === 0) return false;
  const css = getComputedStyle(node);
  return css.visibility !== 'hidden' && css.visibility !== 'collapse' && css.display !== 'none';
}
function kind() {
  if (!visible(document.querySelector('#screen-battle'))) return '';
  if (visible(document.querySelector('#editor-pane .inc-cast'))) return 'incant';
  if (visible(document.querySelector('#answer-here'))) return 'mcq';
  if (visible(document.querySelector('#puzzle-host'))) return 'puzzle';
  if (visible(document.querySelector('#editor-caption'))) return 'code';
  return '';
}
function clicked(event) {
  if (!encounter || !allowed()) return;
  for (const row of registry) {
    const target = event.target?.closest?.(row.selector);
    if (visible(target)) { void used(row.id); break; }
  }
}

export function configure(options = {}) {
  hooks = { ...hooks, ...options };
  lastActivity = hooks.now();
  if (!listening) {
    document.addEventListener('pointerdown', activity, true);
    document.addEventListener('keydown', activity, true);
    document.addEventListener('input', activity, true);
    document.addEventListener('click', clicked, true);
    listening = true;
  }
  return { beat, sync, cue, tick, used, enterEncounter, leaveEncounter, forget };
}

export function sync(payload = {}) {
  // Unknown is closed. Never infer an ended run from an absent encounter.
  const nextRunOpen = typeof payload.run_open === 'boolean' ? payload.run_open : true;
  if (nextRunOpen !== runOpen) epoch++;
  runOpen = nextRunOpen;
  const view = payload.lessons || (payload.cue ? payload : null);
  if (view) {
    panel = view;
    registry = Array.isArray(view.cue?.controls) ? view.cue.controls : [];
    policy = view.cue?.policy || null;
  }
  document.body.classList.toggle('run-open', runOpen);
  document.body.classList.toggle('no-cues', current().settings?.cues === false);
  if (!allowed() || (lessonContext !== null && (lessonContext !== context() || !lessonValid()))) hideLesson();
  if (!allowed() || current().settings?.cues === false) hideCue();
}

export async function beat(id, { valid = () => true } = {}) {
  const stillHere = () => { try { return valid() === true; } catch { return false; } };
  if (lessonContext !== null && (!allowed() || lessonContext !== context() || !lessonValid())) hideLesson();
  if (!allowed() || typeof id !== 'string' || pending.has(id) || shownHere.has(id) ||
      panel?.taught?.includes(id) || lessonContext !== null || !stillHere()) return false;
  const at = context();
  const idleAt = lastActivity;
  let delivered = false;
  pending.add(id);
  try {
    // A read-only preview avoids latching prose lost to an intervening screen.
    const preview = await hooks.api.lessons();
    if (context() !== at || (id === 'the_code_fight' && lastActivity !== idleAt)) return false;
    sync(preview);
    if (!allowed() || lessonContext !== null || !stillHere()) return false;
    const row = preview.beats?.find(b => b.id === id && !b.taught && b.lines?.length);
    if (!row) return false;
    delivered = hooks.show({ ...row, first_time: true, blocks_input: false }) === true;
    if (!delivered) return false;
    lessonContext = at;
    lessonId = id;
    lessonValid = stillHere;
    shownHere.add(id);
    // One writer, after the did-show hook. A retry is harmless because the
    // server latch is idempotent. Failure stays quiet and never repeats this
    // card during the current session; a future session may retry the lesson.
    const acknowledgement = await hooks.api.lesson(id);
    if (acknowledgement?.first_time) {
      if (panel) panel.taught = [...new Set([...(panel.taught || []), id])];
      shownHere.delete(id); // Successful latches follow the save on load/import.
    } else if (lessonId === id) hideLesson();
    return true;
  } catch { return delivered; }
  finally { pending.delete(id); }
}

// Call from the card's close control; it does not mark other lessons taught.
export function dismiss() { hideLesson(); }

export function enterEncounter() {
  epoch++; encounter = true; appearances = 0;
  usedHere.clear(); cuedHere.clear(); activity(); hideLesson();
}
export function leaveEncounter() {
  epoch++; encounter = false; activity(); hideLesson();
}

function noteResult(result) {
  if (!result?.id || !panel?.cue) return;
  panel.cue.shown = { ...panel.cue.shown, [result.id]: result.shown };
  panel.cue.used = { ...panel.cue.used, [result.id]: result.used };
  const retired = new Set(panel.cue.retired || []);
  if (result.retired) retired.add(result.id);
  panel.cue.retired = [...retired];
}
export async function used(id) {
  activity();
  if (!encounter || !allowed() || !registry.some(row => row.id === id)) return false;
  usedHere.add(id);
  try { noteResult(await hooks.api.lessonNote('used', id)); return true; }
  catch { return false; }
}

function candidate() {
  const mode = kind();
  if (!mode) return null;
  const live = row => !panel?.cue?.retired?.includes(row.id) && !cuedHere.has(row.id);
  for (const row of registry) {
    if (!live(row) || !row.kinds?.includes(mode)) continue;
    const node = document.querySelector(row.selector);
    if (!visible(node)) continue;
    if (row.id === 'run' && usedHere.has('run')) continue;
    if (row.id === 'cast' && mode === 'code' && !usedHere.has('run') &&
        visible(document.querySelector(registry.find(r => r.id === 'run')?.selector || ':not(*)'))) continue;
    if (row.id === 'rune' && usedHere.has('rune')) continue;
    if (row.id === 'trials_tab') {
      // Modern MCQs keep choices in the main pane. The historic off-tab cue
      // is unnecessary whenever answers remain visible; never point at one.
      if (visible(document.querySelector('#mcq-choices .answer-choice')) ||
          visible(document.querySelector('#battle-side-body .list-item')) ||
          node.classList.contains('active')) continue;
    }
    return { row, node, mode };
  }
  return null;
}

export async function cue() {
  if (!encounter || !allowed() || current().settings?.cues === false || !policy) {
    hideCue(); return false;
  }
  if (cueNode?.isConnected && visible(cueHost)) return true;
  hideCue();
  if (checking || !Number.isFinite(policy.per_encounter) || appearances >= policy.per_encounter) return false;
  const next = candidate();
  if (!next || !Number.isFinite(policy.dwell_ms?.[next.mode]) ||
      hooks.now() - lastActivity < policy.dwell_ms[next.mode]) return false;
  const at = context();
  checking = true;
  try {
    // Refresh retirement and the run gate just before offering a cue. No
    // polling interval and no request on frames where nothing is eligible.
    const preview = await hooks.api.lessons();
    if (context() !== at) return false;
    sync(preview);
    const fresh = candidate();
    if (!allowed() || current().settings?.cues === false || !fresh ||
        fresh.row.id !== next.row.id || fresh.node !== next.node ||
        hooks.now() - lastActivity < policy.dwell_ms?.[fresh.mode]) return false;
    cueNode = document.createElement('i');
    cueNode.className = `cue${fresh.row.placement === 'under' ? ' under' : ''}`;
    cueNode.setAttribute('aria-hidden', 'true');
    cueHost = fresh.node; cueId = fresh.row.id;
    cueHost.classList.add('has-cue'); cueHost.appendChild(cueNode);
    appearances++; cuedHere.add(cueId);
    noteResult(await hooks.api.lessonNote('shown', cueId));
    return true;
  } catch { hideCue(); return false; }
  finally { checking = false; }
}

export function tick() {
  if (lessonContext !== null && (!allowed() || lessonContext !== context() || !lessonValid())) hideLesson();
  void cue();
}

export async function forget() {
  if (!allowed()) return false;
  try {
    const result = await hooks.api.lessonsForget();
    if (!result?.cleared) return false;
    epoch++; shownHere.clear(); pending.clear(); usedHere.clear(); cuedHere.clear();
    appearances = 0; activity(); hideLesson();
    sync(await hooks.api.lessons());
    return true;
  } catch { return false; }
}
