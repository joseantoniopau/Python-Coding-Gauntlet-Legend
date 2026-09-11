/* Python Coding Gauntlet Legend — client orchestration. */
import { api } from './api.js';
import { audio } from './audio.js';
import * as pixel from './pixel.js';
import * as sprites from './sprites.js';
import * as lootart from './lootart.js';
import { createBattleFX, DAMAGE_KIND, trialsFromFeedback } from './fx.js';
import * as puzzleui from './puzzleui.js';
import { TitleScreen } from './title.js';
import { Editor } from './editor.js';
import { Overworld } from './overworld.js';
import { Visualiser, hasViz } from './viz.js';

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
  tab: 'trials',
  timer: null,
  startedAt: 0,
  hints: [],
  pendingNode: null,
  interview: null,
  interviewTimer: null,
  dialogueQueue: [],
  lastResult: null,
};

/* ---------------- chrome helpers ---------------- */

function toast(title, body, kind = '') {
  const t = el('div', `toast ${kind}`, `<span class="tt">${title}</span>${body}`);
  $('#toasts').appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; }, 4200);
  setTimeout(() => t.remove(), 4800);
}

function modal(html, { wide = false } = {}) {
  const m = $('#modal');
  m.innerHTML = html;
  m.style.width = wide ? 'min(1040px,96vw)' : 'min(900px,94vw)';
  $('#modal-bg').classList.add('show');
  return m;
}

function closeModal() { $('#modal-bg').classList.remove('show'); }

$('#modal-bg').addEventListener('click', (e) => {
  if (e.target.id === 'modal-bg') closeModal();
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
    if (G.storyQueue && G.storyQueue.length) setTimeout(playStoryQueue, 120);
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
  G.state = await api.state();
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

  side.appendChild(el('div', 'section-title', 'TODAY'));
  const quest = el('div');
  if (due) {
    quest.appendChild(el('div', 'list-item',
      `<span class="t">${due} RETEST${due > 1 ? 'S' : ''} DUE</span>
       <span class="d">${s.retests_due.slice(0, 3).map(r =>
         r.family.replace(/_/g, ' ')).join(', ')} — in disguise.</span>`));
  }
  for (const q of s.daily.quests.slice(0, 4)) {
    quest.appendChild(el('div', 'list-item',
      `<span class="t">${q.kind} · ${q.count}×</span>
       <span class="d"><b>${q.title}</b><br>${q.detail}</span>`));
  }
  side.appendChild(quest);

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
  actions.append(btnNext, btnBoss, btnShrine, btnForge);
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

  side.appendChild(el('div', 'section-title', 'TRAVEL'));
  const travel = el('div');
  for (const r of s.regions) {
    const item = el('div', `list-item ${r.unlocked ? '' : 'locked'}`,
      `<span class="t">${r.numeral || '★'} ${r.name.toUpperCase()}</span>
       <span class="d">${r.unlocked ? r.blurb
        : 'Sealed — build mastery in the regions before it.'}</span>`);
    if (r.unlocked) item.onclick = () => { loadRegion(r.id); api.move(r.id, 4, 15); };
    travel.appendChild(item);
  }
  side.appendChild(travel);
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

function openChest(marker) {
  const key = 'gauntlet-chest-' + marker.id;
  if (localStorage.getItem(key)) {
    say('CHEST', ['Already emptied.'], 'scholar');
    return;
  }
  localStorage.setItem(key, '1');
  audio.sfx('unlock');
  const codex = [
    'CODEX: a dict lookup is O(1) on average and O(n) in the pathological case.',
    'CODEX: `all([])` is True. `any([])` is False. Interviewers ask this.',
    'CODEX: Python sorts are stable — equal elements keep their relative order.',
    'CODEX: `deque` gives O(1) at both ends. A list gives O(n) at the front.',
    'CODEX: BFS finds the shortest path in an UNWEIGHTED graph only.',
  ];
  say('TREASURE', [codex[Math.floor(Math.random() * codex.length)]], 'oracle');
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

function showTravel() {
  const rows = G.state.regions.filter(r => r.unlocked)
    .map(r => `<div class="list-item" data-region="${r.id}">
        <span class="t">${r.numeral || '★'} ${r.name.toUpperCase()}</span>
        <span class="d">${r.blurb}</span></div>`).join('');
  const m = modal(`<h2>TRAVEL</h2>${rows}
    <div class="actions"><button class="btn" id="m-close">CLOSE</button></div>`);
  m.querySelectorAll('[data-region]').forEach(n => {
    n.onclick = () => { closeModal(); loadRegion(n.dataset.region); api.move(n.dataset.region, 4, 15); };
  });
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
  G.encounter = payload;
  G.problem = payload.problem;
  G.hints = [];
  G.probeCharges = payload.probe_charges;
  G.startedAt = Date.now();
  G.interview = payload.interview || null;

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
  setTab(interview ? 'approach' : 'trials');
  show('battle');
  audio.play(enemy.boss ? 'boss' : 'battle');

  if (enemy.boss && enemy.taunt) {
    audio.sfx('boss');
    ensureStage().bossIntro({ name: enemy.name, taunt: enemy.taunt,
                              colour: enemy.colour });
    say(enemy.name.toUpperCase(), [enemy.taunt], 'interviewer');
  } else if (payload.encounter.is_retest) {
    toast('MEMORY AMBUSH',
      'A pattern you learned earlier has returned wearing a different face.', 'violet');
  }
  if (payload.interview) paintInterviewTimer();
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
  $('#btn-submit').textContent = 'ANSWER';
  const body = $('#battle-side-body');
  setTab('trials');
  body.innerHTML = '';
  if (p.mcq.code) {
    body.appendChild(el('pre', 'spell-body', p.mcq.code));
  }
  p.mcq.choices.forEach((choice, i) => {
    const item = el('div', 'list-item', `<span class="d">${markdownish(choice)}</span>`);
    item.onclick = async () => {
      const result = await api.mcq(i);
      showResult(result);
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

/* --- side tabs --- */
function setTab(tab) {
  G.tab = tab;
  for (const b of document.querySelectorAll('#battle-side-tabs button')) {
    b.classList.toggle('active', b.dataset.tab === tab);
  }
  const body = $('#battle-side-body');
  body.innerHTML = '';
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
    const r = await api.probe(args, expected);
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
        const r = await api.consumable(c.id);
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
  (G.problem.hint_tree || []).forEach((rung, i) => {
    const used = G.hints.includes(rung.level);
    const node = el('div', `spell ${used ? 'used' : ''}`,
      `<span class="sname">${rung.title.toUpperCase()}</span>
       <span class="scost">${used ? 'CAST' : rung.mana + ' focus'}</span>`);
    node.onclick = async () => {
      if (used) return;
      try {
        const r = await api.hint(rung.level);
        if (r.error) { toast('NOT ENOUGH FOCUS', r.message || r.error, 'red'); return; }
        G.hints.push(rung.level);
        audio.sfx('spell');
        if (G.fx) G.fx.castSpell(rung.spell);
        await refresh();
        setTab('spells');
        const target = $('#battle-side-body');
        const out = el('div', 'spell-body', markdownish(r.body));
        target.insertBefore(out, target.children[i + 2] || null);
        if (rung.spell === 'PHOENIX') {
          toast('PHOENIX', 'A Learning Clear still advances the story — and schedules '
            + 'a mandatory rematch.', 'violet');
        }
      } catch (e) { toast('SPELL FAILED', e.message, 'red'); }
    };
    body.appendChild(node);
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

  if (G.encounter.mode !== 'interview') {
    const btn = el('button', 'btn small', 'SCORE MY EXPLANATION');
    btn.onclick = async () => {
      const r = await api.explain(ta.value);
      if (r.error) return;
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

  if (G.encounter.mode !== 'interview') {
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
  setTimeout(() => v.render(), 50);
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
        showResult(await api.puzzle(answer));
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
    showResult(result);
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
      : `<h3>${result.boss.name} STEPS BACK</h3><p>${result.boss.message}</p>`;
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
  const bind = (id, fn) => { const b = m.querySelector('#' + id); if (b) b.onclick = fn; };
  bind('r-next', () => {
    closeModal();
    if (playStoryQueue()) { G.afterStory = () => startNext(); return; }
    startNext();
  });
  bind('r-retry', () => { closeModal(); G.startedAt = Date.now(); startTimer(); G.editor.focus(); });
  bind('r-world', () => { closeModal(); returnToWorld(); playStoryQueue(); });
  bind('r-camp', () => {
    closeModal();
    const camp = result.training_camp;
    loadRegion(camp.region);
    returnToWorld();
    const mentor = G.world.mentors[camp.mentor] || G.world.mentors.byte;
    say(mentor.name, [camp.why, 'We fix the foundation first. Then we go back.'],
        mentor.sprite);
  });
  bind('r-next-iv', async () => { closeModal(); enterBattle(await api.interviewCurrent()); });
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
  const r = await api.search(region.id, x, y);
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
  if (G.fx) G.fx.stop();
  document.body.classList.remove('interview-mode');
  G.encounter = null;
  G.interview = null;
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

/* ---------------- shrine ---------------- */

async function doShrine() {
  const q = await api.shrine();
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
  const clock = setInterval(() => {
    left--;
    m.querySelector('#shrine-clock').textContent = left + 's';
    if (left <= 0) { clearInterval(clock); submitShrine(); }
  }, 1000);

  async function submitShrine() {
    clearInterval(clock);
    const r = await api.shrineAnswer(input.value);
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
  m.querySelector('#shrine-skip').onclick = () => { clearInterval(clock); closeModal(); };
  input.onkeydown = (e) => { if (e.key === 'Enter') submitShrine(); };
}

/* ---------------- bosses ---------------- */

function showBossList(regionId) {
  const bosses = G.state.bosses.filter(b => !regionId || b.region === regionId);
  const list = (bosses.length ? bosses : G.state.bosses).map(b => {
    const best = b.records.filter(r => r.defeated)
      .reduce((a, r) => (a === null || r.seconds < a.seconds ? r : a), null);
    return `<div class="list-item" data-boss="${b.id}">
      <span class="t">${b.cleared ? '☑ ' : ''}${b.name.toUpperCase()}</span>
      <span class="d">${b.taunt}<br>
      <span class="muted small">${b.region.replace(/_/g, ' ')} ·
      ${b.records.length} attempt(s)${best ? ` · best ${fmtTime(best.seconds)} rank ${best.rank}` : ''}</span>
      </span></div>`;
  }).join('');
  const m = modal(`<h2>BOSSES</h2>
    <p class="small">A boss is never a wall. Fail one and it enters its teaching phase —
    a mentor arrives, the complexity is reduced, and you climb back up.</p>
    ${list}<div class="actions"><button class="btn" id="m-close">CLOSE</button></div>`);
  m.querySelectorAll('[data-boss]').forEach(n => {
    n.onclick = async () => {
      closeModal();
      const payload = await api.startBoss(n.dataset.boss);
      if (payload.error) { toast('BOSS UNAVAILABLE', payload.error, 'red'); return; }
      enterBattle(payload);
    };
  });
  m.querySelector('#m-close').onclick = closeModal;
}

/* ---------------- panels ---------------- */

function panel(title, html) {
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

function paintQuests() {
  const s = G.state;
  const ladder = (s.ladder || []).map(r => `
    <div class="rung ${r.state}">
      <span class="rn">${r.number}</span>
      <span class="grow"><b>${r.title}</b> — ${r.goal}
        ${r.state === 'current'
          ? `<br><span class="muted small">${r.progress.clears}/${r.progress.clears_target} cleared · mastery ${r.progress.mastery}/${r.progress.mastery_target}</span>`
          : ''}</span>
      <span>${r.state === 'done' ? '✔' : r.state === 'current' ? `${r.progress.percent}%` : ''}</span>
    </div>`).join('');

  const q = s.quest_log || {};
  const main = q.main || {};
  const cur = main.current || {};
  const chains = (q.chains || []).filter(c => !c.complete);
  const rival = q.rival || {};

  panel('QUEST LOG', `
    <div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">THE CURRICULUM</div>
      ${ladder || '<p class="small muted">No ladder yet.</p>'}
    </div>
    ${cur.title ? `<div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">MAIN QUEST — ${main.act || ''}
        (${main.completed || 0}/${main.total || 0})</div>
      <div class="list-item"><span class="t">${cur.title}</span>
        <span class="d">${cur.objective || ''}
        ${cur.requirement ? `<br><span class="muted small">${cur.requirement}</span>` : ''}
        ${cur.region_name ? `<br><span class="muted small">in ${cur.region_name}</span>` : ''}
        </span></div>
    </div>` : ''}
    ${chains.length ? `<div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">SIDE CHAINS</div>
      ${chains.map(c => `<div class="list-item">
        <span class="t">${c.title} — step ${c.step}/${c.steps} · ${c.mentor_name}</span>
        <span class="d">${c.objective || c.premise}</span>
      </div>`).join('')}
    </div>` : ''}
    ${rival.name ? `<div class="frame" style="padding:14px;margin-bottom:12px">
      <div class="section-title">${rival.name} — ${rival.meetings_held || 0} meeting(s)</div>
      <div class="skill-row">
        <span class="sn">YOU · ${rival.skill_label || ''}</span>
        <span class="bar"><i style="width:${rival.player_mastery || 0}%"></i></span>
        <span class="sv">${Math.round(rival.player_mastery || 0)}</span></div>
      <div class="skill-row">
        <span class="sn">${rival.name}</span>
        <span class="bar"><i style="width:${rival.rival_mastery || 0}%;background:var(--red)"></i></span>
        <span class="sv">${Math.round(rival.rival_mastery || 0)}</span></div>
      <p class="small" style="color:${rival.ahead ? 'var(--orange)' : 'var(--green)'}">
        ${rival.note || ''}</p>
    </div>` : ''}
    <div class="frame" style="padding:14px">
      <div class="section-title">TODAY — ${s.daily.date}</div>
      ${s.daily.quests.map(q => `<div class="list-item">
        <span class="t">${q.kind} · ×${q.count} · +${q.reward_xp} XP</span>
        <span class="d"><b>${q.title}</b><br>${q.detail}</span></div>`).join('')}
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">RETESTS DUE (${s.retests_due.length})</div>
      ${s.retests_due.length ? s.retests_due.map(r => `<div class="list-item" data-family="${r.family}">
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
  $('#q-next').onclick = () => startNext();
}

function paintGrimoire() {
  const patterns = G.state.grimoire;
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
  const known = Object.keys(cards).filter(k => patterns.includes(k));
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
  const locked = Object.keys(cards).filter(k => !patterns.includes(k))
    .map(k => `<span class="tag">${k.replace(/_/g, ' ')} — earn by solving</span> `).join('');

  panel('PATTERN GRIMOIRE', `
    <p class="small muted">Cards are earned by demonstrated use, not by walking into a
    region. ${known.length} of ${Object.keys(cards).length} earned.</p>
    ${html || '<p class="small muted">Nothing earned yet. Solve an encounter.</p>'}
    <div class="frame" style="padding:14px">
      <div class="section-title">NOT YET EARNED</div>${locked || '—'}</div>`);
}

function paintInterview() {
  const s = G.state;
  panel('INTERVIEW MODE', `
    <div class="frame" style="padding:16px">
      <p style="line-height:1.8">Interview Mode is sacred. Spells, the mentor, pattern
      names, the Grimoire and the coach are all withheld — enforced by the server,
      not merely hidden in this page. Everything is recorded: time to first code,
      runs, failed trials, syntax errors, final correctness and completion time.</p>
      <p class="small muted">The coach opens the moment the attempt is scored, and not
      one second earlier.</p>
      <div class="section-title">PROFILE</div>
      <div class="row" style="flex-wrap:wrap">
        ${['QUORA', 'GENERAL_SWE', 'SECURITY_ENGINEERING', 'CUSTOM'].map(p =>
          `<button class="btn small ${s.player.profile === p ? 'primary' : ''}"
            data-profile="${p}">${p.replace(/_/g, ' ')}</button>`).join('')}
      </div>
      <p class="small muted" style="margin-top:8px">The QUORA profile weights arrays,
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
  document.querySelectorAll('[data-profile]').forEach(b => {
    b.onclick = async () => { await api.profile(b.dataset.profile); await refresh(); paintInterview(); };
  });
  document.querySelectorAll('[data-format]').forEach(b => {
    b.onclick = async () => {
      const run = await api.startInterview(b.dataset.format, s.player.profile);
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
        enterBattle(await api.interviewCurrent());
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
    <p class="small muted">The coach is available again now.</p>
    <div class="actions"><button class="btn primary" id="iv-done">RETURN</button></div>`,
    { wide: true });
  $('#iv-done').onclick = () => { closeModal(); returnToWorld(); refresh().then(paintWorldSide); };
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

  const attrs = Object.entries(lo.attribute_info).map(([key, info]) =>
    `<div class="attr-row">
      <span class="an" style="color:${info.colour}">${info.label.toUpperCase()}</span>
      <span class="av">${lo.attributes[key] || 0}</span>
      ${lo.unspent_points > 0
        ? `<button class="btn small" data-attr="${key}">+1</button>` : ''}
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
      const r = await api.equip(node.dataset.item);
      if (r.error) { toast('CANNOT EQUIP', r.error, 'red'); return; }
      audio.sfx('unlock');
      await refresh();
      paintCharacter();
    };
  });
  document.querySelectorAll('[data-slot]').forEach(node => {
    node.onclick = async () => {
      if (!lo.equipped[node.dataset.slot]) return;
      await api.unequip(node.dataset.slot);
      audio.sfx('select');
      await refresh();
      paintCharacter();
    };
  });
  document.querySelectorAll('[data-attr]').forEach(node => {
    node.onclick = async () => {
      const r = await api.allocate(node.dataset.attr, 1);
      if (r.error) { toast('CANNOT ALLOCATE', r.error, 'red'); return; }
      audio.sfx('levelup');
      await refresh();
      paintCharacter();
    };
  });
  $('#ch-respec').onclick = async () => {
    const r = await api.respec();
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
      const r = await api.allocate(b.dataset.lvlAttr, 1);
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
    if (!canvas.isConnected) return;
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
        ${[['music', 'Music and sound'], ['crt', 'CRT scanlines'],
           ['reduced_motion', 'Reduced motion'], ['high_contrast', 'High contrast']]
          .map(([k, label]) => `<label class="row" style="margin:8px 0;cursor:pointer">
            <input type="checkbox" data-setting="${k}" ${s[k] ? 'checked' : ''}>
            <span>${label}</span></label>`).join('')}
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
        <div class="section-title">SANDBOX</div>
        <div id="sandbox-status" class="small muted">checking…</div>
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      <div class="section-title">PERFORMANCE HISTORY</div>
      <div id="history-body" class="small muted">loading…</div>
    </div>`);

  document.querySelectorAll('[data-setting]').forEach(input => {
    input.onchange = async () => {
      const value = input.type === 'checkbox' ? input.checked : parseFloat(input.value);
      await api.setting(input.dataset.setting, value);
      await refresh();
    };
  });
  $('#s-export').onclick = async () => {
    const data = await api.exportSave();
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
      const text = await input.files[0].text();
      await api.importSave(JSON.parse(text));
      await refresh();
      toast('IMPORTED', 'Save restored.', 'green');
    };
    input.click();
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
  });
}

/* ---------------- nav + boot ---------------- */

document.querySelectorAll('[data-nav]').forEach(b => {
  b.onclick = () => {
    audio.resume();
    audio.sfx('select');
    const nav = b.dataset.nav;
    if (nav === 'world') { returnToWorld(); return; }
    refresh().then(() => {
      if (nav === 'status') paintStatus();
      else if (nav === 'character') paintCharacter();
      else if (nav === 'quests') paintQuests();
      else if (nav === 'grimoire') paintGrimoire();
      else if (nav === 'interview') paintInterview();
      else if (nav === 'settings') paintSettings();
    });
  };
});

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'n' && G.screen === 'world') startNext();
  if (e.key === 'f' && G.screen === 'world') searchHere();
  if (e.key === 'Escape') { closeModal(); $('#dialogue').classList.remove('show'); }
  if (e.key === ' ' && $('#dialogue').classList.contains('show')) {
    e.preventDefault(); advanceDialogue();
  }
});

window.addEventListener('resize', () => {
  if (G.title) G.title.resize();
  if (G.overworld) G.overworld.resize();
  if (G.viz) G.viz.render();
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
  const spec = await api.diagnostic();
  const answers = {};
  let index = 0;

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
  intro.querySelector('#dg-skip').onclick = async () => {
    audio.sfx('select');
    finish(await api.diagnosticFinish({}, true));
  };

  function step() {
    if (index >= spec.trials.length) {
      api.diagnosticFinish(answers, false).then(finish);
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
      ${body}`);

    if (trial.kind === 'mcq') {
      m2.querySelectorAll('[data-choice]').forEach(node => {
        node.onclick = async () => {
          const r = await api.diagnosticCheck(trial.id, Number(node.dataset.choice));
          answers[trial.id] = { correct: r.correct };
          audio.sfx(r.correct ? 'select' : 'fail');
          index++;
          step();
        };
      });
    } else {
      const ed = new Editor(m2.querySelector('#dg-editor'), { assist: false });
      ed.reset(trial.starter || '');
      m2.querySelector('#dg-run').onclick = async () => {
        const r = await api.diagnosticCheck(trial.id, ed.value);
        answers[trial.id] = { correct: r.correct };
        audio.sfx(r.correct ? 'crit' : 'fail');
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
      const r = await api.chooseBuild(node.dataset.build);
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
      if (id === 'continue') { leaveTitle(); return; }
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
