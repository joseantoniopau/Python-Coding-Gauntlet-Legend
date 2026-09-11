/* Python Coding Gauntlet Legend — client orchestration. */
import { api } from './api.js';
import { audio } from './audio.js';
import * as pixel from './pixel.js';
import * as sprites from './sprites.js';
import * as lootart from './lootart.js';
import { createBattleFX, DAMAGE_KIND, trialsFromFeedback } from './fx.js';
import * as puzzleui from './puzzleui.js';
import { IncantationUI } from './incantui.js';
import { TitleScreen } from './title.js';
import { Editor, BLANK } from './editor.js';
import { Overworld } from './overworld.js';
import { Visualiser, hasViz } from './viz.js';
import { WorldUI } from './worldui.js';
import * as partyui from './partyui.js';

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};

const G = {
  state: null,
  world: null,
  encounter: null,
  problem: null,
  screen: 'world',
  overworld: null,
  editor: null,
  viz: null,
  vizCanvas: null,
  tab: 'trials',
  timer: null,
  // Any clock owned by the modal. modal() and closeModal() both clear it, so a
  // countdown can never outlive the node it was writing to.
  modalTimer: null,
  // Set while a modal chain owns the screen and a stray backdrop click must not
  // tear it down mid-way. The diagnostic is the one place this matters.
  modalLocked: false,
  startedAt: 0,
  hints: [],  // [{level, body}] — bodies are kept so a cast spell can be re-read
  pendingNode: null,
  interview: null,
  interviewTimer: null,
  dialogueQueue: [],
  lastResult: null,
  // What the current encounter has had taken off it. finalexam.Seal, as sent.
  seal: null,
  // The live IncantationUI. It owns #puzzle-host while it exists, which is why
  // every path that wants that node destroys this first.
  incant: null,
  incantRun: null,
  incantCards: [],
  // The worldui/partyui instance currently mounted in #panel-body.
  child: null,
};

/* ---------------- chrome helpers ---------------- */

function toast(title, body, kind = '') {
  const t = el('div', `toast ${kind}`, `<span class="tt">${title}</span>${body}`);
  $('#toasts').appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; }, 4200);
  setTimeout(() => t.remove(), 4800);
}

/* A sealed refusal is HTTP 409 with {error,capability,name,message,herald}. The
 * message is the exam's own sentence and is shown verbatim; the capability goes
 * in the title, because "SEALED" alone does not tell the player WHICH door shut. */
function sealedTitle(res) {
  const cap = (res && res.capability) || '';
  return cap ? `SEALED · ${cap.replace(/_/g, ' ')}` : 'SEALED';
}

function modal(html, { wide = false } = {}) {
  const m = $('#modal');
  // There is exactly one #modal node and every modal reuses it, so anything the
  // previous occupant left ticking is now writing into elements that are gone.
  clearInterval(G.modalTimer);
  G.modalTimer = null;
  m.innerHTML = html;
  m.style.width = wide ? 'min(1040px,96vw)' : 'min(900px,94vw)';
  $('#modal-bg').classList.add('show');
  return m;
}

function closeModal() {
  clearInterval(G.modalTimer);
  G.modalTimer = null;
  $('#modal-bg').classList.remove('show');
}

$('#modal-bg').addEventListener('click', (e) => {
  if (e.target.id !== 'modal-bg') return;
  // A locked modal is mid-chain and owns the screen; it supplies its own exit.
  if (G.modalLocked) return;
  closeModal();
});

function say(who, lines, portraitKind) {
  G.dialogueQueue = Array.isArray(lines) ? lines.slice() : [lines];
  const box = $('#dialogue');
  const pc = $('#dialogue-portrait');
  const img = sprites.portrait(portraitKind || 'scholar');
  pc.width = img.width; pc.height = img.height;
  pc.getContext('2d').drawImage(img, 0, 0);
  $('#dialogue-who').textContent = who;
  box.classList.add('show');
  advanceDialogue();
}

function advanceDialogue() {
  const next = G.dialogueQueue.shift();
  if (next === undefined) {
    $('#dialogue').classList.remove('show');
    if (G.storyQueue && G.storyQueue.length) { setTimeout(playStoryQueue, 120); return; }
    // The queue is spent: hand control back to whoever was waiting on it.
    const after = G.afterStory;
    G.afterStory = null;
    if (after) after();
    return;
  }
  $('#dialogue-what').textContent = next;
  audio.sfx('tick');
}

$('#dialogue').addEventListener('click', advanceDialogue);

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function markdownish(text) {
  return (text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(?:python)?\n([\s\S]*?)```/g, (m, code) => `<pre>${code}</pre>`)
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b style="color:var(--gold-hi)">$1</b>');
}

function show(screen) {
  G.screen = screen;
  // A mounted child panel keeps its own timers and listeners. Leaving the panel
  // screen without telling it is the fifth leak this file is not going to have.
  if (screen !== 'panel') destroyChild();
  for (const s of document.querySelectorAll('.screen')) s.classList.remove('active');
  if (screen === 'world') {
    $('#screen-world').classList.add('active');
    G.overworld && G.overworld.start();
    setTimeout(() => G.overworld && G.overworld.resize(), 30);
  } else if (screen === 'battle') {
    $('#screen-battle').classList.add('active');
    G.overworld && G.overworld.stop();
  } else {
    $('#screen-panel').classList.add('active');
    G.overworld && G.overworld.stop();
  }
}

/* ---------------- vitals ---------------- */

function paintVitals() {
  const p = G.state.player;
  $('#bar-stamina').style.width = `${(p.stamina / p.stamina_max) * 100}%`;
  $('#bar-mana').style.width = `${(p.mana / p.mana_max) * 100}%`;
  $('#bar-xp').style.width = `${(p.xp_into_level / Math.max(1, p.xp_for_level)) * 100}%`;
  $('#lvl-label').textContent = `LV ${p.level} · ${p.title.toUpperCase()}`;
  const mult = p.combo >= 10 ? 1.5 : p.combo >= 5 ? 1.25 : p.combo >= 3 ? 1.1 : 1.0;
  $('#combo-val').textContent = `x${mult.toFixed(2)}${p.combo ? ` (${p.combo})` : ''}`;
  const pip = $('#points-pip');
  if (pip) pip.style.display = G.state.unspent_points > 0 ? '' : 'none';
}

async function refresh() {
  let next;
  try {
    next = await api.state();
  } catch (e) {
    // Callers await this on the path to a result modal and a nav repaint. A
    // silent rejection there leaves the player on a dead screen, so say it out
    // loud and carry on with the last state we had.
    toast('THE WORLD IS QUIET', `Could not read the game state — ${e.message}`, 'red');
    if (!G.state) throw e;  // nothing to fall back on during boot
    return G.state;
  }
  G.state = next;
  paintVitals();
  applySettings();
  return G.state;
}

function applySettings() {
  const s = G.state.settings;
  document.body.classList.toggle('crt', !!s.crt);
  document.body.classList.toggle('reduced-motion', !!s.reduced_motion);
  document.body.classList.toggle('high-contrast', !!s.high_contrast);
  document.documentElement.style.setProperty('--scale', s.text_scale || 1);
  audio.setEnabled(!!s.music);
  if (s.vol_master !== undefined) audio.setMaster(s.vol_master);
  if (s.vol_music !== undefined) audio.setMusic(s.vol_music);
  if (s.vol_sfx !== undefined) audio.setSfx(s.vol_sfx);
  if (G.overworld) G.overworld.reducedMotion = !!s.reduced_motion;
}

/* ---------------- world ---------------- */

function currentRegion() {
  const id = G.state.player.region;
  return G.state.regions.find(r => r.id === id) || G.state.regions[0];
}

function loadRegion(regionId, spawn) {
  const region = G.state.regions.find(r => r.id === regionId) || G.state.regions[0];
  G.state.player.region = region.id;
  G.overworld.load(region, region.tier, spawn);
  G.overworld.solvedNodes = new Set(JSON.parse(
    localStorage.getItem('gauntlet-nodes-' + region.id) || '[]'));
  $('#region-name').textContent = (region.numeral ? `${region.numeral} · ` : '')
    + region.name.toUpperCase();
  $('#region-blurb').textContent = region.blurb + ' ' + region.physical;
  audio.play(region.music || 'overworld');
  paintWorldSide();
}

function paintWorldSide() {
  const side = $('#world-side');
  const s_ = G.state;
  const s = G.state;
  const region = currentRegion();
  const due = s.retests_due.length;
  side.innerHTML = '';

  const ch = s_.chapter;
  if (ch) {
    const card = el('div', 'chapter-card',
      `<div class="ct">CHAPTER ${ch.number} OF ${ch.total}</div>
       <div class="cg"><b style="color:var(--gold-hi)">${ch.title}</b><br>${ch.goal}</div>
       <div class="bar" style="margin-top:8px"><i style="width:${ch.progress.percent}%"></i></div>
       <div class="small muted" style="margin-top:5px">
         ${ch.progress.clears}/${ch.progress.clears_target} cleared ·
         mastery ${ch.progress.mastery}/${ch.progress.mastery_target}
         ${ch.next_title ? `· next: ${ch.next_title}` : ''}</div>`);
    side.appendChild(card);
  }

  // state.todo is the no-dead-end guarantee as data: the server promises it is
  // never empty, so it is rendered unconditionally and without a fallback.
  side.appendChild(el('div', 'section-title', 'WHAT NEXT'));
  const next = el('div');
  if (due) {
    next.appendChild(el('div', 'list-item',
      `<span class="t">${due} RETEST${due > 1 ? 'S' : ''} DUE</span>
       <span class="d">${s.retests_due.slice(0, 3).map(r =>
         r.family.replace(/_/g, ' ')).join(', ')} — in disguise.</span>`));
  }
  for (const item of (s.todo || []).slice(0, 4)) {
    const row = el('div', 'list-item',
      `<span class="t">${TODO_ICON[item.kind] || '·'} ${item.title}</span>
       <span class="d">${item.why}<br><span class="muted small">${
         item.region_name || ''}${item.hops ? ` · ${item.hops} hop(s) away` : ' · here'}
         </span></span>`);
    row.onclick = () => doTodo(item);
    next.appendChild(row);
  }
  side.appendChild(next);

  side.appendChild(el('div', 'section-title', 'ACTIONS'));
  const actions = el('div', 'stack');
  const btnNext = el('button', 'btn primary', 'NEXT ENCOUNTER (N)');
  btnNext.onclick = () => startNext();
  const btnBoss = el('button', 'btn danger', 'CHALLENGE BOSS');
  btnBoss.onclick = () => showBossList();
  const btnShrine = el('button', 'btn', 'MEMORY SHRINE');
  btnShrine.onclick = () => doShrine();
  const btnForge = el('button', 'btn good', "ARMORER'S FORGE");
  btnForge.onclick = () => startNext({ kind: 'DEBUG_BATTLE' });
  const btnIncant = el('button', 'btn', 'SPEAK AN INCANTATION');
  btnIncant.onclick = () => showIncantList();
  actions.append(btnNext, btnBoss, btnShrine, btnForge, btnIncant);
  side.appendChild(actions);

  side.appendChild(el('div', 'section-title', 'ARMOUR'));
  const armour = el('div');
  for (const piece of G.world.armor) {
    const v = s.armor[piece.id] || 0;
    const row = el('div', 'skill-row',
      `<span class="sn">${piece.name.toUpperCase()}</span>
       <span class="bar"><i style="width:${v}%;background:${
         v > 60 ? 'var(--green)' : v > 25 ? 'var(--orange)' : 'var(--red)'}"></i></span>
       <span class="sv">${v}</span>`);
    armour.appendChild(row);
  }
  armour.appendChild(el('div', 'small muted',
    'Armour is repaired by fixing broken programs, never by a potion.'));
  side.appendChild(armour);

  // The roads out of here, from state.world.edges. The old list was a hard-coded
  // walk over every region and knew nothing about routes, requirements or the
  // fact that one of these roads is one-way.
  side.appendChild(el('div', 'section-title', 'THE ROADS OUT'));
  const travel = el('div');
  for (const road of roadsFromHere()) travel.appendChild(routeRow(road));
  const seeMap = el('button', 'btn small', 'THE WHOLE MAP');
  seeMap.onclick = () => go('map');
  travel.appendChild(seeMap);
  side.appendChild(travel);
}

/* Every road leaving the region the server says you are standing in. Sorted
 * passable-first, because an open road is a choice and a shut one is a goal. */
function roadsFromHere() {
  const w = G.state.world || {};
  const here = w.here || G.state.player.region;
  const edges = (w.edges || []).filter(e => e.from === here
    || (!e.one_way && e.to === here));
  return edges.map(e => orientRoad(e, here))
    .sort((a, b) => (b.passable ? 1 : 0) - (a.passable ? 1 : 0));
}

/* state.world.edges orients every route from the end it was authored at, so a
 * road the player happens to be standing at the far end of arrives pointing
 * backwards — `to_name` would name the region they are already in. The gate on
 * the road is the same either way; only the destination has to be turned round. */
function orientRoad(edge, here) {
  if (edge.from === here) return edge;
  const back = ((G.state.world || {}).nodes || []).find(n => n.id === edge.from)
    || (G.state.regions || []).find(r => r.id === edge.from) || {};
  return { ...edge, from: here, to: edge.from, to_name: back.name || edge.from };
}

/* One road. A shut one is shown shut, with the server's own `requirement` and
 * its percentage, rather than left off the list. */
function routeRow(road) {
  const shut = !road.passable;
  const row = el('div', `list-item ${shut ? 'locked' : ''}`,
    `<span class="t">${shut ? '⚿ ' : ''}${road.name.toUpperCase()}
       <span class="tag ${shut ? 'red' : 'green'}">${road.to_name}</span>
       ${road.one_way ? '<span class="tag orange">ONE WAY</span>' : ''}</span>
     <span class="d">${road.prose || ''}<br>
       <span class="muted small">${shut
         ? `${road.requirement} — ${road.percent}% of the way there`
         : `danger ${road.danger}${road.warning ? ' · ' + road.warning : ''}`}</span>
     </span>`);
  if (shut) {
    // Never merely absent: pressing a shut road says which number is missing.
    row.onclick = () => toast('THE ROAD IS CLOSED', road.requirement
      + ` — ${road.percent}% of the way there.`, 'red');
    return row;
  }
  row.onclick = () => takeRoad(road);
  return row;
}

async function takeRoad(road) {
  let r;
  try {
    r = await api.travel(road.id);
  } catch (e) { toast('THE ROAD REFUSES', e.message, 'red'); return; }
  // A sealed refusal is a 409 the wrapper hands back as a body. Say its sentence.
  if (r.error === 'sealed') { toast(sealedTitle(r), r.message, 'red'); return; }
  if (r.error) {
    toast('THE ROAD IS CLOSED',
      (r.route && r.route.requirement) || r.error, 'red');
    return;
  }
  audio.sfx('unlock');
  await refresh();
  closeModal();
  loadRegion(r.region);
  // Travelling is reachable from the map panel as well as the world side, so
  // the screen it lands on has to be the world rather than whatever was open.
  returnToWorld();
}

/* Icons for state.todo rows. Decoration, not meaning — every row carries its
 * own `why` and that is the sentence the player reads. */
const TODO_ICON = {
  retest: '↻', chapter: '§', boss: '☠', dungeon: '⛨', event: '✦',
  shrine: '◈', repair: '⚒', explore: '→', travel: '→', quest: '❯',
};

/* One row of state.todo, acted on. Every action kind the server can emit is
 * handled here; an unknown one lands on the adaptive picker, which is always
 * a legal answer to "what now". */
function doTodo(item) {
  const act = item.action || {};
  if (act.kind === 'encounter') return startNext({ region: act.region });
  if (act.kind === 'retest') return startNext();
  if (act.kind === 'shrine') return doShrine();
  if (act.kind === 'boss') return showBossList(item.region);
  if (act.kind === 'dungeon') return go('map');
  if (act.kind === 'objective') return go('map');
  if (act.kind === 'travel') {
    const road = roadsFromHere().find(e => e.to === act.region);
    if (road && road.passable) return takeRoad(road);
    return go('map');
  }
  return startNext();
}

function onNodeEnter(marker) {
  G.pendingNode = marker;
  if (marker.kind === 'shrine') return doShrine();
  if (marker.kind === 'chest') return openChest(marker);
  if (marker.kind === 'npc') return mentorTalk();
  if (marker.kind === 'boss') return showBossList(currentRegion().id);
  if (marker.kind === 'exit') return showTravel();
  if (marker.kind === 'elite') return startNext({ elite: true });
  return startNext({ region: currentRegion().id });
}

/* Chests hold a page of the codex and never anything else. They used to promise
 * TREASURE and report themselves "emptied", which reads as a drop you missed;
 * they are labelled as what they are, and a page can be read again. */
const CODEX_PAGES = [
  'A dict lookup is O(1) on average and O(n) in the pathological case.',
  '`all([])` is True. `any([])` is False. Interviewers ask this.',
  'Python sorts are stable — equal elements keep their relative order.',
  '`deque` gives O(1) at both ends. A list gives O(n) at the front.',
  'BFS finds the shortest path in an UNWEIGHTED graph only.',
];

function openChest(marker) {
  const key = 'gauntlet-chest-' + marker.id;
  const read = !!localStorage.getItem(key);
  if (!read) {
    localStorage.setItem(key, '1');
    audio.sfx('unlock');
  }
  // Deterministic from the id, so a cache always held the page it held.
  let hash = 0;
  for (const ch of String(marker.id)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  say('CODEX CACHE', [
    read ? 'You have read this one. It has not changed its mind.'
         : 'No gold, no gear. Someone left a page behind instead.',
    CODEX_PAGES[hash % CODEX_PAGES.length],
  ], 'oracle');
}

function mentorTalk() {
  const region = currentRegion();
  const mentor = G.world.mentors[region.mentor] || G.world.mentors.byte;
  const weak = G.state.weakness[0];
  const lines = [mentor.greeting];
  if (weak) {
    lines.push(`Your weakest evidence right now is ${weak.replace(/_/g, ' ')}. `
      + 'That is where I would spend tonight.');
  }
  const due = G.state.retests_due[0];
  if (due) {
    lines.push(`And ${due.family.replace(/_/g, ' ')} is due for a retest. `
      + 'It will not arrive wearing the same face.');
  }
  say(mentor.name, lines, mentor.sprite);
}

/* The signpost at the edge of a region. Same roads as the side panel, same
 * refusals, in a modal with a way out. */
function showTravel() {
  const m = modal(`<h2>THE ROADS OUT</h2>
    <p class="small muted">A closed road is a goal with a number on it, not a
    wall. Press one to hear what it is still waiting for.</p>
    <div id="travel-rows"></div>
    <div class="actions"><button class="btn" id="m-close">STAY HERE</button></div>`);
  const rows = m.querySelector('#travel-rows');
  const roads = roadsFromHere();
  for (const road of roads) rows.appendChild(routeRow(road));
  if (!roads.length) {
    // Every region on the map has at least one road, so this is a broken read
    // rather than a place with no exits. Say which it is.
    rows.appendChild(el('p', 'small muted',
      'No roads were returned for this region. The map screen has the full sheet.'));
  }
  const map = el('button', 'btn small', 'THE WHOLE MAP');
  map.onclick = () => { closeModal(); go('map'); };
  rows.appendChild(map);
  m.querySelector('#m-close').onclick = closeModal;
}

/* ---------------- battle ---------------- */

async function startNext(opts = {}) {
  try {
    const payload = await api.nextEncounter({
      region: opts.region, mode: 'adventure', kind: opts.kind,
    });
    enterBattle(payload);
  } catch (e) { toast('THE WORLD RESISTS', e.message, 'red'); }
}

async function startProblem(id, mode = 'adventure') {
  try {
    enterBattle(await api.startEncounter(id, mode));
  } catch (e) { toast('CANNOT ENTER', e.message, 'red'); }
}

function enterBattle(payload) {
  // An IncantationUI from a previous fight owns #puzzle-host until it is told
  // otherwise, and renderPuzzle is about to want that node.
  destroyIncant();
  // A companion card from the last fight is about to be describing the wrong
  // problem, and the once-per-run sealed notice has to be re-armed.
  partyui.beginEncounter();
  G.encounter = payload;
  G.problem = payload.problem;
  G.hints = [];
  G.probeCharges = payload.probe_charges;
  G.startedAt = Date.now();
  G.interview = payload.interview || null;
  // What this fight has taken off you. Interview Mode is the full seal; a boss
  // is whatever its rung has taken. Read it once, here, and let the tabs obey.
  G.seal = payload.seal || null;
  const sealed = applySeal();

  document.body.classList.toggle('interview-mode', payload.mode === 'interview');

  const p = payload.problem;
  $('#problem-title').textContent = p.title;
  $('#problem-statement').innerHTML = markdownish(p.problem_statement);

  const meta = $('#problem-meta');
  meta.innerHTML = '';
  meta.appendChild(el('span', 'tag gold', p.difficulty));
  if (payload.mode !== 'interview') {
    meta.appendChild(el('span', 'tag violet', p.pattern.replace(/_/g, ' ')));
    if (p.optimal_complexity && p.optimal_complexity.time) {
      meta.appendChild(el('span', 'tag blue', 'target ' + p.optimal_complexity.time));
    }
  }
  meta.appendChild(el('span', 'tag', p.encounter_kind.replace(/_/g, ' ')));
  if (payload.encounter.is_retest) {
    meta.appendChild(el('span', 'tag red', `MEMORY AMBUSH · ${Math.round(payload.encounter.interval_days)}d`));
  }
  if (p.reported_company) {
    meta.appendChild(el('span', 'tag green',
      `reported pattern · ${p.reported_company}`));
  }

  const ex = $('#problem-examples');
  ex.innerHTML = '';
  if (p.constraints && p.constraints.length) {
    ex.appendChild(el('div', 'muted small',
      'CONSTRAINTS: ' + p.constraints.join(' · ')));
  }
  if (p.examples && p.examples.length) {
    for (const e of p.examples) {
      ex.appendChild(el('div', 'small',
        `<span class="muted">in</span> <code>${e.input}</code> ` +
        `<span class="muted">→ out</span> <code>${e.output}</code>`));
    }
  }
  if (p.provenance_note && payload.mode !== 'interview') {
    ex.appendChild(el('div', 'muted small', `<br>${p.provenance_note}`));
  }

  // enemy
  const enemy = payload.enemy;
  $('#enemy-name').textContent = enemy.name.toUpperCase();
  $('#enemy-hp').querySelector('i').style.width = '100%';
  $('#enemy-hp-label').textContent = `${enemy.hp} / ${enemy.hp_max}`;
  setEnemyScene(payload);

  $('#battle-target').textContent = fmtTime(p.target_seconds);

  // editor
  const interview = payload.mode === 'interview';
  if (!G.editor) {
    G.editor = new Editor($('#editor-host'), {
      onRun: doRun, onSubmit: doSubmit, assist: !interview,
    });
  }
  G.editor.setAssist(!interview);

  G.puzzle = null;
  $('#btn-reset').style.display = '';
  // Reset the primary button before any branch decides what it should say.
  // Without this a puzzle that was left un-ready leaves CAST disabled for every
  // subsequent encounter, and only a page reload clears it.
  $('#btn-submit').disabled = false;
  $('#btn-submit').style.display = '';
  if (puzzleui.isPuzzle(p.encounter_kind)) {
    renderPuzzle(p);
  } else if (p.entry && p.entry.kind === 'mcq') {
    renderMcq(p);
  } else {
    G.editor.reset(p.starter_code || '');
    $('#editor-host').style.display = '';
    $('#puzzle-host').style.display = 'none';
    $('#btn-run').style.display = '';
    $('#btn-submit').textContent = p.entry.kind === 'test_forge' ? 'FORGE ✦' : 'CAST ✦';
  }

  startTimer();
  setTab(visibleTab(interview ? 'approach' : 'trials'));
  show('battle');
  audio.play(enemy.boss ? 'boss' : 'battle');

  if (enemy.boss && enemy.taunt) {
    audio.sfx('boss');
    ensureStage().bossIntro({ name: enemy.name, taunt: enemy.taunt,
                              colour: enemy.colour });
    // The herald is said before the fight, while walking out is still free —
    // never after the loss. payload.boss carries it; the seal carries it too.
    const herald = (payload.boss && payload.boss.herald)
      || (G.seal && G.seal.herald) || '';
    say(enemy.name.toUpperCase(),
        herald ? [enemy.taunt, herald] : [enemy.taunt], 'interviewer');
    if (sealed.size && G.seal && (G.seal.takes || []).length) {
      toast('THIS ONE TAKES SOMETHING',
        G.seal.takes.map(t => t.name).join(' · ')
        + ' — gone for this fight and every fight after it.', 'red');
    }
  } else if (payload.encounter.is_retest) {
    toast('MEMORY AMBUSH',
      'A pattern you learned earlier has returned wearing a different face.', 'violet');
  }
  if (payload.interview) paintInterviewTimer();
  // Not while a boss is mid-taunt: say() owns one dialogue queue and the taunt
  // is the louder of the two.
  if (!enemy.boss && G.editor && $('#editor-host').style.display !== 'none'
      && G.editor.hasBlank()) explainBlank();
}

/* 59 starters ship with a `__BLANK__` marker and nothing in the game has ever
 * said what it is. Say it once, the first time one appears, and never again. */
function explainBlank() {
  if (localStorage.getItem('gauntlet-blank-seen')) return;
  localStorage.setItem('gauntlet-blank-seen', '1');
  const mentor = G.world.mentors.byte;
  say(mentor.name, [
    `That ${BLANK} in the spell is not Python. It is a slot.`,
    'Everything around it is already written. Replace the marker — only the '
    + 'marker — with the expression that belongs there, then cast.',
    'Your cursor is already sitting on it.',
  ], mentor.sprite);
}

function ensureStage() {
  if (G.fx) return G.fx;
  G.fx = createBattleFX($('#battle-stage'), {});
  G.fx.setAudio(audio);
  G.fx.setReducedMotion(!!(G.state && G.state.settings.reduced_motion));
  return G.fx;
}

function setEnemyScene(payload) {
  const fx = ensureStage();
  fx.setScene({
    region: (payload.region || {}).palette || 'spring',
    enemy: payload.enemy,
    pattern: payload.problem.pattern,
  });
  fx.setEnemyHp(payload.enemy.hp, payload.enemy.hp_max);
  fx.start();
  return fx;
}

function renderPuzzle(p) {
  $('#editor-host').style.display = 'none';
  $('#btn-run').style.display = 'none';
  const host = $('#puzzle-host');
  host.style.display = '';
  $('#btn-submit').textContent = puzzleui.PUZZLE_VERB[p.encounter_kind] || 'ANSWER ✦';
  G.puzzle = puzzleui.createPuzzle(p, () => {
    $('#btn-submit').disabled = !G.puzzle.ready();
  });
  if (!G.puzzle) { host.textContent = 'This puzzle cannot be shown.'; return; }
  G.puzzle.render(host);
  $('#btn-submit').disabled = !G.puzzle.ready();
}

function renderMcq(p) {
  $('#editor-host').style.display = 'none';
  $('#btn-run').style.display = 'none';
  // The answers ARE the choices below. Leaving a primary submit button on
  // screen just offers a way to fail an encounter without answering it.
  $('#btn-submit').style.display = 'none';
  const body = $('#battle-side-body');
  setTab('trials');
  body.innerHTML = '';
  if (p.mcq.code) {
    body.appendChild(el('pre', 'spell-body', p.mcq.code));
  }
  p.mcq.choices.forEach((choice, i) => {
    const item = el('div', 'list-item', `<span class="d">${markdownish(choice)}</span>`);
    item.onclick = async () => {
      try {
        await showResult(await api.mcq(i));
      } catch (e) { toast('ANSWER FAILED', e.message, 'red'); }
    };
    body.appendChild(item);
  });
}

function startTimer() {
  clearInterval(G.timer);
  G.timer = setInterval(() => {
    const s = (Date.now() - G.startedAt) / 1000;
    $('#battle-timer').textContent = fmtTime(s);
    if (G.problem && s > G.problem.target_seconds) {
      $('#battle-timer').style.color = 'var(--orange)';
    }
    if (G.interview) paintInterviewTimer();
  }, 500);
}

function paintInterviewTimer() {
  if (!G.interview) return;
  const remaining = G.interview.seconds_remaining
    - (Date.now() - G.startedAt) / 1000;
  const node = $('#interview-timer');
  node.textContent = `${fmtTime(remaining)} · Q${G.interview.index + 1}/${G.interview.total}`;
  node.classList.toggle('critical', remaining < 300);
  audio.setIntensity(remaining < 300 ? 1 - remaining / 300 : 0);
}

/* --- the seal --- */

/* Which side tab each crutch switches off. The ladder takes them in this order
 * and never gives one back, so hiding the tab is truer than leaving a panel
 * that answers every press with a refusal. WEAKNESS_MAP is taken one rung
 * before PROBES, so hiding TACTICS on PROBES loses nothing that was still there. */
const TAB_SEAL = { spells: 'HINTS', tactics: 'PROBES', vision: 'VISUALS' };

/* The labels as index.html wrote them, captured once. An incantation borrows the
 * TRIALS tab and has to be able to give it back. */
const TAB_LABEL = (() => {
  const out = {};
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    out[b.dataset.tab] = b.textContent;
  }
  return out;
})();

function capSealed(cap) {
  if (G.seal && Array.isArray(G.seal.sealed) && G.seal.sealed.includes(cap)) return true;
  return !!(G.encounter && G.encounter.mode === 'interview');
}

/* Hide the tabs this encounter's seal names, show the rest. Returns the sealed
 * set so the caller can say what was taken. */
function applySeal() {
  const sealed = new Set((G.seal && G.seal.sealed) || []);
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    const cap = TAB_SEAL[b.dataset.tab];
    b.textContent = TAB_LABEL[b.dataset.tab] || b.textContent;
    b.style.display = cap && sealed.has(cap) ? 'none' : '';
  }
  return sealed;
}

/* The wanted tab if it still exists, otherwise the first one that does. TRIALS
 * is never sealed, so this always lands somewhere. */
function visibleTab(wanted) {
  const cap = TAB_SEAL[wanted];
  if (!cap || !capSealed(cap)) return wanted;
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    if (b.style.display !== 'none') return b.dataset.tab;
  }
  return 'trials';
}

/* Who took it, in one line, for a panel that is still open but thinner. */
function sealNote() {
  const label = (G.seal && G.seal.label) || '';
  return label ? `Sealed by ${label.toUpperCase()}.`
               : 'Sealed for this encounter.';
}

/* --- side tabs --- */
function setTab(tab) {
  // The body is about to be emptied. A Visualiser left playing would keep
  // ticking against a canvas that is no longer in the document, forever.
  stopViz();
  G.tab = tab;
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    b.classList.toggle('active', b.dataset.tab === tab);
  }
  const body = $('#battle-side-body');
  body.innerHTML = '';
  // An incantation fight has no problem, no trials and no probes. Its side is
  // the battlefield: the names in scope and what the fight is asking for.
  if (G.incant) { paintIncantSide(body); return; }
  if (tab === 'trials') paintTrials(body);
  else if (tab === 'tactics') paintTactics(body);
  else if (tab === 'spells') paintSpells(body);
  else if (tab === 'approach') paintApproach(body);
  else if (tab === 'vision') paintVision(body);
}

document.querySelectorAll('#battle-side-tabs button').forEach(b => {
  b.onclick = () => setTab(b.dataset.tab);
});

function paintTrials(body, report) {
  if (!report) {
    body.appendChild(el('div', 'muted small',
      `${G.problem.visible_tests ? G.problem.visible_tests.length : 0} visible trials · `
      + `${G.problem.hidden_test_count || 0} hidden. Hidden trials never reveal their `
      + 'expected value — only the category of input that broke your spell.'));
    for (const t of (G.problem.visible_tests || [])) {
      body.appendChild(el('div', 'test-line',
        `<span class="icon">·</span><div class="body"><div class="name">${t.name}</div>
         <pre>${(t.args || []).map(a => JSON.stringify(a)).join(', ')} → ${JSON.stringify(t.expected)}</pre></div>`));
    }
    return;
  }
  for (const line of report.lines) {
    const icon = line.status === 'pass' ? '✔' : line.status === 'timeout' ? '⧗' : '✖';
    const node = el('div', `test-line ${line.status}`,
      `<span class="icon">${icon}</span>
       <div class="body">
         <div class="name">${line.hidden ? '🔒 ' : ''}${line.name}
           <span class="muted small">${line.ms ? line.ms.toFixed(1) + 'ms' : ''}</span></div>
         ${line.message ? `<div class="msg">${line.message}</div>` : ''}
         ${line.got !== null && line.got !== undefined
           ? `<pre>got      ${line.got}\nexpected ${line.expected}</pre>` : ''}
       </div>`);
    body.appendChild(node);
  }
}

/* A real 24x24 item sprite whose material, ornament and aura all read its
 * rarity — not a tinted glyph. Epic and above animate. */
function itemIcon(item, size = 48) {
  const canvas = document.createElement('canvas');
  canvas.width = lootart.ITEM_SIZE;
  canvas.height = lootart.ITEM_SIZE;
  canvas.style.width = size + 'px';
  canvas.style.height = size + 'px';
  canvas.style.imageRendering = 'pixelated';
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const frames = lootart.itemFrameCount(item);
  const paint = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    lootart.drawItem(ctx, item, 0, 0, { scale: 1, time: performance.now() });
  };
  paint();
  if (frames > 1 && !(G.state && G.state.settings.reduced_motion)) {
    const timer = setInterval(() => {
      if (!canvas.isConnected) { clearInterval(timer); return; }
      paint();
    }, lootart.FRAME_MS);
  }
  return canvas;
}

/* The TACTICS panel. This is where the game stops being a quiz: you read the
 * enemy, decide which boundary it is hiding, and spend a probe to find out
 * whether your model of the spec is actually right. */
function paintTactics(body) {
  if (G.encounter.mode === 'interview') {
    body.appendChild(el('div', 'frame', `<div style="padding:14px;line-height:1.7">
      <b style="color:var(--red)">SEALED.</b><br><br>
      Probes, items and gear effects are all withheld in Interview Mode. What you
      bring to a real screen is what you know.</div>`));
    return;
  }

  const t = G.encounter.tactics || {};
  const charges = G.probeCharges !== undefined
    ? G.probeCharges : (G.encounter.probe_charges || 0);

  body.appendChild(el('div', 'muted small', t.advice || ''));

  body.appendChild(el('div', 'section-title', 'WHAT IT GUARDS'));
  if (!(t.weaknesses || []).length) {
    body.appendChild(el('div', 'muted small',
      'No hidden boundaries here. Clean fluency wins this one.'));
  }
  for (const w of t.weaknesses || []) {
    body.appendChild(el('div', `weakness ${w.exposed ? 'exposed' : ''}`,
      `<span class="wi" style="color:${w.colour}">${w.icon}</span>
       <div class="grow">
         <div class="wn" style="color:${w.colour}">${w.name.toUpperCase()}
           ${w.exposed ? '<span style="color:var(--gold-hi)"> — EXPOSED</span>' : ''}</div>
         <div class="wt">${w.exposed ? w.teach : w.tell}</div>
       </div>`));
  }

  if ((t.resistances || []).length) {
    body.appendChild(el('div', 'section-title', 'WHAT IT RESISTS'));
    for (const r of t.resistances) {
      body.appendChild(el('div', 'weakness',
        `<span class="wi" style="color:${r.colour}">${r.icon}</span>
         <div class="grow"><div class="wn" style="color:${r.colour}">${r.name.toUpperCase()}</div>
         <div class="wt">${r.teach}</div></div>`));
    }
  }

  body.appendChild(el('div', 'section-title', 'PROBE'));
  const charge = el('div', 'probe-charges', `◈ ${charges} charge(s)`);
  body.appendChild(charge);
  body.appendChild(el('div', 'muted small',
    'Assert what the CORRECT answer is on an input you choose. Right, and you expose '
    + 'the weakness — passing its hidden trial then strikes critically for bonus XP '
    + 'and better loot. Wrong, and you have caught a flawed mental model before '
    + 'spending twenty minutes on it.'));

  const box = el('div', 'probe-box');
  const sig = (G.problem.entry && G.problem.entry.signature) || '';
  const argsInput = el('input');
  argsInput.placeholder = `arguments as JSON array — e.g. [[3, 3], 6]`;
  const expInput = el('input');
  expInput.placeholder = 'the answer YOU claim is correct — e.g. [0, 1]';
  box.appendChild(el('div', 'small muted', `signature: <code>${sig}</code>`));
  box.append(argsInput, expInput);

  const quick = el('div', 'row');
  quick.style.flexWrap = 'wrap';
  quick.style.marginBottom = '6px';
  for (const [label, argsHint] of [['empty', '[[], 0]'], ['single', '[[1], 1]'],
    ['duplicates', '[[3, 3], 6]'], ['negatives', '[[-1, -2], -3]'],
    ['all same', '[[2, 2, 2], 4]']]) {
    const b = el('button', 'btn small', label);
    b.onclick = () => { argsInput.value = argsHint; argsInput.focus(); };
    quick.appendChild(b);
  }
  box.appendChild(quick);

  const go = el('button', 'btn primary', 'PROBE ◈');
  go.onclick = async () => {
    let args, expected;
    try {
      args = JSON.parse(argsInput.value);
      expected = JSON.parse(expInput.value);
    } catch (err) {
      toast('MALFORMED PROBE', 'Both fields must be valid JSON.', 'red');
      return;
    }
    go.disabled = true;
    let r;
    try {
      r = await api.probe(args, expected);
    } catch (err) {
      go.disabled = false;   // never leave the player holding a dead button
      toast('PROBE FAILED', err.message, 'red');
      return;
    }
    go.disabled = false;
    if (r.error) {
      toast('PROBE FAILED', r.message || r.error, 'red');
      return;
    }
    G.probeCharges = r.charges_left;
    if (r.correct) {
      audio.sfx(r.weakness_hit ? 'crit' : 'select');
      if (r.weakness_hit) {
        G.encounter.tactics = r.brief;
        G.encounter.enemy = r.enemy;
        toast('WEAKNESS EXPOSED', r.message, 'green');
        setTab('tactics');
        return;
      }
    } else {
      audio.sfx('fail');
    }
    const out = el('div', 'spell-body',
      markdownish(r.message) + (r.true_value
        ? `<pre>the true answer was: ${r.true_value}</pre>` : ''));
    box.appendChild(out);
    charge.textContent = `◈ ${r.charges_left} charge(s)`;
  };
  box.appendChild(go);
  body.appendChild(box);

  // consumables
  const loadout = G.encounter.loadout || {};
  if ((loadout.consumables || []).length) {
    body.appendChild(el('div', 'section-title', 'PACK'));
    for (const c of loadout.consumables) {
      const item = el('div', 'item-card',
        `<div class="grow"><div class="in" style="color:${
          (G.state.loadout.rarities[c.rarity] || {}).colour || '#e8c37d'}">
          ${c.name} ×${c.count}</div>
          <div class="ie">${c.blurb}</div></div>`);
      item.onclick = async () => {
        let r;
        try {
          r = await api.consumable(c.id);
        } catch (e) { toast('CANNOT USE', e.message, 'red'); return; }
        if (r.error) { toast('CANNOT USE', r.message || r.error, 'red'); return; }
        audio.sfx('spell');
        toast(r.name.toUpperCase(), r.applied.join(' · '), 'green');
        G.probeCharges = r.probe_charges;
        await refresh();
        G.encounter.loadout = G.state.loadout;
        setTab('tactics');
      };
      body.appendChild(item);
    }
  }
}

function paintSpells(body) {
  if (G.encounter.mode === 'interview') {
    body.appendChild(el('div', 'frame', `<div style="padding:14px;line-height:1.7">
      <b style="color:var(--red)">SEALED.</b><br><br>
      Interview Mode measures what you can do unaided. Spells, the mentor, the
      pattern name and the coach are all withheld — by the server, not merely
      hidden here.<br><br>
      Everything opens again the moment the attempt is scored.</div>`));
    return;
  }
  body.appendChild(el('div', 'muted small',
    'Spells cost FOCUS and lower the rank you can earn. They never block progress. '
    + 'Nobody stays stuck.'));
  (G.problem.hint_tree || []).forEach((rung) => {
    const cast = G.hints.find(h => h.level === rung.level);
    const node = el('div', `spell ${cast ? 'used' : ''}`,
      `<span class="sname">${rung.title.toUpperCase()}</span>
       <span class="scost">${cast ? 'CAST' : rung.mana + ' focus'}</span>`);
    node.onclick = async () => {
      if (cast) return;
      try {
        const r = await api.hint(rung.level);
        if (r.error) { toast('NOT ENOUGH FOCUS', r.message || r.error, 'red'); return; }
        // Keep the body, not just the level. setTab repaints from scratch, and a
        // hint you paid focus for should survive a trip to TRIALS and back.
        G.hints.push({ level: rung.level, body: r.body });
        audio.sfx('spell');
        if (G.fx) G.fx.castSpell(rung.spell);
        await refresh();
        setTab('spells');
        if (rung.spell === 'PHOENIX') {
          toast('PHOENIX', 'A Learning Clear still advances the story — and schedules '
            + 'a mandatory rematch.', 'violet');
        }
      } catch (e) { toast('SPELL FAILED', e.message, 'red'); }
    };
    body.appendChild(node);
    // Every hint already cast is re-rendered under its own rung, in order.
    if (cast) body.appendChild(el('div', 'spell-body', markdownish(cast.body)));
  });
}

function paintApproach(body) {
  body.appendChild(el('div', 'muted small',
    'Before you write: what is your approach, which structure, and what does it cost? '
    + 'Interviewers score this as heavily as the code.'));
  const ta = el('textarea', 'explain');
  ta.placeholder = "I'll use a dictionary of value → index. One pass; for each value I "
    + 'check whether its complement is already stored. Each element is handled once, '
    + 'so O(n) time and O(n) space.';
  ta.value = G.encounter.encounter.explanation || '';
  body.appendChild(ta);
  G.explainBox = ta;

  // The coach is a crutch with a rung on the ladder. Once a boss has taken it,
  // the button is gone in Adventure Mode too — the server refuses it either way.
  if (!capSealed('COACH')) {
    const btn = el('button', 'btn small', 'SCORE MY EXPLANATION');
    btn.onclick = async () => {
      let r;
      try {
        r = await api.explain(ta.value);
      } catch (e) { toast('NOT SCORED', e.message, 'red'); return; }
      if (r.error) { toast('NOT SCORED', r.error, 'red'); return; }
      const out = el('div', 'frame', `<div style="padding:12px">
        <div class="pixel" style="color:var(--gold);font-size:11px">SCORE ${r.score}</div>
        <div style="margin:8px 0">${r.checks.map(c =>
          `<div class="gate ${c.passed ? 'pass' : 'fail'}">
             <span class="mark">${c.passed ? '✔' : '·'}</span>
             <span>${c.label} <span class="muted small">— ${c.why}</span></span></div>`).join('')}</div>
        <div class="small" style="color:var(--violet)">${r.verdict}</div>
        <div class="small muted" style="margin-top:8px">${r.model_answer}</div>
      </div>`);
      body.appendChild(out);
      audio.sfx('select');
    };
    body.appendChild(btn);
  }

  if (capSealed('PATTERN')) {
    body.appendChild(el('div', 'muted small', sealNote()
      + ' Nothing here is labelled, so there is no family to call.'));
  } else {
    body.appendChild(el('div', 'section-title', 'PATTERN CALL'));
    body.appendChild(el('div', 'muted small',
      'Name the family before you implement. Recognition is scored separately.'));
    const families = ['HASH_MAP', 'SET', 'SLIDING_WINDOW', 'TWO_POINTER', 'STACK',
      'QUEUE', 'BFS', 'DFS', 'TREE', 'RECURSION', 'BINARY_SEARCH', 'MATRIX',
      'HEAP', 'PREFIX_SUM', 'SORTING', 'SIMULATION', 'DP', 'DESIGN', 'INTERVALS'];
    const wrap = el('div', 'row');
    wrap.style.flexWrap = 'wrap';
    for (const f of families) {
      const b = el('button', 'btn small', f.replace(/_/g, ' '));
      b.onclick = () => {
        G.declared = f;
        for (const x of wrap.children) x.classList.remove('primary');
        b.classList.add('primary');
        audio.sfx('select');
      };
      wrap.appendChild(b);
    }
    body.appendChild(wrap);
  }
}

function paintVision(body) {
  if (G.encounter.mode === 'interview') {
    body.appendChild(el('div', 'muted', 'Sealed during Interview Mode.'));
    return;
  }
  const kind = (G.problem.visualization && G.problem.visualization.type)
    || G.problem.pattern.toLowerCase();
  if (!hasViz(kind)) {
    body.appendChild(el('div', 'muted small',
      'No animation for this family yet — the Grimoire entry still applies.'));
    return;
  }
  const canvas = el('canvas');
  canvas.id = 'viz-canvas';
  const caption = el('div');
  caption.id = 'viz-caption';
  const controls = el('div');
  controls.id = 'viz-controls';
  body.append(canvas, caption, controls);
  const v = new Visualiser(canvas, caption);
  G.viz = v;
  G.vizCanvas = canvas;
  v.load(kind);
  const mk = (label, fn) => { const b = el('button', 'btn small', label); b.onclick = fn; return b; };
  controls.append(
    mk('◀', () => v.step(-1)),
    mk('PLAY', () => v.play()),
    mk('STOP', () => v.stop()),
    mk('▶', () => v.step(1)));
  if (G.problem.visualization && G.problem.visualization.caption) {
    body.appendChild(el('div', 'muted small',
      G.problem.visualization.caption));
  }
  // The canvas may already have been discarded by a tab switch in those 50ms.
  setTimeout(() => { if (G.viz === v) v.render(); }, 50);
}

/* Stop and forget the visualiser. Called from every path that removes its
 * canvas from the document — tab switch, leaving the battle, a new encounter. */
function stopViz() {
  if (!G.viz) return;
  G.viz.stop();
  G.viz = null;
  G.vizCanvas = null;
}

/* --- run / submit --- */

async function doRun() {
  if (!G.encounter) return;
  const btn = $('#btn-run');
  btn.disabled = true;
  btn.textContent = 'RUNNING…';
  try {
    const r = await api.run(G.editor.value);
    setTab('trials');
    const body = $('#battle-side-body');
    body.innerHTML = '';
    if (r.phase === 'syntax') {
      body.appendChild(el('div', 'test-line fail',
        `<span class="icon">✖</span><div class="body">
          <div class="name">SyntaxError${r.error.line ? ' on line ' + r.error.line : ''}</div>
          <div class="msg">${r.error.message}</div>
          ${r.error.text ? `<pre>${r.error.text}</pre>` : ''}</div>`));
      audio.sfx('fail');
    } else {
      paintTrials(body, {
        lines: r.tests.map(t => ({
          name: t.name, status: t.status, hidden: false, ms: t.ms,
          message: t.message, got: t.got, expected: t.expected,
        })),
      });
      audio.sfx(r.all_passed ? 'select' : 'hit');
    }
    if (r.stdout) {
      body.appendChild(el('div', 'section-title', 'STDOUT'));
      body.appendChild(el('pre', 'spell-body', r.stdout));
    }
    if (r.stderr) {
      body.appendChild(el('div', 'section-title', 'STDERR'));
      body.appendChild(el('pre', 'spell-body', r.stderr));
    }
  } catch (e) { toast('RUN FAILED', e.message, 'red'); }
  btn.disabled = false;
  btn.textContent = 'RUN ▶';
}

async function doSubmit() {
  if (!G.encounter) return;
  const btn = $('#btn-submit');
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'CASTING…';
  if (G.puzzle) {
    try {
      const answer = G.puzzle.answer();
      if (answer === null) {
        toast('MALFORMED', 'That input is not valid JSON.', 'red');
      } else {
        await showResult(await api.puzzle(answer));
      }
    } catch (e) { toast('FAILED', e.message, 'red'); }
    btn.disabled = false;
    btn.textContent = label;
    return;
  }
  try {
    const result = await api.submit({
      code: G.editor.value,
      declared_pattern: G.declared || '',
      explanation: G.explainBox ? G.explainBox.value : '',
      interview: G.encounter.mode === 'interview',
    });
    // Awaited inside the try: a failure while building the report must surface
    // as a toast, not as an unhandled rejection over a cleared battle screen.
    await showResult(result);
  } catch (e) { toast('CAST FAILED', e.message, 'red'); }
  btn.disabled = false;
  btn.textContent = label;
}

async function showResult(result) {
  G.lastResult = result;
  G.declared = null;
  clearInterval(G.timer);
  await refresh();

  const fb = result.feedback;
  const pct = (fb.passed / Math.max(1, fb.total)) * 100;
  $('#enemy-hp').querySelector('i').style.width = `${100 - pct}%`;
  $('#enemy-hp-label').textContent = `${fb.total - fb.passed} / ${fb.total}`;
  setTab('trials');
  paintTrials($('#battle-side-body'), fb);

  // Play the exchange on the stage before the report appears: each passing
  // trial is a hit, each exposed weakness a critical, each perf failure a
  // resist. The modal then explains what the player just watched.
  if (G.fx) {
    try {
      G.fx.setCombo(G.state.player.combo,
                    result.combo_multiplier || 1);
      await G.fx.resolveTrials(trialsFromFeedback(fb, result.combat), {});
      G.fx.setEnemyHp(Math.max(0, fb.total - fb.passed), fb.total);
      if (result.solved) await G.fx.victory({ rank: result.rank, xp: result.xp,
                                              loot: result.loot });
      else await G.fx.defeat({ cause: (result.analysis || {}).root_cause });
    } catch (err) { /* the report must appear even if the animation cannot */ }
  }

  if (result.solved) {
    audio.sfx(result.rank === 'S' ? 'victory' : 'crit');
    if (G.overworld && G.pendingNode) {
      G.overworld.solvedNodes.add(G.pendingNode.id);
      localStorage.setItem('gauntlet-nodes-' + currentRegion().id,
        JSON.stringify([...G.overworld.solvedNodes]));
    }
  } else {
    audio.sfx('fail');
  }

  const rankColour = { S: 'var(--gold-hi)', A: 'var(--green)', B: 'var(--blue)',
    C: 'var(--orange)', LEARNING_CLEAR: 'var(--violet)' }[result.rank] || 'var(--red)';

  let html = `<h2 style="color:${rankColour}">
      ${result.solved ? (result.rank === 'LEARNING_CLEAR' ? 'LEARNING CLEAR'
        : 'VICTORY — RANK ' + result.rank) : 'THE SPELL BROKE'}</h2>
    <div class="row" style="flex-wrap:wrap;gap:6px;margin-bottom:12px">
      <span class="tag gold">+${result.xp} XP</span>
      <span class="tag blue">${fmtTime(result.seconds)} / target ${fmtTime(result.target_seconds)}</span>
      ${result.combo > 1 ? `<span class="tag green">COMBO ×${result.combo_multiplier.toFixed(2)}</span>` : ''}
      ${result.skill ? `<span class="tag violet">${result.skill.replace(/_/g, ' ')}
        → ${result.skill_state ? Math.round(result.skill_state.mastery) : '—'}
        (${result.skill_state ? result.skill_state.stage : ''})</span>` : ''}
      ${result.next_retest_days ? `<span class="tag">retest in ${result.next_retest_days}d</span>` : ''}
    </div>`;

  if (result.analysis && result.analysis.narrative) {
    html += `<h3>WHAT HAPPENED</h3>
      <p>${markdownish(result.analysis.narrative)}</p>`;
    if (result.analysis.root_cause) {
      html += `<p class="small"><span class="tag red">ROOT CAUSE ·
        ${result.analysis.root_cause.replace(/_/g, ' ')}</span></p>`;
    }
  }

  if (result.coach && result.coach.available) {
    if (result.coach.questions.length) {
      html += `<h3>THE COACH ASKS</h3><ul style="line-height:1.9;color:var(--ink-dim)">`
        + result.coach.questions.map(q => `<li>${q}</li>`).join('') + '</ul>';
    }
    if (result.coach.analysis) html += `<p>${markdownish(result.coach.analysis)}</p>`;
    if (result.coach.next_steps.length) {
      html += '<h3>WHAT TO TRAIN NEXT</h3><ul style="line-height:1.9;color:var(--ink-dim)">'
        + result.coach.next_steps.map(s => `<li>${s}</li>`).join('') + '</ul>';
    }
  } else if (result.coach && !result.coach.available) {
    html += `<p class="small muted">${result.coach.analysis}</p>`;
  }

  if (result.training_camp) {
    html += `<h3>TRAINING CAMP — ${result.training_camp.name.toUpperCase()}</h3>
      <p>${result.training_camp.why}</p>`;
  }
  if (result.remediation) {
    const r = result.remediation;
    html += '<h3>YOUR REMEDIATION</h3>';
    for (const [key, label] of [['immediate', 'NOW'], ['next', 'NEXT'], ['delayed', 'IN 3 DAYS']]) {
      if (!r[key]) continue;
      html += `<div class="list-item" data-problem="${r[key].id}">
        <span class="t">${label} · ${r[key].title}</span>
        <span class="d">${r[key].why}</span></div>`;
    }
  }
  if (result.combat) {
    const c = result.combat;
    if (c.crits.length) {
      html += '<h3>CRITICAL STRIKES</h3>';
      for (const crit of c.crits) {
        html += `<div class="crit-line">✦ ${crit.name.toUpperCase()} — the trial
          "${crit.trial}" landed for triple damage</div>`;
      }
      html += `<p class="small muted">You probed those boundaries before you cast.
        That is what the ×${c.xp_multiplier} XP multiplier is for.</p>`;
    } else if (c.probes_used === 0 && result.solved) {
      html += `<p class="small muted">No probes spent. Exposing a weakness before you
        cast turns its hidden trial into a critical — and criticals multiply both XP
        and loot quality.</p>`;
    }
    for (const r of c.resisted) {
      html += `<p class="small" style="color:var(--red)">⛊ ${r.message}</p>`;
    }
  }
  // The companion walking with you says one thing about how that went. The
  // server writes it; saying nothing when it sent one is how a party member
  // becomes a stat.
  if (result.companion_line) {
    html += `<p class="small" style="color:var(--violet)">${result.companion_line}</p>`;
  }
  if (result.combo_saved) {
    html += `<p class="small"><span class="tag violet">COMBO HELD</span>
      Your gear absorbed the break. The streak survives.</p>`;
  }
  html += lootHtml(result.loot);
  if (result.secrets && result.secrets.length) {
    for (const sec of result.secrets) {
      html += `<h3 style="color:var(--red)">★ SECRET — ${sec.name.toUpperCase()}</h3>
        <p>${sec.condition}</p>
        ${sec.item_detail ? `<div class="item-card rarity-${
          String(sec.item_detail.rarity || 'mythic').toLowerCase()}"
          style="border-color:${sec.item_detail.rarity_colour}">
          <div class="grow"><div class="in" style="color:${sec.item_detail.rarity_colour}">
            ${sec.item_detail.name} <span class="muted">· ${sec.item_detail.rarity}</span></div>
          <div class="ie">${sec.item_detail.effect_text.join(' · ')}</div>
          <div class="if">${sec.item_detail.flavour}</div></div></div>` : ''}`;
    }
  }
  if (result.armor_event) {
    const a = result.armor_event;
    html += `<p class="small">${a.repaired
      ? `<span class="tag green">ARMOUR REPAIRED</span> ${a.piece.toUpperCase()} ${a.before} → ${a.after}`
      : `<span class="tag red">ARMOUR CRACKED</span> ${a.piece.toUpperCase()} ${a.before} → ${a.after} — the Armorer has work for you.`}</p>`;
  }
  if (result.weapon_event) {
    html += `<p class="small"><span class="tag gold">WEAPON EVOLVED</span>
      ${result.weapon_event.name} → tier ${result.weapon_event.tier}
      <span class="muted">(${result.weapon_event.criterion})</span></p>`;
  }
  if (result.companion_event) {
    html += `<p class="small"><span class="tag violet">COMPANION JOINS</span>
      ${result.companion_event.name} — "${result.companion_event.line}"</p>`;
  }
  if (result.achievements && result.achievements.length) {
    html += result.achievements.map(a =>
      `<p class="small"><span class="tag gold">ACHIEVEMENT</span> ${a.name} — ${a.desc}</p>`).join('');
  }
  if (result.boss) {
    html += result.boss.defeated
      ? `<h3>${result.boss.name} FALLS</h3>
         <p>Rank ${result.boss.rank} in ${fmtTime(result.boss.seconds)}. Rematch tier
         ${result.boss.rematch_tier} unlocked — the same boss, a different surface form.</p>`
      : `<h3>${result.boss.name} STEPS BACK</h3><p>${result.boss.message}</p>
         ${result.boss.mentor ? `<div class="list-item">
           <span data-portrait="${result.boss.mentor.sprite}"></span>
           <span class="t">${result.boss.mentor.name}</span>
           <span class="d">${result.boss.mentor.greeting}</span></div>` : ''}
         <div id="boss-ladder"><p class="small muted">Reading the ladder…</p></div>`;
  }
  if (result.canonical_solution) {
    html += `<h3>THE WORKED SOLUTION</h3>
      <pre class="spell-body">${result.canonical_solution
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>
      <p class="small muted">Close this, clear the editor, and rebuild it from memory.
      Reading a solution is not learning it.</p>`;
  }
  if (result.explanation) html += `<h3>WHY</h3><p>${markdownish(result.explanation)}</p>`;
  if (result.explanation_score) {
    html += `<p class="small"><span class="tag blue">EXPLANATION ${result.explanation_score.score}</span>
      ${result.explanation_score.verdict}</p>`;
  }

  html += `<div class="actions">
      ${result.interview_next && !result.interview_next.finished
        ? '<button class="btn primary" id="r-next-iv">NEXT INTERVIEW PROBLEM</button>' : ''}
      ${result.interview_next && result.interview_next.finished
        ? '<button class="btn primary" id="r-iv-report">SEE YOUR REPORT</button>' : ''}
      ${!result.interview_next && result.solved
        ? '<button class="btn primary" id="r-next">NEXT ENCOUNTER</button>' : ''}
      ${!result.interview_next && !result.solved
        ? '<button class="btn primary" id="r-retry">TRY AGAIN</button>' : ''}
      ${result.training_camp && !result.solved
        ? '<button class="btn good" id="r-camp">GO TO TRAINING CAMP</button>' : ''}
      <button class="btn" id="r-world">RETURN TO THE WORLD</button>
    </div>`;

  const m = modal(html, { wide: true });
  m.querySelectorAll('[data-problem]').forEach(n => {
    n.onclick = () => { closeModal(); startProblem(n.dataset.problem); };
  });
  /* Something decided to stay. partyui draws the meeting properly — sprite,
   * first words, how it was found — but it wants the one #modal node the
   * report is currently sitting in, so each meeting waits for the report to be
   * dismissed and then for the meeting before it. */
  const meetings = (result.found_pets || []).slice();
  const afterReport = (then) => {
    const row = meetings.shift();
    if (!row) { then(); return; }
    audio.sfx('unlock');
    partyui.showPetFound(row, { onClose: () => afterReport(then) });
  };
  const bind = (id, fn) => { const b = m.querySelector('#' + id); if (b) b.onclick = fn; };
  bind('r-next', () => {
    closeModal();
    afterReport(() => {
      if (playStoryQueue()) { G.afterStory = () => startNext(); return; }
      startNext();
    });
  });
  // The server keeps enc.started_at from first entry and grades SPEED on it, so
  // restarting the visible clock would only lie to the player about their rank.
  bind('r-retry', () => { closeModal(); startTimer(); G.editor.focus(); });
  bind('r-world', () => {
    closeModal();
    afterReport(() => { returnToWorld(); playStoryQueue(); });
  });
  bind('r-camp', () => {
    closeModal();
    const camp = result.training_camp;
    loadRegion(camp.region);
    // Every other travel path moves the server too; without this the camp visit
    // is undone by the next refresh.
    api.move(camp.region, 4, 15).catch(() => {});
    returnToWorld();
    const mentor = G.world.mentors[camp.mentor] || G.world.mentors.byte;
    say(mentor.name, [camp.why, 'We fix the foundation first. Then we go back.'],
        mentor.sprite);
  });
  if (result.boss && !result.boss.defeated) paintBossTeaching(m, result.boss);
  bind('r-next-iv', async () => {
    closeModal();
    try {
      enterBattle(await api.interviewCurrent());
    } catch (e) { toast('CANNOT CONTINUE', e.message, 'red'); }
  });
  bind('r-iv-report', () => { closeModal(); showInterviewReport(result.interview_next); });

  if (result.loot) {
    showLootDrop(result.loot);
    audio.sfx('loot');
    toast('LOOT', result.loot.name, result.loot.kind === 'consumable' ? '' : 'gold');
  }
  if (result.secrets && result.secrets.length) {
    audio.sfx('levelup');
    for (const sec of result.secrets) {
      toast('★ SECRET FOUND', sec.name, 'red');
    }
  }
  if (result.story && result.story.length) {
    // Beats queue behind the report so a milestone never talks over the result
    G.storyQueue = (G.storyQueue || []).concat(result.story);
  }
  if (result.levels_gained) {
    const levels = result.levels_gained;
    const points = result.unspent_points;
    setTimeout(() => {
      if (!$('#modal-bg').classList.contains('show')) showLevelUp(levels, points);
      else toast('LEVEL UP', `Level ${G.state.player.level} — ${points} point(s) `
        + 'waiting in GEAR.', 'gold');
    }, 400);
  }
}

async function searchHere() {
  const region = currentRegion();
  const { x, y } = G.overworld.player;
  let r;
  try {
    r = await api.search(region.id, x, y);
  } catch (e) {
    toast('YOU SEARCH', `Nothing answers — ${e.message}`, 'red');
    return;
  }
  if (!r.found) {
    audio.sfx('tick');
    toast('YOU SEARCH', 'Nothing here but stone and dust.', '');
    return;
  }
  if (!r.secret) {
    say('THE ALCOVE', [r.message], 'oracle');
    return;
  }
  audio.sfx('levelup');
  await refresh();
  const item = r.secret.item_detail;
  modal(`<h2 style="color:var(--red)">★ ${r.secret.name.toUpperCase()}</h2>
    <p>${r.secret.hint}</p>
    ${item ? `<div class="item-card" style="border-color:${item.rarity_colour}">
      <div class="grow"><div class="in" style="color:${item.rarity_colour}">${item.name}
        <span class="muted">· ${item.rarity}</span></div>
      <div class="ie">${item.effect_text.join(' · ')}</div>
      <div class="if">${item.flavour}</div></div></div>` : ''}
    <div class="actions"><button class="btn primary" id="sec-ok">TAKE IT</button></div>`);
  $('#sec-ok').onclick = closeModal;
}

function playStoryQueue() {
  const entry = (G.storyQueue || []).shift();
  if (!entry) return false;
  const speaker = entry.speaker_name || entry.speaker || 'THE SOURCE';
  const portraitKind = entry.portrait
    || (entry.speaker === 'narrator' ? 'oracle'
        : (G.world.mentors[entry.speaker] || {}).sprite) || 'scholar';
  const lines = (entry.lines || []).slice();
  if (entry.objective) lines.push(`OBJECTIVE — ${entry.objective}`);
  for (const r of entry.reward_summary || []) lines.push(`REWARD — ${r}`);
  audio.sfx(entry.kind === 'milestone' ? 'unlock' : 'select');
  say(String(speaker).toUpperCase(), lines, portraitKind);
  return true;
}

function returnToWorld() {
  clearInterval(G.timer);
  stopViz();
  // IncantationUI holds #puzzle-host, a document key listener and its own
  // clock. Leaving the screen without destroying it leaks all three.
  destroyIncant();
  destroyChild();
  // The companion card belongs to the fight, not to the screen behind it.
  partyui.clearIntervention();
  if (G.fx) G.fx.stop();
  document.body.classList.remove('interview-mode');
  G.encounter = null;
  G.interview = null;
  G.seal = null;
  audio.setIntensity(0);
  const region = currentRegion();
  audio.play(region.music || 'overworld');
  paintWorldSide();
  show('world');
}

$('#btn-run').onclick = doRun;
$('#btn-submit').onclick = doSubmit;
$('#btn-reset').onclick = () => {
  if (G.puzzle && G.problem) { renderPuzzle(G.problem); return; }
  if (G.problem) G.editor.reset(G.problem.starter_code || '');
};
$('#btn-flee').onclick = () => {
  say('RETREAT', ['Nothing is lost. The pattern stays in your schedule and will '
    + 'return when it is due.'], 'scholar');
  returnToWorld();
};

/* ---------------- incantation combat ---------------- */

/* A different fight entirely: no editor, no trials, no probes. You type one
 * line of real Python at a battlefield of live names, and it either binds to
 * them or it does not. IncantationUI owns #puzzle-host for the duration, which
 * is why enterBattle and returnToWorld both destroy it before touching that node. */

/* The server's enemy is a bound name; IncantationUI wants an id it can patch by.
 * The name IS the identity here — it is the thing the player types. */
function incantEnemies(inc) {
  return (inc.enemies || []).map(e => ({
    id: e.name, name: e.name, title: e.title, type: e.kind,
    value: e.binding, note: e.taunt,
    hp: e.hp, hp_max: e.hp_max, dead: !e.alive,
  }));
}

/* One rendered move, translated to the shape IncantationUI reads. */
function incantMoves(list) {
  return (list || []).map((m) => {
    const holes = m.holes || [];
    const fills = holes.map(h => h.prefilled || '');
    // A tier-0 scaffold only works if every hole it fills carries a real value.
    // `«the variable that takes the value»` is a label, not Python, and the
    // server refuses a line containing one — so a move whose scaffold is only
    // labels goes out at BLANKS rather than as a line that cannot be cast.
    const usable = fills.every(v => !v.includes('«')) && fills.some(v => v);
    const focus = holes.findIndex(h => h.editable);
    const scaffold = (m.tier === 0) && usable;
    return {
      id: m.id || m.incantation,
      name: m.name,
      template: m.template,
      teach: m.teach || m.note || '',
      tier: scaffold ? 0 : Math.max(1, Number(m.tier) || 0),
      prefill: scaffold ? fills : [],
      focus_hole: focus < 0 ? undefined : focus,
      locked: false,
    };
  });
}

/* The encounters a region offers. Shown as a list because an incantation fight
 * is chosen, not wandered into. */
async function showIncantList() {
  // A field left standing is still standing. Offer it back before offering a
  // new one, or the player silently abandons a fight they were winning.
  let open = null;
  try {
    const live = await api.incantState();
    if (live && live.incantation) open = live;
  } catch (e) { /* no run is the normal answer; the list still opens */ }

  let payload;
  try {
    payload = await api.incantations(currentRegion().id);
  } catch (e) { toast('NOBODY IS SPEAKING', e.message, 'red'); return; }
  if (payload.error) {
    toast('NOBODY IS SPEAKING', payload.message || payload.error, 'red');
    return;
  }
  G.incantCards = payload.encounters || [];
  const rows = G.incantCards.map(c => `<div class="list-item" data-enc="${c.id}">
      <span class="t">${c.title.toUpperCase()}</span>
      <span class="d">${c.blurb}<br>
        <span class="muted small">${(c.enemies || []).join(' · ')} — ${c.lesson}</span>
      </span></div>`).join('');
  const m = modal(`<h2>INCANTATIONS</h2>
    <p class="small">Every enemy here is a bound name. You attack by writing one
    line of Python that really does something to it — the line is parsed, bound
    and run. A wrong line costs the turn and says which of the three layers
    it broke at.</p>
    ${open ? `<div class="frame" style="padding:12px;margin-bottom:10px;
      border-color:var(--gold)">
      <div class="section-title">STILL STANDING</div>
      <p class="small">A field is open — turn ${open.incantation.turn || 0},
        ${(open.incantation.enemies || []).filter(e => e.alive).length} name(s)
        still on their feet.</p>
      <div class="actions">
        <button class="btn primary" id="inc-resume">GO BACK TO IT</button>
        <button class="btn danger" id="inc-drop">WALK AWAY FROM IT</button>
      </div></div>` : ''}
    ${rows || '<p class="small muted">Nothing is standing in this region.</p>'}
    <div class="actions"><button class="btn" id="m-close">WALK ON</button></div>`);
  const resume = m.querySelector('#inc-resume');
  if (resume) {
    resume.onclick = () => { closeModal(); enterIncantation(open); };
    m.querySelector('#inc-drop').onclick = async () => {
      await api.leaveIncant().catch(() => { /* it expires with the save */ });
      closeModal();
      showIncantList();
    };
  }
  m.querySelectorAll('[data-enc]').forEach(n => {
    n.onclick = () => { closeModal(); startIncantation(n.dataset.enc); };
  });
  m.querySelector('#m-close').onclick = closeModal;
}

async function startIncantation(encounterId) {
  let payload;
  try {
    payload = await api.startIncant(encounterId);
  } catch (e) { toast('THE WORDS WILL NOT COME', e.message, 'red'); return; }
  if (payload.error === 'sealed') { toast(sealedTitle(payload), payload.message, 'red'); return; }
  if (payload.error || !payload.incantation) {
    toast('THE WORDS WILL NOT COME', payload.message || payload.error
      || 'That battlefield could not be built.', 'red');
    return;
  }
  enterIncantation(payload);
}

function enterIncantation(payload) {
  // Whatever was holding the battle screen — an encounter, an older
  // incantation — is done with it now.
  destroyIncant();
  clearInterval(G.timer);
  stopViz();
  if (G.fx) G.fx.stop();
  G.encounter = null;
  G.problem = null;
  G.seal = null;
  G.interview = null;
  G.puzzle = null;
  G.incantRun = payload.incantation;
  G.startedAt = Date.now();

  const inc = payload.incantation;
  const card = G.incantCards.find(c => c.id === inc.encounter) || {};
  $('#problem-title').textContent = card.title || 'AN INCANTATION';
  $('#problem-statement').textContent = card.blurb
    || 'Names are standing in front of you. Say something true about them.';
  const meta = $('#problem-meta');
  meta.innerHTML = '';
  meta.appendChild(el('span', 'tag violet', 'INCANTATION'));
  if (card.chapter) meta.appendChild(el('span', 'tag', card.chapter));
  meta.appendChild(el('span', 'tag blue', `${(inc.enemies || []).length} names`));
  $('#problem-examples').innerHTML = card.lesson
    ? `<div class="muted small">${card.lesson}</div>` : '';

  const alive = (inc.enemies || []).filter(e => e.alive);
  const hp = alive.reduce((a, e) => a + e.hp, 0);
  const hpMax = (inc.enemies || []).reduce((a, e) => a + e.hp_max, 0) || 1;
  $('#enemy-name').textContent = (card.title || 'THE FIELD').toUpperCase();
  $('#enemy-hp').querySelector('i').style.width = `${(hp / hpMax) * 100}%`;
  $('#enemy-hp-label').textContent = `${hp} / ${hpMax}`;
  $('#battle-target').textContent = '—';

  // The editor and both primary buttons belong to the other kind of fight.
  // IncantationUI carries its own cast control.
  $('#editor-host').style.display = 'none';
  $('#btn-run').style.display = 'none';
  $('#btn-submit').style.display = 'none';
  $('#btn-reset').style.display = 'none';
  const host = $('#puzzle-host');
  host.style.display = '';
  host.innerHTML = '';

  // Trials, probes and spells all belong to the other kind of fight. One tab,
  // renamed to what it actually holds; applySeal puts the labels back.
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    b.style.display = b.dataset.tab === 'trials' ? '' : 'none';
    if (b.dataset.tab === 'trials') b.textContent = 'THE FIELD';
  }

  G.incant = new IncantationUI(host, {
    mode: 'adventure',
    audio,
    reducedMotion: !!(G.state && G.state.settings.reduced_motion),
    onCast: sendCast,
  });
  G.incant.setMoveset(incantMoves(payload.moveset));
  G.incant.setEncounter({
    id: inc.encounter, mode: 'adventure', turn: (inc.turn || 0) + 1,
    timer_seconds: inc.timer_seconds || 0,
    enemies: incantEnemies(inc),
  });

  startTimer();
  setTab('trials');
  show('battle');
  audio.play('battle');
}

/* IncantationUI hands back its own payload; the server door already speaks it.
 * The one adjustment is the NAME rung, where there are no holes and an empty
 * `holes` list would be read as "no answers" rather than "a whole line". */
async function sendCast(payload) {
  const body = { ...payload };
  if (body.raw !== null && body.raw !== undefined) delete body.holes;
  let r;
  try {
    r = await api.incantCast(body);
  } catch (e) {
    return { ok: false, layer: 'syntax', detail: e.message,
             teach: 'The cast never reached the server.' };
  }
  if (r.error === 'sealed') {
    toast(sealedTitle(r), r.message, 'red');
    return { ok: false, layer: 'semantics', detail: r.message, teach: '' };
  }
  if (r.error) {
    return { ok: false, layer: 'semantics', detail: r.error, teach: '' };
  }
  const inc = r.incantation || {};
  G.incantRun = inc;
  if (r.moveset && G.incant) G.incant.setMoveset(incantMoves(r.moveset));
  refresh().then(() => {}).catch(() => { /* refresh already said so */ });
  if (G.incant) setTab(G.tab);

  const enemies = incantEnemies(inc);
  const hp = enemies.filter(e => !e.dead).reduce((a, e) => a + e.hp, 0);
  const hpMax = enemies.reduce((a, e) => a + e.hp_max, 0) || 1;
  $('#enemy-hp').querySelector('i').style.width = `${(hp / hpMax) * 100}%`;
  $('#enemy-hp-label').textContent = `${hp} / ${hpMax}`;

  // Let the last hit land before the report. If the player walked out inside
  // those nine hundred milliseconds, there is nothing left to report on.
  if (r.cleared || inc.cleared) {
    setTimeout(() => { if (G.incant) finishIncantation(r); }, 900);
  }

  return {
    ok: !!r.correct,
    // The server's own layer names, plus `blank` for a line still holding a
    // gap. That is a line not yet formed, so it is reported as syntax.
    layer: INCANT_LAYER[r.layer] || 'semantics',
    detail: r.detail || r.teaching || '',
    teach: r.teaching || '',
    damage: r.damage,
    effect: r.effect,
    line: r.line,
    enemies,
    turn: (inc.turn || 0) + 1,
  };
}

const INCANT_LAYER = {
  syntax: 'syntax', binding: 'binding', semantics: 'semantics', blank: 'syntax',
};

function finishIncantation(result) {
  const cleared = !!(result && (result.cleared
    || (result.incantation || {}).cleared));
  destroyIncant();
  audio.sfx(cleared ? 'victory' : 'select');
  modal(`<h2 style="color:var(--gold-hi)">${cleared
      ? 'THE FIELD IS QUIET' : 'YOU STOP SPEAKING'}</h2>
    <p>${cleared
      ? 'Every name on that field answered to a line you wrote yourself. '
        + 'That is the only kind of fluency this game counts.'
      : 'The names are still standing. They will be standing tomorrow.'}</p>
    <div class="actions">
      <button class="btn primary" id="inc-more">SPEAK AGAIN</button>
      <button class="btn" id="inc-out">RETURN TO THE WORLD</button>
    </div>`);
  $('#inc-more').onclick = () => { closeModal(); returnToWorld(); showIncantList(); };
  $('#inc-out').onclick = () => { closeModal(); returnToWorld(); };
  refresh().catch(() => { /* refresh already said so */ });
}

/* Unmount and forget. Called from every path that takes #puzzle-host back:
 * entering any other encounter, leaving the battle screen, finishing a field. */
function destroyIncant() {
  const ui = G.incant;
  const running = G.incantRun;
  G.incant = null;
  G.incantRun = null;
  if (ui) {
    try { ui.destroy(); } catch (e) { /* a destroyed UI is still destroyed */ }
    const host = $('#puzzle-host');
    if (host) host.innerHTML = '';
  }
  // Tell the server the field is abandoned. Nothing waits on the answer, and a
  // run the server already cleared answers ok to this anyway.
  if (running) api.leaveIncant().catch(() => { /* it expires with the save */ });
}

/* The side panel during an incantation: who is on the field, what they are
 * bound to, and what the fight is asking for next. */
function paintIncantSide(body) {
  const inc = G.incantRun || {};
  const card = G.incantCards.find(c => c.id === inc.encounter) || {};
  if (card.lesson) body.appendChild(el('div', 'muted small', card.lesson));

  const demand = inc.demand || {};
  if (demand.name) {
    body.appendChild(el('div', 'section-title', 'WHAT THE FIELD DEMANDS'));
    body.appendChild(el('div', 'weakness',
      `<span class="wi" style="color:var(--violet)">❯</span>
       <div class="grow"><div class="wn" style="color:var(--violet)">${demand.name}</div>
       <div class="wt">${demand.suggested_target
         ? `Aimed at <code>${demand.suggested_target}</code>.`
         : 'Anything still standing.'}</div></div>`));
  }

  body.appendChild(el('div', 'section-title', 'ON THE FIELD'));
  for (const e of inc.enemies || []) {
    const pct = (e.hp / Math.max(1, e.hp_max)) * 100;
    body.appendChild(el('div', `test-line ${e.alive ? '' : 'pass'}`,
      `<span class="icon">${e.alive ? '·' : '✔'}</span>
       <div class="body">
         <div class="name">${e.name} <span class="muted small">${e.title} · ${e.kind}</span></div>
         <pre>${e.name} = ${e.binding}</pre>
         <div class="bar" style="margin-top:4px"><i style="width:${pct}%;
           background:${e.alive ? 'var(--red)' : 'var(--green)'}"></i></div>
         <div class="msg">${e.taunt}</div>
       </div>`));
  }

  const names = Object.keys(inc.bindings || {});
  if (names.length) {
    body.appendChild(el('div', 'section-title', 'EVERY NAME IN SCOPE'));
    body.appendChild(el('div', 'muted small',
      'Anything here can be typed. Only the ones above can be hit.'));
    body.appendChild(el('pre', 'spell-body',
      names.map(n => `${n} = ${inc.bindings[n]}`).join('\n')));
  }
}

/* ---------------- shrine ---------------- */

async function doShrine() {
  let q;
  try {
    q = await api.shrine();
  } catch (e) {
    toast('THE SHRINE IS SILENT', e.message, 'red');
    return;
  }
  audio.sfx('shrine');
  const m = modal(`<h2>MEMORY SHRINE</h2>
    <p style="font-size:16px;color:var(--ink)">${q.question}</p>
    <input id="shrine-answer" class="explain" style="min-height:auto;height:44px"
      placeholder="type your answer — ${q.seconds} seconds" autofocus>
    <div class="small muted" id="shrine-clock">${q.seconds}s</div>
    <div class="actions">
      <button class="btn primary" id="shrine-go">ANSWER</button>
      <button class="btn" id="shrine-skip">WALK ON</button>
    </div>`);
  const input = m.querySelector('#shrine-answer');
  input.focus();
  let left = q.seconds;
  // The clock lives on G so closeModal owns it: the backdrop, ESCAPE and any
  // modal that replaces this one all kill it. Without that the callback throws
  // on a missing #shrine-clock and keeps throwing, once a second, forever.
  G.modalTimer = setInterval(() => {
    const node = m.querySelector('#shrine-clock');
    if (!node || !node.isConnected) { clearInterval(G.modalTimer); return; }
    left--;
    node.textContent = left + 's';
    if (left <= 0) { clearInterval(G.modalTimer); submitShrine(); }
  }, 1000);

  async function submitShrine() {
    clearInterval(G.modalTimer);
    G.modalTimer = null;
    let r;
    try {
      r = await api.shrineAnswer(input.value);
    } catch (e) {
      closeModal();
      toast('THE SHRINE IS UNMOVED', e.message, 'red');
      return;
    }
    await refresh();
    closeModal();
    if (r.correct) {
      audio.sfx('shrine');
      toast('THE SHRINE ANSWERS', `+${r.xp} XP · focus and stamina restored.`, 'green');
    } else {
      toast('THE SHRINE IS SILENT', `The answer was "${r.expected}". `
        + 'It will ask again.', 'violet');
    }
    paintWorldSide();
  }
  m.querySelector('#shrine-go').onclick = submitShrine;
  m.querySelector('#shrine-skip').onclick = closeModal;
  input.onkeydown = (e) => { if (e.key === 'Enter') submitShrine(); };
}

/* ---------------- bosses ---------------- */

/* The mastery a region demands of its prerequisites (world.unlocked_regions).
 * Walking into a boss below it is legal and occasionally correct, but the
 * player should be told which one they are doing. */
const BOSS_READY_MASTERY = 25;

/* What the player is walking into, in the numbers we already have client-side.
 * The server only refuses the final boss, so everything else is a warning the
 * player can overrule — but never a surprise. */
function bossGate(b) {
  const region = G.state.regions.find(r => r.id === b.region);
  if (region && !region.unlocked) {
    return { open: false, label: 'SEALED', colour: 'red',
      why: `${region.name} is still sealed — build mastery in the regions before it.` };
  }
  if (b.final) {
    const castle = G.state.castle || {};
    if (!castle.open) {
      const owed = [];
      for (const d of castle.regions || []) {
        if (!d.met) owed.push(`${d.skill.replace(/_/g, ' ')} ${d.mastery}/${d.required}`);
      }
      if (castle.bosses && !castle.bosses.met) {
        owed.push(`bosses ${castle.bosses.cleared}/${castle.bosses.required}`);
      }
      if (castle.gates && !castle.gates.met) {
        owed.push(`readiness gates ${castle.gates.passed}/${castle.gates.required}`);
      }
      return { open: false, label: 'THE GATE IS SHUT', colour: 'red',
        why: owed.length ? `Still owed: ${owed.join(' · ')}.`
                         : 'The castle gate is not open yet.' };
    }
    // The gate is the final boss's readiness test, and it has been passed. No
    // per-skill warning on top of it.
    return { open: true, label: 'THE GATE IS OPEN', colour: 'gold',
      why: 'Every gate is met. This is the one you have been training for.' };
  }
  const skill = (G.state.skills || []).find(k => k.name === b.skill);
  const mastery = Math.round(skill ? skill.mastery : 0);
  if (mastery < BOSS_READY_MASTERY) {
    return { open: true, label: 'UNDER-PREPARED', colour: 'orange',
      why: `${b.skill.replace(/_/g, ' ')} mastery ${mastery}/${BOSS_READY_MASTERY}. `
        + 'You can fight it now; it will fight back at full strength.' };
  }
  return { open: true, label: '', colour: '',
    why: `${b.skill.replace(/_/g, ' ')} mastery ${mastery} — this is your weight class.` };
}

function showBossList(regionId) {
  const bosses = G.state.bosses.filter(b => !regionId || b.region === regionId);
  const gates = new Map();
  const list = (bosses.length ? bosses : G.state.bosses).map(b => {
    const best = b.records.filter(r => r.defeated)
      .reduce((a, r) => (a === null || r.seconds < a.seconds ? r : a), null);
    const gate = bossGate(b);
    gates.set(b.id, gate);
    return `<div class="list-item ${gate.open ? '' : 'locked'}" data-boss="${b.id}">
      <span class="t">${b.cleared ? '☑ ' : gate.open ? '' : '⚿ '}${b.name.toUpperCase()}
        ${gate.label ? `<span class="tag ${gate.colour}">${gate.label}</span>` : ''}</span>
      <span class="d">${b.taunt}<br>
      <span class="muted small">${b.region.replace(/_/g, ' ')} ·
      ${b.records.length} attempt(s)${best ? ` · best ${fmtTime(best.seconds)} rank ${best.rank}` : ''}
      <br>${gate.why}</span>
      </span></div>`;
  }).join('');
  const m = modal(`<h2>BOSSES</h2>
    <p class="small">A boss is never a wall. Fail one and it enters its teaching phase —
    a mentor arrives, the complexity is reduced, and you climb back up.</p>
    ${list}<div class="actions"><button class="btn" id="m-close">CLOSE</button></div>`);
  m.querySelectorAll('[data-boss]').forEach(n => {
    n.onclick = async () => {
      const gate = gates.get(n.dataset.boss) || { open: true };
      // A locked boss says why it is locked rather than handing out a fight the
      // player cannot win and a one-line error afterwards.
      if (!gate.open) { toast(gate.label, gate.why, 'red'); return; }
      closeModal();
      try {
        const payload = await api.startBoss(n.dataset.boss);
        if (payload.error) {
          toast('BOSS UNAVAILABLE', payload.message || payload.error, 'red');
          return;
        }
        enterBattle(payload);
      } catch (e) { toast('BOSS UNAVAILABLE', e.message, 'red'); }
    };
  });
  m.querySelector('#m-close').onclick = closeModal;
}

/* The teaching phase, rendered rather than promised: the mentor who arrives,
 * and the ladder of same-family problems that climbs back to the boss. */
async function paintBossTeaching(m, boss) {
  const art = m.querySelector('[data-portrait]');
  if (art) {
    const img = sprites.portrait(art.dataset.portrait || 'scholar');
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    canvas.style.cssText = 'width:56px;height:56px;image-rendering:pixelated';
    canvas.getContext('2d').drawImage(img, 0, 0);
    art.appendChild(canvas);
  }
  const host = m.querySelector('#boss-ladder');
  if (!host) return;
  try {
    const r = await api.bossLadder(boss.id);
    if (r.error) { host.innerHTML = ''; return; }
    host.innerHTML = `<h3>THE LADDER BACK UP</h3>
      <p class="small">${r.message}</p>`
      + r.ladder.map(rung => `<div class="list-item" data-problem="${rung.id}">
          <span class="t">${rung.title}</span>
          <span class="d">${rung.difficulty} · the same algorithm, one rung simpler</span>
          </div>`).join('');
    host.querySelectorAll('[data-problem]').forEach(n => {
      n.onclick = () => { closeModal(); startProblem(n.dataset.problem); };
    });
  } catch (e) {
    host.innerHTML = `<p class="small muted">The ladder could not be read — ${e.message}</p>`;
  }
}

/* ---------------- panels ---------------- */

function panel(title, html) {
  // Overwriting #panel-body tears a mounted child panel out of the document
  // without telling it, so it is told first. Every panel goes through here.
  destroyChild();
  $('#panel-body').innerHTML = `<h2 class="pixel" style="color:var(--gold);
    font-size:15px;margin:0 0 16px">${title}</h2>${html}`;
  show('panel');
}

function paintStatus() {
  const s = G.state;
  const r = s.readiness;
  const skills = s.skills.filter(k => k.attempts > 0 || k.mastery > 0);
  const rows = (skills.length ? skills : s.skills.slice(0, 12)).map(k =>
    `<div class="skill-row">
      <span class="sn">${k.name.replace(/_/g, ' ')}</span>
      <span class="bar"><i style="width:${k.mastery}%"></i></span>
      <span class="sv">${Math.round(k.mastery)}</span>
      <span class="stage">${k.stage}</span>
    </div>`).join('');

  const gates = r.gates.map(g =>
    `<div class="gate ${g.passed ? 'pass' : 'fail'}">
      <span class="mark">${g.passed ? '✔' : '·'}</span><span>${g.label}</span></div>`).join('');

  const dims = r.dimensions.map(d =>
    `<div class="skill-row"><span class="sn">${d.label}</span>
      <span class="bar"><i style="width:${d.score}%"></i></span>
      <span class="sv">${d.score}</span></div>`).join('');

  panel('STATUS', `
    <div class="grid2">
      <div class="frame" style="padding:14px">
        <div class="section-title">THE ARCHITECT</div>
        <p class="small">LV ${s.player.level} · ${s.player.title}<br>
          ${s.player.xp} XP · ${s.player.gold} gold · best combo ${s.player.best_combo}<br>
          Profile: <b style="color:var(--gold)">${s.player.profile}</b><br>
          Region: ${s.player.region.replace(/_/g, ' ')}</p>
        <div class="section-title">READINESS ${r.overall}%</div>
        ${dims}
        <p class="small" style="color:var(--violet);margin-top:10px">${r.verdict}</p>
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">READINESS GATES ${r.gates_passed}/${r.gates_total}</div>
        ${gates}
        <p class="small muted" style="margin-top:10px">
          Beating the final castle requires every gate. An average cannot substitute
          for a gate, because an interview will not average your answers either.</p>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">SKILLS — EVIDENCE, NOT EXPOSURE</div>
      ${rows}
    </div>
    <div class="grid2" style="margin-top:12px">
      <div class="frame" style="padding:14px">
        <div class="section-title">WEAPONS</div>
        ${G.world.weapons.map(w => {
          const tier = s.weapons[w.id] || 0;
          return `<div class="skill-row"><span class="sn">${w.name}</span>
            <span class="bar"><i style="width:${tier * 25}%;background:var(--gold)"></i></span>
            <span class="sv">${tier ? 'T' + tier : '—'}</span></div>`;
        }).join('')}
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">ACHIEVEMENTS ${s.achievements.length}/${G.world.achievements.length}</div>
        ${G.world.achievements.map(a =>
          `<div class="gate ${s.achievements.includes(a.id) ? 'pass' : 'fail'}">
            <span class="mark">${s.achievements.includes(a.id) ? '✔' : '·'}</span>
            <span>${a.name} <span class="muted small">— ${a.desc}</span></span></div>`).join('')}
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">COMPANIONS</div>
      ${G.world.companions.map(c => s.companions.includes(c.id)
        ? `<p class="small"><span class="tag green">${c.name}</span> "${c.line}"</p>`
        : `<p class="small muted"><span class="tag">${c.name}</span> ${c.unlock}</p>`).join('')}
    </div>`);
}

/* The board, from state.quests. The old panel rendered state.daily.quests — the
 * three-a-day chores — and called it the quest log while seventy-four authored
 * quests sat unreferenced behind it. */
function paintQuests() {
  const s = G.state;
  const board = s.quests || { available: [], active: [], done: [], locked: [], counts: {} };
  const counts = board.counts || {};

  const ladder = (s.ladder || []).map(r => `
    <div class="rung ${r.state}">
      <span class="rn">${r.number}</span>
      <span class="grow"><b>${r.title}</b> — ${r.goal}
        ${r.state === 'current'
          ? `<br><span class="muted small">${r.progress.clears}/${r.progress.clears_target} cleared · mastery ${r.progress.mastery}/${r.progress.mastery_target}</span>`
          : ''}</span>
      <span>${r.state === 'done' ? '✔' : r.state === 'current' ? `${r.progress.percent}%` : ''}</span>
    </div>`).join('');

  panel('QUEST LOG', `
    <div class="row" style="flex-wrap:wrap;margin-bottom:12px">
      <span class="tag gold">${counts.active || 0} RUNNING</span>
      <span class="tag green">${counts.available || 0} OFFERED</span>
      <span class="tag">${counts.done || 0} FINISHED</span>
      <span class="tag red">${(board.locked || []).length} LOCKED</span>
      <span class="tag violet">${counts.total || 0} IN THE WORLD</span>
    </div>
    <div id="q-active"></div>
    <div id="q-available"></div>
    <div id="q-locked"></div>
    <div id="q-done"></div>
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">WHOSE STORY THIS IS</div>
      <div id="q-chains"></div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">THE CURRICULUM</div>
      ${ladder || '<p class="small muted">No ladder yet.</p>'}
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">RETESTS DUE (${s.retests_due.length})</div>
      ${s.retests_due.length ? s.retests_due.map(r => `<div class="list-item">
        <span class="t">${r.family.replace(/_/g, ' ').toUpperCase()}</span>
        <span class="d">${r.days_overdue > 0 ? r.days_overdue + ' days overdue' : 'due now'}
          · interval stage ${r.stage}${r.lapses ? ` · ${r.lapses} lapse(s)` : ''}</span>
        </div>`).join('')
      : '<p class="small muted">Nothing due. Every pattern you have learned is currently within its interval.</p>'}
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">WEAKEST AREAS</div>
      ${s.weakness.length
        ? s.weakness.map(w => `<span class="tag red">${w.replace(/_/g, ' ')}</span> `).join('')
        : '<p class="small muted">Not enough evidence yet — play a few encounters.</p>'}
      <p class="small muted" style="margin-top:10px">
        These are computed from real failures, hint dependence and error rate.
        Never from how long you have been playing.</p>
    </div>
    <div class="actions">
      <button class="btn primary" id="q-next">NEXT ADAPTIVE ENCOUNTER</button>
    </div>`);

  questSection($('#q-active'), 'RUNNING', board.active || [],
    'Press REPORT IN to hand one back. If it is not finished yet, the giver '
    + 'says how far along it is instead of taking it.');
  questSection($('#q-available'), 'OFFERED NOW', board.available || [],
    'Ordered by story: the next step of somebody you already know comes before '
    + "a stranger's errand.");
  questSection($('#q-locked'), 'NOT YET OFFERED', (board.locked || []).slice(0, 12),
    'Closest first. Each one names the single thing standing in the way.');
  const done = board.done || [];
  questSection($('#q-done'), 'FINISHED', done.slice(-12).reverse(),
    done.length > 12 ? `The last twelve of ${done.length}.` : '');

  $('#q-next').onclick = () => startNext();
  showChains();
}

/* One section of the board, grouped by chain. A chain is somebody's life told
 * across four quests, so the log says whose life it is rather than listing four
 * unrelated errands. */
function questSection(host, title, entries, blurb) {
  if (!host) return;
  host.innerHTML = '';
  if (!entries.length) return;
  const frame = el('div', 'frame');
  frame.style.cssText = 'padding:14px;margin-bottom:12px';
  frame.appendChild(el('div', 'section-title', `${title} (${entries.length})`));
  if (blurb) frame.appendChild(el('div', 'muted small', blurb));

  // Insertion order is the server's order, and the server already sorted for
  // story. Grouping must not disturb it, so the first appearance of a chain
  // fixes that chain's position.
  const groups = new Map();
  for (const q of entries) {
    const key = q.chain || '';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(q);
  }
  for (const [chain, rows] of groups) {
    if (chain) {
      const first = rows[0];
      frame.appendChild(el('div', 'section-title',
        `${first.chain_title.toUpperCase()} — ${first.giver_name}`));
    } else if (groups.size > 1) {
      frame.appendChild(el('div', 'section-title', 'STANDING OFFERS'));
    }
    for (const q of rows) frame.appendChild(questRow(q));
  }
  host.appendChild(frame);
}

function questRow(q) {
  const locked = q.state === 'locked';
  const row = el('div', `list-item ${locked ? 'locked' : ''}`);
  row.style.cursor = 'default';
  const target = q.objective && (q.objective.count || q.objective.depth);
  row.innerHTML = `
    <span class="t">${locked ? '⚿ ' : q.state === 'done' ? '☑ ' : ''}${q.title}
      <span class="tag">${q.kind}</span>
      <span class="tag violet">${q.tier_name}</span>
      ${q.chain ? `<span class="tag blue">step ${q.step}/${q.steps}</span>` : ''}
      ${q.final_step ? '<span class="tag gold">LAST STEP</span>' : ''}</span>
    <span class="d">${q.premise}<br>
      <b style="color:var(--gold-hi)">${q.objective_text}</b>
      ${target > 1 ? ` <span class="muted small">(${target} of them)</span>` : ''}
      <br><span class="muted small">${q.giver_name} · ${q.region_name}
      ${q.reward_lines && q.reward_lines.length
        ? ' · pays ' + q.reward_lines.join(', ') : ''}</span>
      ${locked ? `<br><span class="tag red">STILL OWED</span>
        <span class="muted small">${q.blocked_by}${q.blocked_count > 1
          ? ` — and ${q.blocked_count - 1} more` : ''}</span>` : ''}
    </span>`;

  const progress = el('div');
  const actions = el('div', 'row');
  actions.style.marginTop = '8px';
  actions.style.flexWrap = 'wrap';

  if (q.state === 'available') {
    const take = el('button', 'btn small primary', 'ACCEPT');
    take.onclick = () => acceptQuest(q, take);
    const hear = el('button', 'btn small', 'HEAR THEM OUT');
    hear.onclick = () => showOffer(q);
    actions.append(take, hear);
  } else if (q.state === 'active') {
    const turn = el('button', 'btn small good', 'REPORT IN');
    turn.onclick = () => turnInQuest(q, turn, progress);
    const drop = el('button', 'btn small', 'PUT IT DOWN');
    drop.onclick = () => abandonQuest(q);
    actions.append(turn, drop);
  } else if (locked) {
    // Every requirement, not just the first, because the first is only the
    // nearest one and the player is entitled to the whole bill.
    for (const need of q.requirements || []) {
      progress.appendChild(el('div', `gate ${need.met ? 'pass' : 'fail'}`,
        `<span class="mark">${need.met ? '✔' : '·'}</span>
         <span>${need.text}${need.required > 1
           ? ` <span class="muted small">— ${need.current}/${need.required}</span>` : ''}</span>`));
    }
  }
  if (actions.children.length) row.appendChild(actions);
  row.appendChild(progress);
  return row;
}

async function acceptQuest(q, btn) {
  // Called from the row's own button and from the offer modal, which has none.
  const lock = (v) => { if (btn) btn.disabled = v; };
  lock(true);
  let r;
  try {
    r = await api.acceptQuest(q.id);
  } catch (e) { lock(false); toast('NOT TAKEN', e.message, 'red'); return; }
  if (r.error === 'sealed') { lock(false); toast(sealedTitle(r), r.message, 'red'); return; }
  if (r.refused) {
    lock(false);
    toast('NOT YET', r.blocked_by, 'red');
    return;
  }
  audio.sfx('unlock');
  say(q.giver_name.toUpperCase(), (r.lines || []).concat(
    r.objective ? [`OBJECTIVE — ${r.objective}`] : []), 'scholar');
  await refresh();
  paintQuests();
}

/* What the giver actually says when you walk up to them. The board row is the
 * summary; this is the scene, and it is the only place the setup lines exist. */
async function showOffer(q) {
  let offer;
  try {
    offer = await api.quest(q.id);
  } catch (e) { toast('NOBODY ANSWERS', e.message, 'red'); return; }
  if (offer.error) { toast('NOBODY ANSWERS', offer.message || offer.error, 'red'); return; }
  const m = modal(`<h2>${offer.title}</h2>
    <p class="small muted">${offer.giver_name} · ${offer.region_name} ·
      ${offer.tier_name}${offer.chain_title ? ` · ${offer.chain_title}` : ''}</p>
    ${offer.chain_premise ? `<p class="small">${offer.chain_premise}</p>` : ''}
    ${(offer.lines || []).map(l => `<p>${l}</p>`).join('')}
    <h3>WHAT IT ASKS</h3>
    <p>${offer.objective_text}
      <br><span class="muted small">${offer.kind_blurb || ''}</span></p>
    <h3>WHAT IT PAYS</h3>
    <p class="small">${(offer.reward_lines || []).join(' · ') || 'Nothing but the ending.'}</p>
    <div class="actions">
      <button class="btn primary" id="of-take">TAKE IT</button>
      <button class="btn" id="of-no">NOT NOW</button>
    </div>`);
  m.querySelector('#of-no').onclick = closeModal;
  m.querySelector('#of-take').onclick = () => {
    closeModal();
    acceptQuest(q);
  };
}

/* One person's whole arc, offered under the board. A chain is four quests about
 * the same life, so it is worth being able to read the life rather than the
 * four rows it was cut into. */
async function showChains() {
  const host = $('#q-chains');
  if (!host) return;
  host.innerHTML = '<p class="small muted">Reading the chains…</p>';
  let payload;
  try {
    payload = await api.chains();
  } catch (e) {
    if (host.isConnected) {
      host.innerHTML = `<p class="small muted">The chains could not be read — ${e.message}</p>`;
    }
    return;
  }
  if (!host.isConnected) return;   // the screen changed while this was in flight
  // A chain nobody has started is a list of four titles the player has no
  // context for. Show the ones that have moved, and the ones that are finished.
  const chains = (payload.chains || []).filter(c => c.done > 0
    || (c.steps || []).some(x => x.state === 'available'));
  if (!chains.length) {
    host.innerHTML = `<p class="small muted">No chain has opened yet. There are
      ${(payload.chains || []).length} of them in this world.</p>`;
    return;
  }
  const running = new Set(((G.state.quests || {}).active || []).map(x => x.id));
  host.innerHTML = chains.map(c => `
    <div class="list-item" style="cursor:default">
      <span class="t">${c.title.toUpperCase()} — ${c.giver_name}
        <span class="tag">${c.region_name}</span>
        <span class="tag ${c.complete ? 'green' : 'violet'}">${c.done}/${c.total}</span></span>
      <span class="d">${c.premise}
        ${(c.steps || []).map((step, i) => `<span class="rung ${
          step.state === 'done' ? 'done'
            : running.has(step.id) ? 'current'
            : step.state === 'locked' ? 'locked' : 'next'}">
          <span class="rn">${i + 1}</span>
          <span class="grow">${step.title}${step.state === 'locked' && step.blocked_by
            ? ` <span class="muted small">— ${step.blocked_by}</span>` : ''}</span>
          <span>${step.state === 'done' ? '✔' : running.has(step.id) ? '…' : ''}</span>
        </span>`).join('')}
        ${c.epilogue ? `<br><span class="small" style="color:var(--violet)">${
          c.epilogue}</span>` : ''}
      </span></div>`).join('');
}

async function abandonQuest(q) {
  const m = modal(`<h2>PUT IT DOWN</h2>
    <p>${q.title} goes back on the board. Nothing is lost — progress you have
    already made is kept, and ${q.giver_name} will offer it again.</p>
    <div class="actions">
      <button class="btn danger" id="ab-yes">PUT IT DOWN</button>
      <button class="btn" id="ab-no">KEEP IT</button>
    </div>`);
  m.querySelector('#ab-no').onclick = closeModal;
  m.querySelector('#ab-yes').onclick = async () => {
    closeModal();
    let r;
    try {
      r = await api.abandonQuest(q.id);
    } catch (e) { toast('STILL YOURS', e.message, 'red'); return; }
    if (r.error === 'sealed') { toast(sealedTitle(r), r.message, 'red'); return; }
    audio.sfx('select');
    await refresh();
    paintQuests();
  };
}

/* Handing a quest back is also how the log learns how far along it is: the
 * server refuses an unfinished one with its own progress numbers attached, so
 * the bar below is the server's count and not a guess. */
async function turnInQuest(q, btn, host) {
  btn.disabled = true;
  let r;
  try {
    r = await api.turnInQuest(q.id);
  } catch (e) { btn.disabled = false; toast('NOT ACCEPTED', e.message, 'red'); return; }
  btn.disabled = false;
  if (r.error === 'sealed') { toast(sealedTitle(r), r.message, 'red'); return; }
  if (r.error === 'not finished') {
    const p = r.progress || {};
    host.innerHTML = `
      <div class="skill-row" style="margin-top:8px">
        <span class="sn">PROGRESS</span>
        <span class="bar"><i style="width:${p.percent || 0}%"></i></span>
        <span class="sv">${p.current || 0}/${p.required || 1}</span></div>
      <div class="small muted">${p.text || q.objective_text}${
        p.failures !== undefined
          ? ` · ${p.failures}/${p.failures_allowed} allowed failures spent` : ''}</div>`;
    audio.sfx('tick');
    return;
  }
  if (r.error) { toast('NOT ACCEPTED', r.error, 'red'); return; }
  audio.sfx('levelup');
  if (r.chain_complete) {
    toast('A STORY ENDS', `${q.chain_title} is finished.`, 'violet');
  }
  const lines = (r.lines || []).concat(
    (r.consequence && r.consequence.npc_line) ? [r.consequence.npc_line] : [],
    r.reward_lines || []);
  if (lines.length) say(q.giver_name.toUpperCase(), lines, 'scholar');
  else toast('TURNED IN', `${q.title} — ${(q.reward_lines || []).join(', ')}`, 'gold');
  await refresh();
  paintQuests();
}

function paintGrimoire() {
  // state.grimoire is one list holding two id spaces: pattern names written by
  // the engine on a clear, and story card ids written by the narrative. Only the
  // pattern names match the deck below; the story cards are resolved to their
  // content by quest_log.cards, which is where they are rendered from.
  const earned = G.state.grimoire || [];
  const cards = {
    HASH_MAP: { when: 'you need fast lookup by key, or counts',
      signals: 'seen before, count, frequency, duplicate, pair, group by',
      model: 'trade memory for lookup speed', time: 'O(n)', space: 'O(n)',
      tpl: 'seen = {}\nfor i, v in enumerate(nums):\n    if target - v in seen:\n        return [seen[target-v], i]\n    seen[v] = i',
      fail: 'recording the value before checking it, so it pairs with itself' },
    SLIDING_WINDOW: { when: 'a contiguous range under a constraint',
      signals: 'contiguous, substring, subarray, longest, shortest, at most, at least',
      model: 'expand right; while invalid, shrink left', time: 'O(n)', space: 'O(k)',
      tpl: 'left = 0\nfor right in range(len(data)):\n    add(data[right])\n    while invalid():\n        remove(data[left])\n        left += 1\n    update_best()',
      fail: 'leaving zero-count keys in the dict so len() lies' },
    TWO_POINTER: { when: 'sorted input, or a converging/chasing scan',
      signals: 'sorted, pair, palindrome, in place, O(1) space',
      model: 'move whichever pointer can improve the answer', time: 'O(n)', space: 'O(1)',
      tpl: 'lo, hi = 0, len(data) - 1\nwhile lo < hi:\n    if too_small: lo += 1\n    elif too_big: hi -= 1\n    else: return ...',
      fail: 'using <= so an element pairs with itself' },
    BFS: { when: 'the shortest path in an unweighted graph or grid',
      signals: 'shortest, fewest steps, minimum moves, level by level',
      model: 'expand in rings; first arrival is shortest', time: 'O(V+E)', space: 'O(V)',
      tpl: 'q = deque([start]); seen = {start}\nwhile q:\n    node = q.popleft()\n    for nxt in neighbours(node):\n        if nxt not in seen:\n            seen.add(nxt); q.append(nxt)',
      fail: 'marking visited on pop instead of on push' },
    DFS: { when: 'explore everything, or enumerate all paths',
      signals: 'all paths, connected component, island, can you reach',
      model: 'commit to one path, then unwind', time: 'O(V+E)', space: 'O(V)',
      tpl: 'def walk(node):\n    if node in seen: return\n    seen.add(node)\n    for nxt in neighbours(node):\n        walk(nxt)',
      fail: 'a global visited set when you needed per-path backtracking' },
    STACK: { when: 'the most recent item matters most',
      signals: 'matching, nesting, undo, next greater, valid parentheses',
      model: 'LIFO; the top is what you can act on', time: 'O(n)', space: 'O(n)',
      tpl: 'stack = []\nfor item in items:\n    while stack and resolves(stack[-1], item):\n        stack.pop()\n    stack.append(item)',
      fail: 'forgetting to check the stack is empty at the end' },
    DP: { when: 'overlapping subproblems with reusable answers',
      signals: 'count the ways, minimum cost, longest subsequence, can you make',
      model: 'solve small, store, reuse', time: 'O(n·states)', space: 'O(n)',
      tpl: 'dp = [base] * (n + 1)\nfor i in range(1, n + 1):\n    dp[i] = combine(dp[i-1], dp[i-2], ...)',
      fail: 'greedy where the optimum needed the full table' },
    TREE: { when: 'hierarchical data with two children per node',
      signals: 'root, leaf, subtree, depth, ancestor, BST',
      model: 'ask both children, combine, return upward', time: 'O(n)', space: 'O(h)',
      tpl: 'def walk(node):\n    if node is None: return base\n    return combine(walk(node.left), walk(node.right), node.val)',
      fail: 'comparing a node only to its direct children in a BST check' },
    BINARY_SEARCH: { when: 'sorted data, or a monotonic predicate over an answer',
      signals: 'sorted, find the smallest X such that, O(log n) required',
      model: 'halve the search space every comparison', time: 'O(log n)', space: 'O(1)',
      tpl: 'lo, hi = 0, n - 1\nwhile lo <= hi:\n    mid = (lo + hi) // 2\n    if hit: return mid\n    if low: lo = mid + 1\n    else: hi = mid - 1',
      fail: 'lo = mid rather than mid + 1, which never terminates' },
  };
  const known = Object.keys(cards).filter(k => earned.includes(k));
  const storyCards = ((G.state.quest_log || {}).cards) || [];
  // Patterns you have demonstrated that no deck card has been written for yet.
  // Listing them is honest; dropping them is what made the old count wrong.
  const undocumented = earned.filter(k => !cards[k] && k === k.toUpperCase());
  const html = (known.length ? known : []).map(k => {
    const c = cards[k];
    return `<div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">${k.replace(/_/g, ' ')}</div>
      <p class="small"><b style="color:var(--gold)">WHEN</b> ${c.when}<br>
      <b style="color:var(--gold)">SIGNALS</b> ${c.signals}<br>
      <b style="color:var(--gold)">MENTAL MODEL</b> ${c.model}<br>
      <b style="color:var(--gold)">COST</b> ${c.time} time · ${c.space} space<br>
      <b style="color:var(--gold)">COMMON FAILURE</b> ${c.fail}</p>
      <pre class="spell-body">${c.tpl.replace(/</g, '&lt;')}</pre>
    </div>`;
  }).join('');
  const locked = Object.keys(cards).filter(k => !earned.includes(k))
    .map(k => `<span class="tag">${k.replace(/_/g, ' ')} — earn by solving</span> `).join('');

  const storyHtml = storyCards.map(c => `
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">${c.name.toUpperCase()}
        <span class="tag violet">${(c.pattern || '').replace(/_/g, ' ')}</span></div>
      <p class="small"><b style="color:var(--gold)">ASKED</b> ${c.front}<br>
      <b style="color:var(--gold)">ANSWERED</b> ${c.back}</p>
    </div>`).join('');

  panel('PATTERN GRIMOIRE', `
    <p class="small muted">Cards are earned by demonstrated use, not by walking into a
    region. ${known.length} of ${Object.keys(cards).length} pattern cards
    · ${storyCards.length} card(s) recovered from the story.</p>
    ${html || '<p class="small muted">No pattern card yet. Solve an encounter.</p>'}
    ${storyCards.length ? `<div class="section-title">RECOVERED FROM THE STORY</div>
      ${storyHtml}` : ''}
    ${undocumented.length ? `<div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">PROVEN, NOT YET WRITTEN UP</div>
      <p class="small muted">You have evidence in these families. The deck has no card
      for them yet.</p>
      ${undocumented.map(k => `<span class="tag green">${k.replace(/_/g, ' ')}</span> `).join('')}
    </div>` : ''}
    <div class="frame" style="padding:14px">
      <div class="section-title">NOT YET EARNED</div>${locked || '—'}</div>`);
}

function paintInterview() {
  const s = G.state;
  // A run that is already going is the only thing on this screen that matters.
  // Without this the only door back into a measured run is starting a second
  // one, which is the same as being told the first one is gone.
  const run = s.interview;
  const live = run ? `
    <div class="frame" style="padding:14px;margin-bottom:12px;border-color:var(--red)">
      <div class="section-title">A RUN IS OPEN</div>
      <p class="small">${run.format.replace(/_/g, ' ')} · question ${
        (run.index || 0) + 1} of ${(run.problem_ids || []).length} ·
        ${run.minutes} minutes on the clock, and it has not stopped.</p>
      <div class="row">
        <button class="btn primary" id="iv-resume">BACK TO THE QUESTION</button>
        <button class="btn danger" id="iv-abandon">END IT AND SEE THE REPORT</button>
      </div>
    </div>` : '';
  panel('INTERVIEW MODE', `
    ${live}
    <div class="frame" style="padding:16px">
      <p style="line-height:1.8">Interview Mode is sacred. Spells, the mentor, pattern
      names, the Grimoire and the coach are all withheld — enforced by the server,
      not merely hidden in this page. Everything is recorded: time to first code,
      runs, failed trials, syntax errors, final correctness and completion time.</p>
      <p class="small muted">The coach opens the moment the attempt is scored, and not
      one second earlier.</p>
      <div class="section-title">PROFILE</div>
      <div class="row" style="flex-wrap:wrap">
        ${['PRACTICAL', 'GENERAL_SWE', 'SECURITY_ENGINEERING', 'CUSTOM'].map(p =>
          `<button class="btn small ${s.player.profile === p ? 'primary' : ''}"
            data-profile="${p}">${p.replace(/_/g, ' ')}</button>`).join('')}
      </div>
      <p class="small muted" style="margin-top:8px">The PRACTICAL profile weights arrays,
      strings, hash maps, sets, sorting, sliding window, two pointers, matrices, trees,
      recursion, BFS/DFS, design, debugging, Big-O and testing — the publicly reported
      emphasis for that screen. These are historical patterns, never guaranteed
      questions.</p>
      <div class="section-title">FORMAT</div>
      <div class="row">
        <button class="btn primary" data-format="LIVE_SCREEN">LIVE SCREEN · 50 min · 2 problems</button>
        <button class="btn primary" data-format="GAUNTLET">THE GAUNTLET · 65 min · 4 problems</button>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">READINESS ${s.readiness.overall}% ·
        GATES ${s.readiness.gates_passed}/${s.readiness.gates_total}</div>
      <p class="small" style="color:var(--violet)">${s.readiness.verdict}</p>
    </div>`);
  if (run) {
    $('#iv-resume').onclick = async () => {
      try {
        enterBattle(await api.interviewCurrent());
      } catch (e) { toast('CANNOT RESUME', e.message, 'red'); }
    };
    $('#iv-abandon').onclick = () => confirmThen('END THE RUN',
      'The questions you have not answered are scored as unanswered. The report '
      + 'opens either way.', 'END IT', async () => {
        let report;
        try {
          report = await api.finishInterview();
        } catch (e) { toast('NOT ENDED', e.message, 'red'); return; }
        await refresh();
        showInterviewReport(report);
      });
  }
  document.querySelectorAll('[data-profile]').forEach(b => {
    b.onclick = async () => {
      try {
        await api.profile(b.dataset.profile);
      } catch (e) { toast('PROFILE UNCHANGED', e.message, 'red'); return; }
      await refresh();
      paintInterview();
    };
  });
  document.querySelectorAll('[data-format]').forEach(b => {
    b.onclick = async () => {
      let run;
      try {
        run = await api.startInterview(b.dataset.format, s.player.profile);
      } catch (e) { toast('CANNOT START', e.message, 'red'); return; }
      if (run.error) { toast('CANNOT START', run.error, 'red'); return; }
      const m = modal(`<h2>${run.label}</h2>
        <ul style="line-height:2;color:var(--ink-dim)">${run.rules.map(r => `<li>${r}</li>`).join('')}</ul>
        <p class="small muted">${run.problems.length} problems, rising in difficulty.
        The family is never named.</p>
        <div class="actions">
          <button class="btn danger" id="iv-go">BEGIN. THE CLOCK STARTS NOW.</button>
          <button class="btn" id="iv-cancel">NOT YET</button></div>`);
      m.querySelector('#iv-go').onclick = async () => {
        closeModal();
        try {
          enterBattle(await api.interviewCurrent());
        } catch (e) { toast('CANNOT START', e.message, 'red'); }
      };
      m.querySelector('#iv-cancel').onclick = closeModal;
    };
  });
}

function showInterviewReport(report) {
  document.body.classList.remove('interview-mode');
  audio.play('victory');
  const rows = report.results.map((r, i) =>
    `<div class="test-line ${r.solved ? 'pass' : 'fail'}">
      <span class="icon">${r.solved ? '✔' : '✖'}</span>
      <div class="body"><div class="name">Q${i + 1} — ${r.problem_id}</div>
      <div class="msg">${fmtTime(r.seconds)}${r.rank ? ' · rank ' + r.rank : ''}
      ${r.root_cause ? ' · ' + r.root_cause.replace(/_/g, ' ') : ''}</div></div></div>`).join('');
  modal(`<h2>INTERVIEW REPORT — ${report.score}%</h2>
    <p>${report.solved} of ${report.total} solved in ${fmtTime(report.seconds)}
      ${report.within_time ? '(within time)' : '(over time)'}.</p>
    ${rows}
    <h3>WHERE THE FAILURES CAME FROM</h3>
    <p class="small">
      Knowledge failures: ${report.breakdown.knowledge_failures} ·
      Implementation failures: ${report.breakdown.implementation_failures} ·
      Time failures: ${report.breakdown.time_failures}</p>
    <p style="color:var(--violet)">${report.verdict}</p>
    ${examDebriefHtml(report.debrief)}
    <p class="small muted">The coach is available again now.</p>
    <div class="actions"><button class="btn primary" id="iv-done">RETURN</button></div>`,
    { wide: true });
  $('#iv-done').onclick = () => {
    closeModal();
    returnToWorld();
    refresh().then(paintWorldSide).catch(() => { /* refresh already said so */ });
  };
}

/* The Practical Test's own debrief: segment by segment against its clock, what
 * the failures had in common, and what to drill. Absent for every other format,
 * and absent too when the exam was composed in a process that has since exited —
 * which the server says in `note` rather than guessing a score. */
function examDebriefHtml(debrief) {
  if (!debrief) return '';
  if (debrief.unavailable) {
    return `<h3>THE PRACTICAL TEST</h3><p class="small muted">${debrief.note}</p>`;
  }
  const segments = (debrief.segments || []).map(seg =>
    `<div class="skill-row">
      <span class="sn">${seg.label}</span>
      <span class="bar"><i style="width:${Math.min(100,
        (seg.spent_seconds / Math.max(1, seg.budget_seconds)) * 100)}%;
        background:${seg.over_budget ? 'var(--red)' : 'var(--green)'}"></i></span>
      <span class="sv">${seg.solved}/${seg.total}</span>
      <span class="stage">${seg.spent_clock} / ${seg.budget_clock}</span>
    </div>`).join('');
  const questions = (debrief.questions || []).map(q =>
    `<div class="test-line ${q.solved ? 'pass' : 'fail'}">
      <span class="icon">${q.solved ? '✔' : '✖'}</span>
      <div class="body"><div class="name">${q.label} — ${q.title}
        <span class="muted small">${q.difficulty} · ${q.role} · ${q.pattern
          ? q.pattern.replace(/_/g, ' ') : ''}</span></div>
        <div class="msg">${q.clock} against a ${q.target_clock} target${
          q.over_target ? ' — over' : ''}${q.root_cause
            ? ' · ' + q.root_cause.replace(/_/g, ' ') : ''}</div>
        ${q.assessment ? `<div class="msg">${q.assessment}</div>` : ''}
      </div></div>`).join('');
  return `<h3>${debrief.format_label || 'THE PRACTICAL TEST'} —
      ${debrief.solved}/${debrief.total} in ${debrief.clock}</h3>
    <p>${debrief.verdict}</p>
    ${segments}
    ${questions}
    ${debrief.signal_note ? `<p class="small"><span class="tag red">${
      (debrief.dominant_signal || '').replace(/_/g, ' ')}</span>
      ${debrief.signal_note}</p>` : ''}
    ${(debrief.drills || []).length ? `<h3>WHAT TO DRILL</h3>
      <ul style="line-height:1.9;color:var(--ink-dim)">${
        (debrief.drills || []).map(d => (typeof d === 'string' ? `<li>${d}</li>`
          : `<li><b style="color:var(--gold)">${(d.skill || '').replace(/_/g, ' ')}</b>
             — ${d.why || ''} <span class="muted small">${d.occurrences || 1}×</span></li>`
        )).join('')}</ul>` : ''}
    ${debrief.what_it_says ? `<p class="small muted">${debrief.what_it_says}</p>` : ''}`;
}

function paintCharacter() {
  const lo = G.state.loadout;
  const rar = lo.rarities;

  const slots = lo.slots.map(slot => {
    const item = lo.equipped[slot];
    return `<div class="slot ${item ? '' : 'empty'}" data-slot="${slot}">
      <span class="sl">${slot.toUpperCase()}</span>
      <span class="si" style="color:${item ? item.rarity_colour : ''}">
        ${item ? item.name : 'empty'}</span>
      ${item ? `<span class="small muted">${item.effect_text.join(' · ')}</span>` : ''}
    </div>`;
  }).join('');

  // The server already clamps `points` to what is unspent, so the extra steps
  // cost nothing but save a round trip and a full repaint per point.
  const spend = lo.unspent_points || 0;
  const attrs = Object.entries(lo.attribute_info).map(([key, info]) =>
    `<div class="attr-row">
      <span class="an" style="color:${info.colour}">${info.label.toUpperCase()}</span>
      <span class="av">${lo.attributes[key] || 0}</span>
      ${spend > 0
        ? `<button class="btn small" data-attr="${key}" data-points="1">+1</button>` : ''}
      ${spend >= 5
        ? `<button class="btn small" data-attr="${key}" data-points="5">+5</button>` : ''}
      ${spend > 1
        ? `<button class="btn small" data-attr="${key}" data-points="${spend}">ALL ${spend}</button>` : ''}
      <span class="ab">${info.blurb}</span>
    </div>`).join('');

  const inventory = lo.inventory.length
    ? lo.inventory.map(item => `<div class="item-card rarity-${
        String(item.rarity || 'common').toLowerCase()} ${item.equipped ? 'equipped' : ''}"
        data-item="${item.id}">
        <span class="item-art" data-art="${item.id}"></span>
        <div class="grow">
          <div class="in" style="color:${item.rarity_colour}">${item.name}
            <span class="muted">· ${rar[item.rarity].label} · ${item.slot}</span>
            ${item.equipped ? '<span style="color:var(--green)"> ✔ WORN</span>' : ''}</div>
          <div class="ie">${item.effect_text.join(' · ') || 'no effect'}</div>
          <div class="if">${item.flavour}</div>
        </div></div>`).join('')
    : '<p class="small muted">Nothing yet. Clear encounters — every victory rolls for loot, '
      + 'and bosses always drop something you can wear.</p>';

  const sets = Object.entries(lo.sets).map(([id, spec]) => {
    const active = (lo.active_sets || []).filter(a => a.id === id);
    const pieces = active.length ? active[0].pieces : 0;
    return `<div class="list-item">
      <span class="t" style="color:${pieces ? 'var(--gold-hi)' : 'var(--ink-faint)'}">
        ${spec.name.toUpperCase()} — ${pieces} piece(s)</span>
      <span class="d">${spec.blurb}<br>
      ${Object.entries(spec.bonuses).map(([n, eff]) =>
        `<span style="color:${pieces >= n ? 'var(--green)' : 'var(--ink-faint)'}">
          (${n}) ${Object.entries(eff).map(([k, v]) => k.replace(/_/g, ' ')).join(', ')}
        </span>`).join(' · ')}</span></div>`;
  }).join('');

  const secrets = lo.secrets.map(sec => `<div class="list-item">
    <span class="t" style="color:${sec.found ? 'var(--gold-hi)' : 'var(--ink-faint)'}">
      ${sec.found ? '★ ' + sec.name.toUpperCase() : '??? — UNDISCOVERED'}</span>
    <span class="d">${sec.found ? sec.condition : sec.hint}</span></div>`).join('');

  panel('GEAR &amp; BUILD', `
    ${lo.unspent_points ? `<div class="frame" style="padding:12px;margin-bottom:12px;
      border-color:var(--gold)">
      <span class="pixel" style="color:var(--gold-hi);font-size:11px">
        ${lo.unspent_points} UNSPENT POINT(S)</span>
      <p class="small muted" style="margin:6px 0 0">Spend them below. Points are permanent
      until you pay the Armorer to unpick them.</p></div>` : ''}
    <div class="grid2">
      <div class="frame" style="padding:14px">
        <div class="section-title">EQUIPPED${lo.build ? ' · ' + lo.builds[lo.build].name.toUpperCase() : ''}</div>
        <div class="slot-grid">${slots}</div>
        <div class="section-title">YOUR BUILD DOES</div>
        <p class="small" style="color:var(--green);line-height:1.8">
          ${lo.effect_text.join('<br>') || 'Nothing yet — equip something.'}</p>
        <p class="small muted">Every one of these changes the economics of a fight.
        None of them writes a line of Python for you, and none survive into
        Interview Mode.</p>
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">ATTRIBUTES</div>
        ${attrs}
        <div class="actions">
          <button class="btn small" id="ch-respec">RESPEC AT THE ARMORER</button>
        </div>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">INVENTORY (${lo.inventory.length})</div>
      ${inventory}
    </div>
    <div class="grid2" style="margin-top:12px">
      <div class="frame" style="padding:14px">
        <div class="section-title">SET BONUSES</div>${sets}
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">SECRETS ${lo.secrets.filter(x => x.found).length}/${lo.secrets.length}</div>
        ${secrets}
      </div>
    </div>`);

  // The art placeholders are filled after the panel exists, so each card gets a
  // live canvas rather than a data URL baked into the HTML string.
  const byId = Object.create(null);
  for (const item of lo.inventory) byId[item.id] = item;
  document.querySelectorAll('[data-art]').forEach(slot => {
    const item = byId[slot.dataset.art];
    if (item) slot.appendChild(itemIcon(item, 40));
  });

  document.querySelectorAll('[data-item]').forEach(node => {
    node.onclick = async () => {
      let r;
      try {
        r = await api.equip(node.dataset.item);
      } catch (e) { toast('CANNOT EQUIP', e.message, 'red'); return; }
      if (r.error) { toast('CANNOT EQUIP', r.error, 'red'); return; }
      audio.sfx('unlock');
      await refresh();
      paintCharacter();
    };
  });
  document.querySelectorAll('[data-slot]').forEach(node => {
    node.onclick = async () => {
      if (!lo.equipped[node.dataset.slot]) return;
      try {
        await api.unequip(node.dataset.slot);
      } catch (e) { toast('CANNOT UNEQUIP', e.message, 'red'); return; }
      audio.sfx('select');
      await refresh();
      paintCharacter();
    };
  });
  document.querySelectorAll('[data-attr]').forEach(node => {
    node.onclick = async () => {
      const points = Number(node.dataset.points) || 1;
      try {
        const r = await api.allocate(node.dataset.attr, points);
        if (r.error) { toast('CANNOT ALLOCATE', r.error, 'red'); return; }
      } catch (e) { toast('CANNOT ALLOCATE', e.message, 'red'); return; }
      audio.sfx('levelup');
      await refresh();
      paintCharacter();
    };
  });
  $('#ch-respec').onclick = async () => {
    let r;
    try {
      r = await api.respec();
    } catch (e) { toast('THE ARMORER DECLINES', e.message, 'red'); return; }
    if (r.error) { toast('THE ARMORER DECLINES', r.error, 'red'); return; }
    toast('RESPEC', `${r.points} points returned for ${r.cost} gold.`, 'green');
    await refresh();
    paintCharacter();
  };
}

function showLevelUp(levels, points) {
  audio.sfx('levelup');
  const lo = G.state.loadout;
  const attrs = Object.entries(lo.attribute_info).map(([key, info]) =>
    `<button class="btn" data-lvl-attr="${key}" style="text-align:left;
      border-color:${info.colour}">
      <span style="color:${info.colour}">${info.label.toUpperCase()}
        (${lo.attributes[key] || 0})</span><br>
      <span class="small muted" style="text-transform:none">${info.blurb}</span>
    </button>`).join('');
  const m = modal(`<h2 style="color:var(--gold-hi)">LEVEL ${G.state.player.level}</h2>
    <p class="pixel" style="color:var(--violet);font-size:11px">
      ${G.state.player.title.toUpperCase()}</p>
    <p>${levels > 1 ? levels + ' levels' : 'A level'} gained.
      <b style="color:var(--gold-hi)">${points} attribute point(s)</b> to spend.</p>
    <div class="stack" style="margin-top:12px">${attrs}</div>
    <div class="actions">
      <button class="btn" id="lvl-later">SPEND THEM LATER</button>
    </div>`);
  m.querySelectorAll('[data-lvl-attr]').forEach(b => {
    b.onclick = async () => {
      let r;
      try {
        r = await api.allocate(b.dataset.lvlAttr, 1);
      } catch (e) { closeModal(); toast('CANNOT ALLOCATE', e.message, 'red'); return; }
      if (r.error) { closeModal(); return; }
      audio.sfx('unlock');
      await refresh();
      if (G.state.loadout.unspent_points > 0) {
        showLevelUp(0, G.state.loadout.unspent_points);
      } else {
        closeModal();
        toast('POINTS SPENT', 'Your build has changed shape.', 'green');
      }
    };
  });
  m.querySelector('#lvl-later').onclick = closeModal;
}

/* The reward moment: a rarity burst, a beam, and the item rising into a bob.
 * A drop the player did not see is a drop that did not happen. */
function showLootDrop(drop) {
  if (!drop || drop.kind === 'consumable') return;
  const host = document.createElement('div');
  host.className = 'loot-drop-stage';
  const canvas = document.createElement('canvas');
  canvas.width = 192; canvas.height = 128;
  canvas.style.cssText = 'width:288px;height:192px;image-rendering:pixelated';
  host.appendChild(canvas);
  const target = $('#modal');
  const anchor = target && target.querySelector('.loot-anchor');
  (anchor || document.body).appendChild(host);
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const reduced = !!(G.state && G.state.settings.reduced_motion);
  const started = performance.now();
  const DURATION = 1400;
  const step = () => {
    // closeModal only hides #modal-bg; the canvas stays in the document until the
    // next modal overwrites it. Without this check the bob loop keeps running
    // against a screen nobody is looking at.
    if (!canvas.isConnected || !$('#modal-bg').classList.contains('show')) return;
    const now = performance.now();
    const t = Math.min(1, (now - started) / DURATION);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    lootart.drawLootDrop(ctx, drop, 96, 104,
      { t: reduced ? 1 : t, time: now, scale: 2, reducedMotion: reduced });
    if (t < 1 || !reduced) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function lootHtml(drop) {
  if (!drop) return '';
  if (drop.kind === 'consumable') {
    return `<h3>LOOT</h3><p><span class="tag green">${drop.name}</span>
      ${drop.blurb}</p>`;
  }
  return `<h3>LOOT</h3>
    <div class="loot-anchor center"></div>
    <div class="item-card rarity-${String(drop.rarity || 'common').toLowerCase()}"
         style="border-color:${drop.rarity_colour}">
      <div class="grow">
        <div class="in" style="color:${drop.rarity_colour}">${drop.name}
          <span class="muted">· ${drop.rarity} · ${drop.slot}</span>
          ${drop.auto_equipped ? '<span style="color:var(--green)"> ✔ EQUIPPED</span>' : ''}</div>
        <div class="ie">${drop.effect_text.join(' · ')}</div>
        <div class="if">${drop.flavour}</div>
      </div></div>`;
}

function paintSettings() {
  const s = G.state.settings;
  panel('MENU', `
    <div class="grid2">
      <div class="frame" style="padding:14px">
        <div class="section-title">ACCESSIBILITY</div>
        ${[['music', 'Audio on'], ['crt', 'CRT scanlines'],
           ['reduced_motion', 'Reduced motion'], ['high_contrast', 'High contrast']]
          .map(([k, label]) => `<label class="row" style="margin:8px 0;cursor:pointer">
            <input type="checkbox" data-setting="${k}" ${s[k] ? 'checked' : ''}>
            <span>${label}</span></label>`).join('')}
        <div class="section-title">MIXER</div>
        ${[['vol_master', 'Master', s.vol_master],
           ['vol_music', 'Music', s.vol_music],
           ['vol_sfx', 'Sound effects', s.vol_sfx]]
          .map(([k, label, value]) => `
            <label class="row" style="margin:9px 0">
              <span style="flex:0 0 120px">${label}</span>
              <input type="range" min="0" max="1" step="0.02"
                     value="${value === undefined ? 0.7 : value}"
                     data-setting="${k}" style="flex:1">
              <span class="small muted" data-readout="${k}"
                    style="flex:0 0 42px;text-align:right">${
                      Math.round((value === undefined ? 0.7 : value) * 100)}%</span>
            </label>`).join('')}
        <div class="actions">
          <button class="btn small" id="s-test">TEST THE RIG</button>
        </div>
        <label class="row" style="margin:8px 0">
          <span class="grow">Text scale</span>
          <input type="range" min="0.85" max="1.5" step="0.05" value="${s.text_scale || 1}"
            data-setting="text_scale">
        </label>
        <p class="small muted">Adventure Mode timers are advisory only. Interview Mode
        uses standardised constraints so the measurement stays comparable.</p>
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">SAVE</div>
        <p class="small muted">Progress saves automatically after every action, locally.
        Nothing leaves this machine.</p>
        <div class="actions">
          <button class="btn" id="s-export">EXPORT SAVE</button>
          <button class="btn" id="s-import">IMPORT SAVE</button>
        </div>
        <div class="section-title">PLACEMENT</div>
        <p class="small muted">The Trial of the Architect decides where on the ladder
        you start. ${G.state.diagnostic_done ? 'You have taken it.' : 'You have not taken it.'}</p>
        <div class="actions">
          <button class="btn" id="s-diagnostic">${G.state.diagnostic_done
            ? 'RETAKE THE TRIAL' : 'TAKE THE TRIAL'}</button>
        </div>
        <div class="section-title">SANDBOX</div>
        <div id="sandbox-status" class="small muted">checking…</div>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">PERFORMANCE HISTORY</div>
      <div id="history-body" class="small muted">loading…</div>
    </div>`);

  document.querySelectorAll('[data-setting]').forEach(input => {
    const apply = (value) => {
      // The mixer must move the moment the fader does. Waiting on a round trip
      // to the server makes a volume slider feel broken.
      if (input.dataset.setting === 'vol_master') audio.setMaster(value);
      if (input.dataset.setting === 'vol_music') audio.setMusic(value);
      if (input.dataset.setting === 'vol_sfx') audio.setSfx(value);
      const readout = document.querySelector(
        `[data-readout="${input.dataset.setting}"]`);
      if (readout) readout.textContent = Math.round(value * 100) + '%';
    };
    input.oninput = () => {
      if (input.type === 'range') apply(parseFloat(input.value));
    };
    input.onchange = async () => {
      const value = input.type === 'checkbox' ? input.checked : parseFloat(input.value);
      if (input.type === 'range') apply(value);
      try {
        await api.setting(input.dataset.setting, value);
      } catch (e) { toast('SETTING NOT SAVED', e.message, 'red'); return; }
      await refresh();
    };
  });
  const test = $('#s-test');
  if (test) {
    test.onclick = () => {
      audio.resume();
      audio.play('battle');
      audio.sfx('crit');
      toast('THE RIG', 'Thrash track and a pinch harmonic. Adjust the faders while '
        + 'it plays.', 'gold');
    };
  }
  $('#s-export').onclick = async () => {
    let data;
    try {
      data = await api.exportSave();
    } catch (e) { toast('EXPORT FAILED', e.message, 'red'); return; }
    const blob = new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'gauntlet-save.json';
    a.click();
    toast('EXPORTED', 'gauntlet-save.json written to your Downloads.', 'green');
  };
  $('#s-import').onclick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = async () => {
      let payload;
      try {
        payload = JSON.parse(await input.files[0].text());
      } catch (e) {
        toast('NOT A SAVE FILE', 'That file is not readable JSON.', 'red');
        return;
      }
      let res;
      try {
        res = await api.importSave(payload);
      } catch (e) { toast('IMPORT REFUSED', e.message, 'red'); return; }
      if (res && res.ok === false) {
        toast('IMPORT REFUSED', res.error || 'That save could not be read.', 'red');
        return;
      }
      // Region node and chest caches are local to this browser and would
      // otherwise describe the previous save's world on top of the imported one.
      for (const key of Object.keys(localStorage)) {
        if (key.startsWith('gauntlet-nodes-') || key.startsWith('gauntlet-chest-')) {
          localStorage.removeItem(key);
        }
      }
      await refresh();
      toast('IMPORTED', 'Save restored.', 'green');
    };
    input.click();
  };

  $('#s-diagnostic').onclick = () => {
    const taken = G.state.diagnostic_done;
    const m = modal(`<h2>THE TRIAL OF THE ARCHITECT</h2>
      <p>Five short questions that decide where on the ladder you start.</p>
      ${taken ? `<p class="small" style="color:var(--orange)">You have already been
        placed. Taking it again re-seeds the placement mastery and lowers confidence
        on those skills — it re-reads the evidence rather than adding to it. Nothing
        you have solved is erased.</p>` : ''}
      <div class="actions">
        <button class="btn primary" id="dg-again">${taken ? 'TAKE IT AGAIN' : 'BEGIN'}</button>
        <button class="btn" id="dg-never">NOT NOW</button>
      </div>`);
    m.querySelector('#dg-again').onclick = () => { closeModal(); runDiagnostic(); };
    m.querySelector('#dg-never').onclick = closeModal;
  };

  api.sandboxCheck().then(c => {
    $('#sandbox-status').innerHTML = `
      Seatbelt: ${c.hardened ? '<span style="color:var(--green)">active</span>'
        : '<span style="color:var(--orange)">unavailable — resource limits only</span>'}<br>
      Network from your code: ${c.network_blocked
        ? '<span style="color:var(--green)">blocked</span>'
        : '<span style="color:var(--red)">NOT blocked</span>'}<br>
      Infinite loops: ${c.timeout_enforced
        ? '<span style="color:var(--green)">stopped</span>'
        : '<span style="color:var(--red)">not stopped</span>'}<br>
      Interpreter: ${c.interpreter}`;
  }).catch((e) => {
    $('#sandbox-status').textContent = `Could not verify the sandbox — ${e.message}`;
  });

  api.history().then(h => {
    const rows = h.recent.slice(0, 18).map(a =>
      `<div class="test-line ${a.solved ? 'pass' : 'fail'}">
        <span class="icon">${a.solved ? '✔' : '✖'}</span>
        <div class="body"><div class="name">${a.problem_id}
          <span class="muted">${a.difficulty} · ${a.mode}</span></div>
        <div class="msg">${fmtTime(a.seconds)}${a.rank ? ' · rank ' + a.rank : ''}
        ${a.hints_used ? ' · ' + a.hints_used + ' spell(s)' : ' · unaided'}
        ${a.root_cause ? ' · ' + a.root_cause.replace(/_/g, ' ') : ''}</div></div></div>`).join('');
    $('#history-body').innerHTML = `
      <p>${h.stats.solved}/${h.stats.total} cleared · ${h.stats.unaided} unaided ·
      ${h.stats.first_try} on the first submission ·
      median ${fmtTime(h.stats.avg_seconds || 0)}</p>${rows || 'No attempts yet.'}`;
  }).catch((e) => {
    $('#history-body').textContent = `Could not read your history — ${e.message}`;
  });
}

/* ---------------- saves ---------------- */

function slotWhen(seconds) {
  if (!seconds) return '';
  const d = new Date(seconds * 1000);
  return d.toLocaleString(undefined,
    { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function slotBytes(n) {
  if (!n) return '';
  return n > 1024 ? `${Math.round(n / 1024)} KB` : `${n} B`;
}

/* A slot the client must not offer to load. `ok:false` is the server's verdict
 * when it has one; an empty slot has nothing to load and a corrupt one has
 * something that will not decode. Both are shown, both say why. */
function slotBroken(row) {
  if (row.ok === false && !row.empty) return true;
  return !!row.status && !['ok', 'empty', 'unchecked'].includes(row.status);
}

async function paintSaves() {
  panel('SAVES', `
    <p class="small">Sixteen slots: manual, automatic and one undo. Autosaves are
    written for you after a region, a boss and a turned-in quest. Nothing here
    overwrites anything without asking first.</p>
    <div id="saves-head" class="row" style="flex-wrap:wrap;margin-bottom:10px"></div>
    <div id="saves-body"><p class="small muted">Reading the slots…</p></div>`);

  let payload;
  try {
    payload = await api.saves();
  } catch (e) {
    // The player may have walked to another screen while this was in flight.
    // Writing into a node that is no longer in the document throws; say nothing.
    if ($('#saves-body')) {
      $('#saves-body').innerHTML = `<p class="small" style="color:var(--red)">
        The slots could not be read — ${e.message}</p>`;
    }
    return;
  }
  if (!$('#saves-body')) return;
  if (payload.error) {
    $('#saves-body').innerHTML = `<p class="small" style="color:var(--red)">
      ${payload.message || payload.error}</p>`;
    return;
  }

  const head = $('#saves-head');
  head.innerHTML = '';
  const undo = el('button', 'btn small', 'UNDO THE LAST LOAD');
  undo.disabled = !payload.undo_available;
  undo.title = payload.undo_available
    ? 'Puts back the game that was running before the last load.'
    : 'Nothing has been loaded over, so there is nothing to put back.';
  undo.onclick = () => confirmThen('UNDO THE LAST LOAD',
    'This puts back the game that was running immediately before the last load. '
    + 'The game you are in now is the one that goes away.', 'PUT IT BACK',
    async () => {
      let r;
      try {
        r = await api.undoLoad();
      } catch (e) { toast('NOT UNDONE', e.message, 'red'); return; }
      if (r.error) { toast('NOT UNDONE', r.message || r.error, 'red'); return; }
      audio.sfx('unlock');
      await refresh();
      toast('PUT BACK', 'The previous game is running again.', 'green');
      loadRegion(G.state.player.region);
      returnToWorld();
    });
  const imp = el('button', 'btn small', 'IMPORT A FILE INTO A SLOT');
  imp.onclick = () => importIntoSlot();
  head.append(undo, imp);

  const body = $('#saves-body');
  body.innerHTML = '';
  const kinds = [['manual', 'YOUR SLOTS'], ['auto', 'AUTOSAVES'], ['undo', 'UNDO']];
  for (const [kind, label] of kinds) {
    const rows = (payload.slots || []).filter(r => r.kind === kind);
    if (!rows.length) continue;
    const frame = el('div', 'frame');
    frame.style.cssText = 'padding:14px;margin-bottom:12px';
    frame.appendChild(el('div', 'section-title', label));
    if (kind === 'auto') {
      frame.appendChild(el('div', 'muted small',
        'Written by the game, oldest overwritten first. You can load one; you '
        + 'cannot save into one.'));
    }
    for (const row of rows) frame.appendChild(slotRow(row));
    body.appendChild(frame);
  }
}

function slotRow(row) {
  const broken = slotBroken(row);
  const sum = row.summary || {};
  // .locked is for content the player cannot act on. An empty slot is the one
  // they can act on most — it is where a save goes — so only a broken one dims.
  const node = el('div', `list-item ${broken ? 'broken' : ''} ${
    row.empty ? 'slot-empty' : ''}`);
  node.style.cursor = 'default';
  // The server writes `message` for exactly this: a slot that cannot be loaded
  // says so on hover rather than being quietly removed from the list.
  if (row.message) node.title = row.message;
  node.innerHTML = `
    <span class="t">${row.name || row.slot_id}
      ${row.empty ? '<span class="tag">EMPTY</span>' : ''}
      ${broken ? `<span class="tag red">${(row.status || 'unreadable').toUpperCase()}</span>` : ''}
      ${row.reason_label ? `<span class="tag violet">${row.reason_label}</span>` : ''}</span>
    <span class="d">${row.empty
      ? 'Nothing saved here.'
      : `LV ${sum.level} ${sum.title || ''} · ${sum.chapter_title || ''}<br>
         <span class="muted small">${sum.region || ''} · ${sum.playtime || ''} played ·
         ${sum.solved || 0} cleared · ${sum.bosses_cleared || 0} boss(es) ·
         readiness ${sum.readiness || 0}%<br>
         ${slotWhen(row.created_at)}${row.bytes ? ' · ' + slotBytes(row.bytes) : ''}
         ${sum.in_encounter ? ' · saved mid-encounter' : ''}</span>`}
      ${broken && row.message ? `<br><span class="tag red">WILL NOT LOAD</span>
        <span class="muted small">${row.message}</span>` : ''}
    </span>`;

  const actions = el('div', 'row');
  actions.style.cssText = 'margin-top:8px;flex-wrap:wrap';

  if (!row.empty && !broken) {
    const load = el('button', 'btn small primary', 'LOAD');
    load.onclick = () => confirmThen(`LOAD ${(row.name || row.slot_id).toUpperCase()}`,
      'The game you are playing right now is replaced by this one. It is kept '
      + 'in the undo slot, so this is reversible exactly once.', 'LOAD IT',
      async () => {
        let r;
        try {
          r = await api.loadSlot(row.slot_id);
        } catch (e) { toast('NOT LOADED', e.message, 'red'); return; }
        if (r.error === 'sealed') { toast(sealedTitle(r), r.message, 'red'); return; }
        if (r.error) { toast('NOT LOADED', r.message || r.error, 'red'); return; }
        audio.sfx('unlock');
        await refresh();
        toast('LOADED', `${row.name} is running. UNDO is available.`, 'green');
        // A load can happen with an encounter still open behind the panel.
        // returnToWorld tears that down; show('world') would only hide it.
        loadRegion(G.state.player.region);
        returnToWorld();
      });
    actions.appendChild(load);
  }

  if (row.kind === 'manual') {
    const save = el('button', 'btn small good', row.empty ? 'SAVE HERE' : 'OVERWRITE');
    save.onclick = () => {
      const write = async (name) => {
        let r;
        try {
          r = await api.saveSlot(row.ordinal, name, '');
        } catch (e) { toast('NOT SAVED', e.message, 'red'); return; }
        if (r.error) { toast('NOT SAVED', r.message || r.error, 'red'); return; }
        audio.sfx('select');
        toast('SAVED', `${name || row.name} written.`, 'green');
        paintSaves();
      };
      if (row.empty) { askName('SAVE HERE', row.name, write); return; }
      confirmThen(`OVERWRITE ${(row.name || row.slot_id).toUpperCase()}`,
        'What is in this slot goes away and cannot be recovered. The undo slot '
        + 'only ever holds the game you loaded over, never a save you replaced.',
        'OVERWRITE IT', () => askName('NAME THIS SAVE', row.name, write));
    };
    actions.appendChild(save);
  }

  if (!row.empty) {
    const rename = el('button', 'btn small', 'RENAME');
    rename.onclick = () => askName('RENAME', row.name, async (name) => {
      if (!name) return;
      let r;
      try {
        r = await api.renameSlot(row.slot_id, name);
      } catch (e) { toast('NOT RENAMED', e.message, 'red'); return; }
      if (r.error) { toast('NOT RENAMED', r.message || r.error, 'red'); return; }
      paintSaves();
    });
    const exp = el('button', 'btn small', 'EXPORT');
    exp.onclick = async () => {
      let r;
      try {
        r = await api.exportSlot(row.slot_id);
      } catch (e) { toast('NOT EXPORTED', e.message, 'red'); return; }
      if (r.error) { toast('NOT EXPORTED', r.message || r.error, 'red'); return; }
      const blob = new Blob([JSON.stringify(r, null, 1)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `gauntlet-${row.slot_id.replace(':', '-')}.json`;
      a.click();
      // The object URL holds the whole envelope in memory until it is revoked.
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast('EXPORTED', `${a.download} written to your Downloads.`, 'green');
    };
    const del = el('button', 'btn small danger', 'DELETE');
    del.onclick = () => confirmThen(`DELETE ${(row.name || row.slot_id).toUpperCase()}`,
      'This save is gone for good. There is no undo for a delete — undo only '
      + 'ever holds the game you loaded over.', 'DELETE IT', async () => {
        let r;
        try {
          r = await api.deleteSlot(row.slot_id);
        } catch (e) { toast('NOT DELETED', e.message, 'red'); return; }
        if (r.error) { toast('NOT DELETED', r.message || r.error, 'red'); return; }
        audio.sfx('fail');
        paintSaves();
      });
    actions.append(rename, exp, del);
  }

  if (actions.children.length) node.appendChild(actions);
  return node;
}

/* One shape for every destructive press: what it does, what it costs, and a
 * way out that is the default. */
function confirmThen(title, body, verb, fn) {
  const m = modal(`<h2>${title}</h2><p>${body}</p>
    <div class="actions">
      <button class="btn danger" id="cf-yes">${verb}</button>
      <button class="btn primary" id="cf-no">NEVER MIND</button>
    </div>`);
  m.querySelector('#cf-no').onclick = closeModal;
  m.querySelector('#cf-yes').onclick = () => { closeModal(); fn(); };
}

function askName(title, value, fn) {
  const m = modal(`<h2>${title}</h2>
    <input id="nm-in" class="explain" style="min-height:auto;height:44px"
      value="${(value || '').replace(/"/g, '&quot;')}" maxlength="60">
    <div class="actions">
      <button class="btn primary" id="nm-ok">CONFIRM</button>
      <button class="btn" id="nm-no">CANCEL</button>
    </div>`);
  const input = m.querySelector('#nm-in');
  input.focus();
  input.select();
  const go = () => { const v = input.value.trim(); closeModal(); fn(v); };
  m.querySelector('#nm-ok').onclick = go;
  m.querySelector('#nm-no').onclick = closeModal;
  input.onkeydown = (e) => { if (e.key === 'Enter') go(); };
}

function importIntoSlot() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'application/json';
  input.onchange = async () => {
    let payload;
    try {
      payload = JSON.parse(await input.files[0].text());
    } catch (e) {
      toast('NOT A SAVE FILE', 'That file is not readable JSON.', 'red');
      return;
    }
    askName('IMPORT INTO WHICH SLOT? (1-8)', '1', async (ordinal) => {
      const n = Number(ordinal);
      if (!Number.isInteger(n) || n < 1) {
        toast('NOT IMPORTED', 'That is not a slot number.', 'red');
        return;
      }
      let r;
      try {
        r = await api.importSlot(payload, n, '');
      } catch (e) { toast('IMPORT REFUSED', e.message, 'red'); return; }
      if (r.error) { toast('IMPORT REFUSED', r.message || r.error, 'red'); return; }
      toast('IMPORTED', `Written into slot ${n}. Load it when you want it.`, 'green');
      paintSaves();
    });
  };
  input.click();
}

/* ---------------- the final exam ---------------- */

/* Fourteen bosses, each taking exactly one thing and never giving it back. This
 * is the spine of the whole game, so it is drawn as a ladder rather than
 * described in a paragraph: what is gone by each rung, and what is still yours. */
async function paintExam() {
  panel('THE PRACTICAL TEST', `
    <div id="exam-body"><p class="small muted">Reading the ladder…</p></div>`);
  let payload;
  try {
    payload = await api.examLadder();
  } catch (e) {
    if ($('#exam-body')) {
      $('#exam-body').innerHTML = `<p class="small" style="color:var(--red)">
        The ladder could not be read — ${e.message}</p>`;
    }
    return;
  }
  if (!$('#exam-body')) return;   // the screen changed while this was in flight
  if (payload.error) {
    $('#exam-body').innerHTML = `<p class="small" style="color:var(--red)">
      ${payload.message || payload.error}</p>`;
    return;
  }
  const ladder = payload.ladder || [];
  const fmt = payload.format || {};
  const cleared = new Set(G.state.cleared_bosses || []);

  // Crutch ids arrive bare in `sealed` and `remaining`; only `takes` carries the
  // readable name. Build the dictionary out of the ladder's own rungs so the
  // names stay the server's and never drift.
  const NAMES = {};
  for (const rung of ladder) {
    for (const t of rung.takes || []) NAMES[t.id] = t.name;
  }
  const nameOf = (id) => NAMES[id] || id.replace(/_/g, ' ').toLowerCase();

  const rungs = ladder.map((r) => {
    const done = cleared.has(r.boss_id);
    const takes = r.takes || [];
    return `<div class="frame" style="padding:12px;margin-bottom:8px;
        border-color:${done ? 'var(--green)' : r.final ? 'var(--red)' : 'var(--line)'}">
      <div class="row" style="align-items:baseline">
        <span class="pixel" style="flex:0 0 40px;font-size:11px;color:${
          done ? 'var(--green)' : 'var(--gold)'}">${done ? '✔' : r.rung}</span>
        <span class="grow">
          <b style="color:${r.final ? 'var(--red)' : 'var(--gold-hi)'}">${r.boss}</b>
          <span class="muted small"> · ${r.region.replace(/_/g, ' ')}</span>
          ${r.timed ? '<span class="tag orange">ON THE CLOCK</span>' : ''}
          ${r.final ? '<span class="tag red">THE LAST DOOR</span>' : ''}
        </span>
        <span class="small" style="color:var(--violet)">${
          (r.remaining || []).length} left</span>
      </div>
      ${takes.length
        ? takes.map(t => `<div class="small" style="margin-top:6px">
            <span class="tag red">TAKES</span>
            <b style="color:var(--red)">${t.name}</b>
            ${t.herald ? `<br><span class="muted small">“${t.herald}”</span>` : ''}
          </div>`).join('')
        : `<div class="small muted" style="margin-top:6px">Takes nothing. The first
           two exist so you know what a full kit feels like before it starts going.</div>`}
      <div class="small" style="margin-top:6px;color:var(--ink-faint)">
        STILL YOURS AFTERWARDS — ${(r.remaining || []).map(nameOf).join(' · ') || 'nothing'}
      </div>
    </div>`;
  }).join('');

  const run = G.state.interview;
  const inExam = !!(run && run.format === 'FINAL_EXAM');

  $('#exam-body').innerHTML = `
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">${fmt.label || 'THE PRACTICAL TEST'} —
        ${fmt.count || 0} PROBLEMS · ${fmt.minutes || 0} MINUTES</div>
      <ul style="line-height:1.9;color:var(--ink-dim)">
        ${(fmt.rules || []).map(x => `<li>${x}</li>`).join('')}</ul>
      <p class="small muted">The ladder below is not a warning about the exam.
      It is the exam, delivered one boss at a time over the whole game, so that
      by the time the rules go quiet for good you have already played under
      every one of them.</p>
      <div class="actions">
        ${inExam
          ? '<button class="btn danger" id="ex-finish">END THE RUN AND BE SCORED</button>'
          : '<button class="btn danger" id="ex-start">SIT THE PRACTICAL TEST</button>'}
        <button class="btn" id="ex-interview">PRACTISE IN INTERVIEW MODE</button>
      </div>
      ${inExam ? `<p class="small" style="color:var(--orange)">A run is open —
        question ${(run.index || 0) + 1} of ${(run.problem_ids || []).length}.</p>` : ''}
    </div>
    ${rungs}`;

  const start = $('#ex-start');
  if (start) {
    start.onclick = () => confirmThen('SIT THE PRACTICAL TEST',
      `${fmt.count || 6} problems, ${fmt.minutes || 115} minutes, one clock per
      segment. Nothing is withheld that you have not already fought without.
      It is scored the moment it ends.`, 'BEGIN. THE CLOCK STARTS NOW.',
      async () => {
        let r;
        try {
          r = await api.startExam(G.state.player.profile);
        } catch (e) { toast('CANNOT START', e.message, 'red'); return; }
        if (r.error) { toast('CANNOT START', r.message || r.error, 'red'); return; }
        try {
          enterBattle(await api.interviewCurrent());
        } catch (e) { toast('CANNOT START', e.message, 'red'); }
      });
  }
  const finish = $('#ex-finish');
  if (finish) {
    finish.onclick = () => confirmThen('END THE RUN',
      'Everything you have answered so far is scored as it stands. Everything '
      + 'you have not answered is scored as unanswered.', 'END IT AND SCORE ME',
      async () => {
        let r;
        try {
          r = await api.finishExam({});
        } catch (e) { toast('NOT ENDED', e.message, 'red'); return; }
        if (r.error) { toast('NOT ENDED', r.message || r.error, 'red'); return; }
        await refresh();
        showInterviewReport(r);
      });
  }
  $('#ex-interview').onclick = () => go('interview');
}

/* ---------------- the world seed ---------------- */

async function paintSeed() {
  panel('THIS WORLD', `<div id="seed-body"><p class="small muted">Reading the
    card…</p></div>`);
  let card;
  try {
    card = await api.worldCard();
  } catch (e) {
    if ($('#seed-body')) {
      $('#seed-body').innerHTML = `<p class="small" style="color:var(--red)">
        The world card could not be read — ${e.message}</p>`;
    }
    return;
  }
  if (!$('#seed-body')) return;   // the screen changed while this was in flight
  if (card.error) {
    $('#seed-body').innerHTML = `<p class="small" style="color:var(--red)">
      ${card.message || card.error}</p>`;
    return;
  }
  const hour = card.first_hour || {};
  $('#seed-body').innerHTML = `
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">THE WORLD CODE</div>
      <div class="pixel" id="seed-code" style="font-size:20px;color:var(--gold-hi);
        letter-spacing:3px;margin:10px 0">${card.seed}</div>
      <p class="small muted">Anyone who types this code gets the same geography,
      the same dungeons and the same boss affixes. It is the whole world in eight
      characters.</p>
      <div class="actions">
        <button class="btn small" id="seed-copy">COPY THE CODE</button>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">YOUR FIRST HOUR HERE</div>
      <p class="small">${hour.encounters || 0} encounters ·
        hardest difficulty ${hour.hardest_difficulty || '—'} ·
        ${hour.dungeons_reachable || 0} dungeon(s) in reach ·
        first boss at about ${fmtTime(hour.first_boss_seconds || 0)} of play.<br>
        <span style="color:${hour.gentle ? 'var(--green)' : 'var(--orange)'}">
        ${hour.gentle ? 'This seed opens gently.'
          : 'This seed does not open gently.'}</span></p>
    </div>
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">THE CARD</div>
      <pre class="spell-body" style="white-space:pre-wrap">${
        (card.card || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>
    </div>
    <div class="frame" style="padding:14px">
      <div class="section-title">ROLL A NEW WORLD</div>
      <p class="small">A new world re-draws the map, the dungeons and the boss
      affixes. Your character, your skills and everything you have proved stay
      exactly as they are — this moves the ground, not you.</p>
      <div class="row" style="flex-wrap:wrap">
        <input id="seed-in" class="explain" style="min-height:auto;height:44px;
          flex:1;min-width:200px" maxlength="40"
          placeholder="a world code, a number, or any phrase — blank for a surprise">
        <button class="btn danger" id="seed-go">ROLL IT</button>
      </div>
    </div>`;

  $('#seed-copy').onclick = async () => {
    try {
      await navigator.clipboard.writeText(card.seed);
      toast('COPIED', `${card.seed} is on your clipboard.`, 'green');
    } catch (e) {
      // Clipboard access is refused in plenty of ordinary configurations.
      toast('NOT COPIED', `Read it off the screen: ${card.seed}`, 'red');
    }
  };
  $('#seed-go').onclick = () => {
    const typed = $('#seed-in').value.trim();
    confirmThen('ROLL A NEW WORLD',
      `The map, the dungeons and the boss affixes are all re-drawn${
        typed ? ` from “${typed}”` : ''}. Save first if you want this one back.`,
      'ROLL IT', async () => {
        let r;
        try {
          r = await api.newWorld(typed || 0);
        } catch (e) { toast('NOT ROLLED', e.message, 'red'); return; }
        if (r.error === 'sealed') { toast(sealedTitle(r), r.message, 'red'); return; }
        if (r.error) { toast('NOT ROLLED', r.message || r.error, 'red'); return; }
        audio.sfx('levelup');
        await refresh();
        // The canonical code is what came back, not what was typed.
        toast('A NEW WORLD', `${r.seed} — the ground has moved.`, 'gold');
        loadRegion(G.state.player.region);
        paintSeed();
      });
  };
}

/* ---------------- the map and the party ---------------- */

/* Two files draw the world layer and neither knows this shell exists, so this
 * is the whole of the contract. worldui.js is a class that takes a hooks object
 * and mounts into a node we give it; partyui.js paints whole panels instead, so
 * it borrows the chrome once and repaints #panel-body through it. Both are told
 * when they are being taken off the screen, because both keep clocks. */

function destroyChild() {
  if (!G.child) return;
  const child = G.child;
  G.child = null;
  try { child.destroy(); } catch (e) { /* a destroyed panel is still destroyed */ }
}

/* Everything worldui.js needs from the shell, so it never reaches into the
 * document for chrome that is not its own. */
function worldHooks() {
  return {
    audio,
    toast,
    say,
    onBack: () => returnToWorld(),
    /* The panel keeps its own copy of the dashboard; main.js keeps the
     * original, and there is only allowed to be one of those. */
    onRefresh: async () => { await refresh(); return G.state; },
    /* The player walked. The world screen is drawn from the region, so it has
     * to be told too or it keeps painting the place they left. api.travel
     * answers with the region's id; api.region answers with the whole view. */
    onRegion: (region) => {
      const id = typeof region === 'string' ? region : (region && region.id);
      if (id) loadRegion(id);
    },
    /* Rows the map does not own — an encounter, a boss, a shrine, unspent
     * points. doTodo already knows every action kind the server emits. */
    onAction: (action, entry) => doTodo({ ...(entry || {}), action }),
    /* A dungeon room that turned into a fight. */
    onEncounter: (payload) => enterBattle(payload),
  };
}

async function mountMap() {
  panel('THE MAP', `<p class="small muted">Regions, roads, what the world does
    next, and the dungeons under all of it.</p>
    <div id="child-host"></div>`);
  const host = $('#child-host');
  const ui = new WorldUI(worldHooks());
  G.child = ui;
  try {
    // A descent already in progress is where the player actually is. Opening
    // the overworld on top of it would be the map telling them otherwise.
    if (G.state && G.state.dungeon) await ui.mountDescent(host, G.state);
    else await ui.mountOverworld(host, G.state);
  } catch (e) {
    destroyChild();
    if (!host.isConnected) return;
    host.innerHTML = `<div class="frame" style="padding:14px">
      <div class="section-title">THE MAP WILL NOT DRAW</div>
      <p class="small">${e.message}</p>
      <p class="small muted">Everything on it is still reachable from the
      ledger; only the drawing failed.</p></div>`;
  }
}

/* partyui.js repaints #panel-body itself, so the wrapper below is also where it
 * gets re-registered as the mounted child — a screen that navigates to its own
 * sibling has just destroyed the previous mount through panel(). */
const PARTY_CHILD = { destroy: () => partyui.leave() };

function configureParty() {
  partyui.configure({
    panel: (title, html) => { panel(title, html); G.child = PARTY_CHILD; },
    modal,
    closeModal,
    toast,
    state: () => G.state,
    refresh: async () => { await refresh(); return G.state; },
    back: () => returnToWorld(),
    sfx: (name) => audio.sfx(name),
  });
}

/* The tree is the party screen; its own strip carries the companions and the
 * codex. An unchosen class makes paintSkillTree hand over to the selection
 * screen, which is the screen that player needs anyway. */
async function mountParty() {
  try {
    await partyui.paintSkillTree();
  } catch (e) {
    toast('THAT PANEL WILL NOT OPEN', e.message, 'red');
  }
}

/* ---------------- the ledger ---------------- */

/* The index. Fifteen screens do not fit across a topbar, and a topbar that
 * tried would be a wall of eight-point capitals nobody reads twice. */
const LEDGER = [
  { id: 'status', label: 'STATUS',
    blurb: 'Skills as evidence, readiness gates, weapons, achievements.' },
  { id: 'character', label: 'GEAR & BUILD',
    blurb: 'What you are wearing, what it does, and the points you have not spent.' },
  { id: 'grimoire', label: 'PATTERN GRIMOIRE',
    blurb: 'Cards earned by demonstrated use, and the ones still unearned.' },
  { id: 'saves', label: 'SAVES',
    blurb: 'Sixteen slots, the autosaves, and one undo.' },
  { id: 'exam', label: 'THE PRACTICAL TEST',
    blurb: 'The fourteen-rung ladder, and the exam at the top of it.' },
  { id: 'interview', label: 'INTERVIEW MODE',
    blurb: 'A measured run. Nothing is taught while it is running.' },
  { id: 'seed', label: 'THIS WORLD',
    blurb: 'The shareable world code, and the ground under it.' },
  { id: 'settings', label: 'MENU',
    blurb: 'Audio, accessibility, the sandbox, and your history.' },
];

/* The eleven modules, each in one line, each pointing at the screen that owns
 * it. The map and the party are written elsewhere and may not have landed; this
 * strip reads their dashboard keys directly, so nothing behind them is ever
 * invisible — only less interactive than it will be. */
function worldLayerHtml() {
  const s = G.state;
  const w = s.world || {};
  const events = (w.events || {}).upcoming || [];
  const dungeon = s.dungeon;
  const cls = s.class;
  const pets = s.pets || [];
  const found = pets.filter(p => p.found);
  const active = pets.filter(p => p.active);
  const relics = (s.legendaries || {}).owned || [];
  const hand = (s.legendaries || {}).hand || {};
  const exam = s.exam || {};
  const climbed = (s.cleared_bosses || []).length;

  const line = (screen, label, text) =>
    `<div class="list-item" data-ledger="${screen}" style="padding:8px 10px">
      <span class="t">${label}</span><span class="d">${text}</span></div>`;

  return [
    line('map', 'THE MAP',
      `${(w.reachable || []).length} region(s) in reach from ${
        (w.nodes || []).find(n => n.here) ? (w.nodes.find(n => n.here).name) : 'here'}
       · ${(w.open_routes || []).length} road(s) open · sky ${w.sky || '—'}
       · ${w.restored || 0} place(s) restored`),
    line('map', 'WHAT THE WORLD DOES NEXT',
      events.length
        ? `${events[0].title} — ${events[0].requirement} (${events[0].percent}%)`
        : 'Nothing is queued. The map is waiting on you, not the other way round.'),
    line('map', 'THE DESCENT',
      // `rooms` and `visited` are counts, and `rule` is the rule's key; the
      // sentence a player can read is `note`.
      dungeon
        ? `${dungeon.name} — ${dungeon.visited}/${dungeon.rooms} rooms seen,
           depth ${dungeon.depth || 0}. ${dungeon.note || ''}`
        : `No run open. ${(s.dungeons || []).length} dungeon(s) in this region.`),
    line('party', 'YOUR CLASS',
      cls
        ? `${(cls.class || {}).name || '—'} — ${cls.spent} of ${
             cls.spent + cls.points} point(s) spent, ${cls.respecs} respec(s) taken.${
             cls.dual_open && !cls.dual ? ' A second discipline is open.' : ''}`
        : `Unchosen. ${(s.class_selection || []).length} to pick from, and the
           tree does not open until you do.`),
    line('party', 'COMPANIONS',
      `${found.length}/${pets.length} found${active.length
        ? ` · ${active.map(p => p.name).join(' and ')} walking with you` : ''}.
       ${(s.pet_hints || []).length
         ? `${s.pet_hints[0].name} is out there: ${s.pet_hints[0].how}` : ''}`),
    line('party', 'RELICS',
      `${relics.length}/22 held.${hand.uses
        ? ` The Obliging Hand has been used ${hand.uses} time(s), on ${
            hand.skills_touched} skill(s).`
        : ' The Obliging Hand has not been used.'}`),
    line('exam', 'THE LADDER',
      `${climbed}/${(exam.ladder || []).length} rung(s) climbed ·
       ${(exam.format || {}).label || 'The Practical Test'} waits at the top`),
    line('seed', 'THIS WORLD', `${s.seed} — the code anyone can type to stand here.`),
  ].join('');
}

function paintLedger() {
  const s = G.state;
  const board = s.quests || {};
  const counts = board.counts || {};
  const facts = {
    status: `readiness ${s.readiness.overall}% · ${s.readiness.gates_passed}/${s.readiness.gates_total} gates`,
    character: `${(s.loadout.inventory || []).length} items · ${s.unspent_points} unspent`,
    grimoire: `${(s.grimoire || []).length} card(s)`,
    saves: 'sixteen slots',
    exam: `${(s.cleared_bosses || []).length}/14 rungs climbed`,
    interview: `profile ${s.player.profile}`,
    seed: s.seed || '',
    settings: `${s.playtime || ''} played`,
  };
  panel('THE LEDGER', `
    <p class="small muted">Everything this game keeps about you, and every door
    that is not one of the five on the bar.</p>
    <div class="grid2">
      ${LEDGER.map(item => `<div class="list-item" data-ledger="${item.id}">
        <span class="t">${item.label}</span>
        <span class="d">${item.blurb}<br>
          <span class="muted small">${facts[item.id] || ''}</span></span>
      </div>`).join('')}
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">THE WORLD LAYER</div>
      ${worldLayerHtml()}
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">WHAT NEXT</div>
      <div id="ledger-todo"></div>
    </div>`);
  document.querySelectorAll('[data-ledger]').forEach(n => {
    n.onclick = () => go(n.dataset.ledger);
  });
  const todo = $('#ledger-todo');
  for (const item of (s.todo || [])) {
    const row = el('div', 'list-item',
      `<span class="t">${TODO_ICON[item.kind] || '·'} ${item.title}</span>
       <span class="d">${item.why}<br>
         <span class="muted small">${item.region_name || ''}</span></span>`);
    row.onclick = () => doTodo(item);
    todo.appendChild(row);
  }
}

/* ---------------- nav + boot ---------------- */

/* Every screen in the game, by name. The topbar carries five of them and the
 * ledger carries the rest; both arrive here, so there is exactly one place that
 * knows how to open anything. */
const SCREENS = {
  world: () => returnToWorld(),
  quests: paintQuests,
  map: mountMap,
  party: mountParty,
  character: paintCharacter,
  ledger: paintLedger,
  status: paintStatus,
  grimoire: paintGrimoire,
  interview: paintInterview,
  settings: paintSettings,
  saves: paintSaves,
  exam: paintExam,
  seed: paintSeed,
};

function go(id) {
  audio.resume();
  audio.sfx('select');
  const open = SCREENS[id];
  if (!open) { toast('NO SUCH SCREEN', `There is no screen called ${id}.`, 'red'); return; }
  if (id === 'world') { open(); return; }
  // Every panel reads G.state, so every panel gets a fresh one first. A failed
  // read has already said so out loud and left the last state in place.
  refresh().then(() => open())
    .catch((e) => toast('THAT PANEL WILL NOT OPEN', e.message, 'red'));
}

/* The bar. Seven flat buttons was already crowded and the world layer would
 * have made it fifteen; five doors and an index is the same reach with a third
 * of the noise, and the index is a screen that can say what each door is for. */
const NAV = [
  { id: 'world', label: 'WORLD' },
  { id: 'quests', label: 'QUESTS' },
  { id: 'map', label: 'MAP' },
  { id: 'party', label: 'PARTY' },
  { id: 'character', label: 'GEAR', pip: true },
  { id: 'ledger', label: '☰ LEDGER' },
];

function buildNav() {
  const bar = document.querySelector('#topbar .nav');
  if (!bar) return;
  bar.innerHTML = '';
  for (const entry of NAV) {
    const b = el('button', 'btn small', entry.label);
    b.dataset.nav = entry.id;
    if (entry.pip) {
      // The unspent-point pip is painted by paintVitals, which looks it up by id.
      const pip = el('span', '', ' ●');
      pip.id = 'points-pip';
      pip.style.cssText = 'display:none;color:var(--gold-hi)';
      b.appendChild(pip);
    }
    b.onclick = () => go(entry.id);
    bar.appendChild(b);
  }
}

buildNav();

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'n' && G.screen === 'world') startNext();
  if (e.key === 'f' && G.screen === 'world') searchHere();
  if (e.key === 'Escape' && !G.modalLocked) {
    closeModal();
    $('#dialogue').classList.remove('show');
  }
  if (e.key === ' ' && $('#dialogue').classList.contains('show')) {
    e.preventDefault(); advanceDialogue();
  }
});

window.addEventListener('resize', () => {
  if (G.title) G.title.resize();
  if (G.overworld) G.overworld.resize();
  if (G.viz && G.vizCanvas && G.vizCanvas.isConnected) G.viz.render();
});

document.addEventListener('click', () => audio.resume(), { once: true });

async function intro() {
  const check = await api.sandboxCheck();
  if (!check.network_blocked) {
    toast('SANDBOX NOTICE',
      'Network isolation could not be verified on this machine. Code still runs '
      + 'under CPU, memory and wall-clock limits.', 'red');
  }
  modal(`<h2 style="color:var(--gold-hi)">PYTHON CODING GAUNTLET LEGEND</h2>
    <p class="pixel" style="color:var(--violet);font-size:11px">THE ALGORITHM REALMS</p>
    <p style="line-height:1.9">The ancient <b style="color:var(--gold)">Source</b> once
    governed the realm. It was shattered by <b style="color:var(--red)">the Null
    King</b>, and its fragments became the fundamental patterns of computation.</p>
    <p style="line-height:1.9">You are <b style="color:var(--gold)">the Security
    Architect</b>. Your judgement is already sharp. Your defences already hold. But
    the Source cannot be restored without mastering the old language:
    <b style="color:var(--green)">Python</b>.</p>
    <p style="line-height:1.9">Sixteen regions. Fourteen bosses. Every failure opens a
    path, never a wall. Break your armour and you repair it by debugging real code.</p>
    <p class="small muted">Adventure Mode teaches. Interview Mode measures.
    They are never confused.</p>
    <div class="actions">
      <button class="btn primary" id="intro-go">ENTER PYTHON VILLAGE</button>
    </div>`, { wide: true });
  $('#intro-go').onclick = () => {
    audio.resume();
    audio.sfx('unlock');
    if (!G.state.build) { chooseBuild(); return; }
    closeModal();
    const mentor = G.world.mentors.byte;
    say(mentor.name, [
      mentor.greeting,
      'You read code well. You reason about systems well. What you do not yet do is '
      + 'produce Python quickly from a blank screen.',
      'So that is what we train. Walk east. Step on anything that moves.',
      'Press SPACE to talk, N for whatever the engine thinks you most need next.',
    ], mentor.sprite);
  };
}

/* The Trial of the Architect: five short encounters that decide where on the
 * ladder to start. It can place you forward as well as back, and skipping is
 * always safe because a skip starts you at the beginning. */
async function runDiagnostic() {
  let spec;
  try {
    spec = await api.diagnostic();
  } catch (e) {
    toast('THE TRIAL WILL NOT OPEN', e.message, 'red');
    return;
  }
  const answers = {};
  let index = 0;
  // A backdrop click at trial 3 used to discard the whole run with a half-filled
  // answer sheet and no way back in. The chain owns the modal until it finishes.
  G.modalLocked = true;

  const intro = modal(`<h2>THE TRIAL OF THE ARCHITECT</h2>
    <p>Five short questions. They are not a test you can fail — they decide where
    you start, and they can just as easily start you further in.</p>
    <p class="small muted">About four minutes. Skipping is safe: it starts you at
    the beginning, which is never the wrong answer.</p>
    <div class="actions">
      <button class="btn primary" id="dg-go">BEGIN</button>
      <button class="btn" id="dg-skip">SKIP — START AT THE BEGINNING</button>
    </div>`);
  intro.querySelector('#dg-go').onclick = () => step();
  intro.querySelector('#dg-skip').onclick = () => abandon();

  /* The exit. Skipping is a real placement, not a cancel, so leaving mid-trial
   * still ends with the player somewhere rather than nowhere. */
  async function abandon() {
    audio.sfx('select');
    // An unanswered trial evaluates as not-yet-demonstrated, which can only
    // place you earlier — so stopping half way is safe, and an empty answer
    // sheet is a plain skip rather than a placement of zero.
    const answered = Object.keys(answers).length > 0;
    try {
      finish(await api.diagnosticFinish(answers, !answered));
    } catch (e) {
      G.modalLocked = false;
      closeModal();
      toast('THE TRIAL BREAKS OFF', e.message, 'red');
    }
  }

  function step() {
    if (index >= spec.trials.length) {
      api.diagnosticFinish(answers, false).then(finish).catch((e) => {
        G.modalLocked = false;
        closeModal();
        toast('THE TRIAL BREAKS OFF', e.message, 'red');
      });
      return;
    }
    const trial = spec.trials[index];
    const body = trial.kind === 'mcq'
      ? `${trial.code ? `<pre class="spell-body">${trial.code
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>` : ''}
         <div id="dg-choices">${trial.choices.map((c, i) =>
           `<div class="list-item" data-choice="${i}"><span class="d">${c}</span></div>`
         ).join('')}</div>`
      : `<div id="dg-editor" style="height:240px;border:2px solid var(--line)"></div>
         <div class="actions"><button class="btn primary" id="dg-run">SUBMIT</button></div>`;

    const m2 = modal(`<h2>TRIAL ${index + 1} OF ${spec.trials.length}</h2>
      ${trial.narration ? `<p class="small muted">${trial.narration}</p>` : ''}
      <p style="font-size:15px;color:var(--ink)">${trial.prompt}</p>
      ${body}
      <div class="actions">
        <button class="btn" id="dg-quit">STOP HERE — PLACE ME FROM WHAT I ANSWERED</button>
      </div>`);
    m2.querySelector('#dg-quit').onclick = () => abandon();

    if (trial.kind === 'mcq') {
      m2.querySelectorAll('[data-choice]').forEach(node => {
        node.onclick = async () => {
          if (node.classList.contains('chosen')) return;  // no double commits
          node.classList.add('chosen');
          try {
            const r = await api.diagnosticCheck(trial.id, Number(node.dataset.choice));
            answers[trial.id] = { correct: r.correct };
            audio.sfx(r.correct ? 'select' : 'fail');
          } catch (e) {
            node.classList.remove('chosen');
            toast('THAT DID NOT REGISTER', e.message, 'red');
            return;
          }
          index++;
          step();
        };
      });
    } else {
      const ed = new Editor(m2.querySelector('#dg-editor'), { assist: false });
      ed.reset(trial.starter || '');
      m2.querySelector('#dg-run').onclick = async () => {
        try {
          const r = await api.diagnosticCheck(trial.id, ed.value);
          answers[trial.id] = { correct: r.correct };
          audio.sfx(r.correct ? 'crit' : 'fail');
        } catch (e) { toast('THAT DID NOT REGISTER', e.message, 'red'); return; }
        index++;
        step();
      };
    }
  }

  function finish(placement) {
    audio.sfx('levelup');
    const detail = (placement.detail || []).map(d =>
      `<div class="gate ${d.correct ? 'pass' : 'fail'}">
        <span class="mark">${d.correct ? '✔' : '·'}</span>
        <span>${d.probes} <span class="muted small">— ${d.note}</span></span></div>`).join('');
    const chapter = placement.chapter || {};
    const m3 = modal(`<h2>YOUR PLACEMENT</h2>
      ${detail}
      <h3>${chapter.title || placement.chapter_title}</h3>
      <p>${placement.verdict}</p>
      <p class="small muted">${chapter.goal || ''}</p>
      <div class="actions">
        <button class="btn primary" id="dg-done">ENTER PYTHON VILLAGE</button>
      </div>`, { wide: true });
    m3.querySelector('#dg-done').onclick = async () => {
      G.modalLocked = false;
      closeModal();
      await refresh();
      if (!G.state.build) { chooseBuild(); return; }
      loadRegion(G.state.player.region);
    };
  }
}

function chooseBuild() {
  const lo = G.state.loadout;
  const cards = Object.entries(lo.builds).map(([id, spec]) => `
    <div class="list-item" data-build="${id}">
      <span class="t">${spec.name.toUpperCase()}</span>
      <span class="d">${spec.blurb}<br>
      <span class="muted small">Starts with ${Object.entries(spec.starting)
        .filter(([, v]) => v >= 3).map(([k, v]) => `${k} ${v}`).join(', ')}
        · favours the ${lo.sets[spec.set].name}</span></span>
    </div>`).join('');
  const m = modal(`<h2>CHOOSE YOUR PATH</h2>
    <p>Three ways to fight. None of them writes Python for you — they change what a
    fight <i>costs</i> you, and what it pays. You can pay the Armorer to change your
    mind later.</p>
    ${cards}
    <p class="small muted">Every one of these is disabled inside Interview Mode.</p>`);
  m.querySelectorAll('[data-build]').forEach(node => {
    node.onclick = async () => {
      let r;
      try {
        r = await api.chooseBuild(node.dataset.build);
      } catch (e) { toast('CANNOT CHOOSE', e.message, 'red'); return; }
      if (r.error) { toast('CANNOT CHOOSE', r.error, 'red'); return; }
      audio.sfx('levelup');
      await refresh();
      closeModal();
      toast(r.build.name.toUpperCase(),
        'Starting gear equipped. Check GEAR to spend your first points.', 'gold');
      loadRegion(G.state.player.region);
      const mentor = G.world.mentors.byte;
      say(mentor.name, [
        mentor.greeting,
        'You read code well. You reason about systems well. What you do not yet do is '
        + 'produce Python quickly from a blank screen.',
        'So that is what we train. Walk east. Step on anything that moves.',
        'In a fight, open TACTICS before you write. Enemies guard specific boundaries — '
        + 'empty inputs, duplicates, negatives. PROBE one and you expose it.',
        'Expose a weakness, and when your solution passes that hidden trial it strikes '
        + 'critically: more XP, better loot. That is how you fight here — by predicting '
        + 'how code breaks.',
        'Press SPACE to talk, N for whatever I think you most need next, F to search '
        + 'for what the map does not show.',
      ], mentor.sprite);
    };
  });
}

async function boot() {
  try {
    await api.ping();
  } catch (e) {
    document.body.classList.remove('titling');
    document.body.innerHTML = `<div style="padding:40px;font-family:monospace;color:#e8c37d">
      Could not reach the local game server.<br><br>${e.message}</div>`;
    return;
  }
  G.world = await api.world();
  await refresh();

  // partyui.js paints through the shell's own chrome — one modal node, one
  // toast rail, one panel body. Handed over once, before any door can open.
  configureParty();

  // Optional: prefer recorded audio where it exists. Absent samples are the
  // normal case and the rig synthesises everything instead.
  audio.loadSamples('/audio/').then((report) => {
    if (report && report.loaded) {
      toast('SAMPLES LOADED', `${report.loaded} licence-clear sample(s) in use.`, 'green');
    }
    if (report && report.refused && report.refused.length) {
      toast('SAMPLES REFUSED', report.refused[0], 'red');
    }
  }).catch(() => { /* synthesis covers it */ });

  G.overworld = new Overworld($('#world-canvas'));
  G.overworld.onEnter = onNodeEnter;
  G.overworld.onMove = (x, y) => {
    clearTimeout(G._moveSave);
    G._moveSave = setTimeout(() => api.move(currentRegion().id, x, y), 900);
  };
  loadRegion(G.state.player.region);
  show('world');
  G.overworld.start();

  // deep links: #world drops straight into the overworld, #problem/<id> into
  // an encounter. Both skip the title screen.
  if ((location.hash || '') === '#world') {
    document.body.classList.remove('titling');
    if (!G.state.build) await api.chooseBuild('ANALYST').catch(() => {});
    await refresh();
    loadRegion(G.state.player.region);
    show('world');
    G.overworld.start();
    return;
  }
  const deep = /^#problem\/(.+)$/.exec(location.hash || '');
  if (deep) {
    document.body.classList.remove('titling');
    if (!G.state.build) await api.chooseBuild('ANALYST').catch(() => {});
    await refresh();
    startProblem(decodeURIComponent(deep[1]));
    return;
  }

  // #panel/<nav> opens any top-level screen directly. Useful for linking
  // someone to the thing you are talking about, and it is the only way to
  // reach a screen from a capture tool, which cannot click a nav button.
  const panel = /^#panel\/([a-z-]+)$/.exec(location.hash || '');
  if (panel) {
    const target = document.querySelector(`[data-nav="${panel[1]}"]`);
    if (target) {
      document.body.classList.remove('titling');
      if (!G.state.build) await api.chooseBuild('ANALYST').catch(() => {});
      await refresh();
      target.click();
      return;
    }
  }

  showTitle();
}

/* ---------------- title screen ---------------- */

function showTitle() {
  document.body.classList.add('titling');
  const started = !!(G.state.build && G.state.stats.encounters);
  G.title = new TitleScreen($('#title-canvas'), {
    hasSave: started,
    reducedMotion: !!G.state.settings.reduced_motion,
    onSelect: (id) => {
      audio.resume();
      if (id === 'move') { audio.sfx('select'); return; }
      audio.sfx('unlock');
      if (id === 'settings') { leaveTitle(); paintSettings(); return; }
      if (id === 'about') { showAbout(); return; }
      if (id === 'continue') {
        leaveTitle();
        // CONTINUE is how a returning player gets back in, and the trial only
        // ever fired from NEW GAME. An unfinished placement is offered here too.
        if (!G.state.diagnostic_done) setTimeout(runDiagnostic, 560);
        return;
      }
      leaveTitle();
      beginNewRun();
    },
  });
  G.title.resize();
  G.title.start();
  audio.play('town');
}

function leaveTitle() {
  const layer = $('#title-layer');
  layer.classList.add('fading');
  setTimeout(() => {
    document.body.classList.remove('titling');
    layer.classList.remove('fading');
    if (G.title) { G.title.destroy(); G.title = null; }
    if (G.overworld) { G.overworld.resize(); G.overworld.start(); }
    const region = currentRegion();
    audio.play(region.music || 'overworld');
  }, 520);
}

function showAbout() {
  modal(`<h2>PYTHON CODING GAUNTLET LEGEND</h2>
    <p class="pixel" style="color:var(--violet);font-size:11px">THE ALGORITHM REALMS</p>
    <p>A 16-bit RPG whose combat system is a Python coding-interview trainer.
    Adventure Mode teaches. Interview Mode measures. They are never confused.</p>
    <p class="small muted">Everything here — art, music, text, problems — is original
    to this project. No third-party game assets are used. Problems drawn from publicly
    reported interview patterns are labelled as historical patterns and are never
    presented as guaranteed questions.</p>
    <p class="small muted">Your code runs locally under a sandbox that denies network
    access and enforces CPU, memory and wall-clock limits. Nothing leaves this machine.</p>
    <div class="actions"><button class="btn primary" id="about-back">BACK</button></div>`);
  $('#about-back').onclick = closeModal;
}

async function beginNewRun() {
  if (!G.state.diagnostic_done) { runDiagnostic(); return; }
  if (!G.state.build) { chooseBuild(); return; }
  const due = G.state.retests_due.length;
  if (due) {
    toast('RETESTS DUE', `${due} pattern${due > 1 ? 's' : ''} waiting to be proved `
      + 'again — in disguise.', 'violet');
  }
}

boot();
