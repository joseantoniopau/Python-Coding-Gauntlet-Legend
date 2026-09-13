/* Python Coding Gauntlet Legend — the hidden half of the world.
 *
 * Five things that were all built, all proved, and all unreachable:
 *
 *   THE SAGES        sixteen of them, each behind a deed rather than a search.
 *                    Never a grey wall: an unfound sage is drawn as a SILHOUETTE
 *                    with the deed spelled out, because `why` is a thing to go
 *                    and do and that is the no-dead-end rule in working clothes.
 *   THE SECRET ARTS  ninety-six castable lines of typed Python, one per sage per
 *                    class, behind a five-rung gauntlet of REAL problems.
 *   REGALIA          twenty-four objects that buy a companion MORE help and
 *                    never DEEPER help.
 *   THE SANCTUARIES  seventeen hidden healers, found by being hurt in the right
 *                    place rather than by looking.
 *   THE ROLL CALL    the people each boss took, and the ones still held.
 *
 * THE ONE RULE THIS FILE IS BUILT AROUND. `gauntletStage(key)` does NOT take
 * whether the rung was passed — the engine reads that off the attempts table.
 * So the driver here opens the rung's problem through the ordinary encounter
 * door, lets the player answer it the way they answer anything, and then asks
 * the server what happened. A client cannot assert its way to a secret art and
 * this one does not try.
 *
 * AND THE ONE NUMBER IT DOES NOT COMPUTE. Two regalia systems chose the same two
 * levers independently and can reach past what either declares legal. The
 * server folds them through a SINGLE floor and a SINGLE ceiling and reports the
 * numbers ACTUALLY IN FORCE; this draws `floor`, `ceiling`, `floored` and
 * `capped` and works nothing out for itself.
 */
import { api } from './api.js';
import * as sprites from './sprites.js';
import {
  $, el, esc, lines, num, card, prose, meter, makeDisposer, faceFor,
  HOST, refusal, isSealed, sealedTitle, refusalCard,
} from './uikit.js';

export const LEGEND_UI_VERSION = '1.0.0';

const D = makeDisposer();
export const leave = D.leave;

/* The open gauntlet, while one is running: {sage, region, stages, bound, at}. */
let RUN = null;

/* =========================================================== THE SAGES === */

export async function paintSage(regionId) {
  D.leave();
  HOST.panel('THE ONE WHO SITS HERE', `
    <p class="small muted">Sixteen of them, in sixteen regions, found by having
    done the area’s work rather than by searching it. Meeting one costs nothing
    and opens nothing — the trial is still every rung of it, and the art is
    still behind the last one.</p>
    <div id="sage-body"><p class="small muted">Asking after them…</p></div>`);
  const body = $('#sage-body');
  const r = await api.sage(regionId || '').catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NOBODY SITS HERE' }); return; }
  if (!r.available || !r.sage) {
    body.innerHTML = `<div class="frame" style="padding:16px">
      <p class="small">Nobody sits in this region. Sixteen of the seventeen have
      somebody; this is the one that does not.</p></div>`;
    return;
  }
  drawSage(body, r);
}

function drawSage(body, r) {
  const p = r.progress || {};
  const g = r.gauntlet || {};
  const greet = r.greeting || {};
  const met = !!r.met;
  const art = r.art || {};

  body.innerHTML = `
    <div class="frame" style="padding:16px;display:flex;gap:18px;flex-wrap:wrap;
         border-left:4px solid ${met ? 'var(--gold)' : 'var(--line-hi)'}">
      <div id="sage-face" style="flex:0 0 96px"></div>
      <div style="flex:1 1 340px;min-width:280px">
        <div class="pixel" style="font-size:13px;color:${met ? 'var(--gold-hi)' : 'var(--ink-faint)'}">
          ${esc(met ? String(g.name || '').toUpperCase()
                    : String(p.unnamed || 'SOMEBODY').toUpperCase())}</div>
        ${met ? `<div class="small" style="color:var(--violet);margin:4px 0 8px">
          ${esc(g.title || '')}</div>` : `<div class="small muted" style="margin:4px 0 8px">
          not found yet — this is the shape of them, not the name</div>`}
        ${met && g.creed ? `<p class="small" style="color:var(--gold)">
          “${esc(g.creed)}”</p>` : ''}
        <p class="small"><b>Where:</b> ${esc(p.where || greet.where || '')}</p>
        <p class="small"><b>How:</b> ${esc(p.how || greet.how || '')}</p>
        ${greet.line ? `<p class="small" style="font-style:italic">
          “${esc(greet.line)}”</p>` : ''}
        ${!met && p.first_words ? `<p class="small muted">What they will open with:
          “${esc(p.first_words)}”</p>` : ''}
      </div>
    </div>

    ${card('WHAT IS STILL OWED', (p.checks || []).map(c => `
      <div class="gate ${c.met ? 'pass' : 'fail'}">
        <span class="mark">${c.met ? '✔' : '·'}</span>
        <span>${esc(c.label)} — ${num(c.have)} of ${num(c.need)}</span></div>`).join('')
      || '<p class="small muted">Nothing outstanding.</p>')}

    ${card('THE TRIAL', `
      <p class="small">${esc(g.stage_count || 0)} rung(s), each one a REAL problem
      out of the corpus, opened through the ordinary door: same sandbox, same
      grader, same mastery, same loot. Failing costs the toll —
      ${num(g.toll)} more encounter(s) in this region before they will see you
      again — and never a door. A second attempt draws DIFFERENT problems from
      the same specifications.</p>
      ${(g.stages || []).map((s, i) => `
        <div class="rung ${i === 0 ? 'current' : 'next'}">
          <span class="rn">${i + 1}</span>
          <span><b>${esc(s.label)}</b> — ${esc(s.demands)}
            <br><span class="muted small">${esc(s.kind)} ·
              ${esc(s.difficulty)} · ${esc(s.pattern || '')}</span></span>
        </div>`).join('')}
      <p class="small muted" style="margin-top:10px">Behind it:
        <b style="color:var(--violet)">${esc(art.name || g.art && g.art.name || '—')}</b>.
        Named, not rendered — the line itself is what you are being asked to earn.</p>
      <div class="actions" id="sage-actions"></div>
      <p class="small" style="color:${r.may_attempt ? 'var(--green)' : 'var(--orange)'}">
        ${esc(r.why || (r.may_attempt ? 'They will see you.' : ''))}</p>`,
      { accent: r.may_attempt ? 'var(--green)' : '' })}`;

  drawFace($('#sage-face'), met ? 'oracle' : 'scholar');
  const actions = $('#sage-actions');
  if (r.may_attempt) {
    const go = el('button', 'btn primary', 'SIT DOWN FOR THE TRIAL');
    go.onclick = () => beginGauntlet(r.region, go);
    actions.appendChild(go);
  } else {
    actions.innerHTML = '<span class="small muted">Not yet. The line above is a '
      + 'thing to go and do, and nothing here is closed for good.</span>';
  }
}

async function beginGauntlet(regionId, btn) {
  btn.disabled = true;
  const r = await api.beginGauntlet(regionId || '').catch(e => ({ error: e.message }));
  btn.disabled = false;
  if (!r || r.error || !r.started) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT TODAY',
      refusal(r) || 'They are not sitting for this.', 'red');
    return;
  }
  RUN = { region: regionId, stages: r.stages || [], bound: r.bound || {},
          sage: r.sage || '', at: Date.now() };
  HOST.sfx('unlock');
  drawGauntlet();
}

/* The five rungs, with the one that is open marked and its problem reachable.
 * Rebuilt from the server's answer after every stage rather than advanced
 * locally — the record is the authority on which rung is next. */
export function drawGauntlet() {
  if (!RUN) return;
  const body = $('#sage-body') || $('#panel-body');
  if (!body) return;
  const rows = (RUN.stages || []).map((s, i) => {
    const bound = (RUN.bound || {})[s.key];
    const state = RUN.done && RUN.done[s.key];
    return `<div class="list-item${state === 'pass' ? ' chosen' : ''}"
      data-stage="${esc(s.key)}" ${bound ? '' : 'style="opacity:.5"'}>
      <span class="t">${i + 1}. ${esc(s.label)}
        ${state === 'pass' ? '<span class="tag green">CLEARED</span>' : ''}
        ${state === 'fail' ? '<span class="tag red">FAILED</span>' : ''}
        <span class="tag">${esc(s.difficulty || '')}</span></span>
      <span class="d">${esc(s.demands || '')}<br>
        <span class="muted small">${bound
          ? 'bound to a real problem — press to open it'
          : 'nothing bound to this rung'}</span></span></div>`;
  }).join('');

  body.innerHTML = `
    <div class="frame" style="padding:16px;border-left:4px solid var(--violet)">
      <div class="section-title" style="margin-top:0">THE TRIAL IS OPEN</div>
      <p class="small">Open a rung, answer its problem the way you answer
      anything, then come back and settle it. Settling reads the record; it does
      not take your word for it.</p>
    </div>
    <div id="gauntlet-rows" style="margin-top:12px">${rows}</div>
    <div class="actions">
      <button class="btn" id="g-abandon">LEAVE IT FOR NOW</button>
    </div>`;

  for (const node of body.querySelectorAll('[data-stage]')) {
    const key = node.dataset.stage;
    node.onclick = () => openRung(key);
  }
  const quit = $('#g-abandon');
  if (quit) quit.onclick = () => { RUN = null; HOST.back(); };
}

async function openRung(key) {
  const r = await api.gauntletEncounter(key).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'THAT RUNG WILL NOT OPEN',
      refusal(r), 'red');
    return;
  }
  /* An ordinary encounter payload. main.js owns the battle screen, so it is
   * handed straight over; the stage is settled when the player comes back. */
  RUN.pending = key;
  HOST.onEncounter(r);
}

/* Called by main.js when a fight that was opened from a rung is over. It does
 * not say whether it was passed, because it is not entitled to an opinion. */
export async function settlePendingRung() {
  if (!RUN || !RUN.pending) return null;
  const key = RUN.pending;
  RUN.pending = null;
  const r = await api.gauntletStage(key).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    /* Walking out of a rung without answering it is a normal thing to do and
     * is not a failure: the server refuses to settle a rung the attempts table
     * has nothing for, which is the same rule that stops a client asserting
     * its way to an art. The rung stays open and stays pending. */
    if (String(r && r.error).indexOf('not been attempted') >= 0) {
      RUN.pending = key;
      HOST.toast('THE RUNG IS STILL OPEN',
        'You walked out before answering it. Nothing is spent and nothing is '
        + 'failed — the trial is where you left it.', '');
      return null;
    }
    HOST.toast('NOT SETTLED', refusal(r), '');
    return null;
  }
  RUN.done = RUN.done || {};
  if (r.fail) {
    RUN.done[key] = 'fail';
    const run = RUN;
    RUN = null;
    HOST.toast('THE TRIAL ENDS', r.line || r.on_fail
      || `Three more encounters in ${esc(run.region)} before they will see you again.`,
      'red');
    return r;
  }
  RUN.done[key] = 'pass';
  if (r.cleared) {
    const art = r.art || {};
    const name = r.art_name || art.name || '';
    RUN = null;
    HOST.sfx('unlock');
    D.openModal(`<h2 style="color:var(--violet)">${esc(String(name).toUpperCase())}</h2>
      <p>${esc(r.line || art.line || 'It is yours.')}</p>
      <p class="small muted">It is in the movebook now, and the incantations its
      spine is spelled out of came with it. There is one road into an art and
      this was it.</p>
      <div class="actions"><button class="btn primary" id="art-ok">GOOD</button></div>`);
    const ok = $('#art-ok');
    if (ok) ok.onclick = () => { D.dismiss(); paintArts(); };
    await HOST.refresh();
    return r;
  }
  HOST.sfx('select');
  HOST.toast('RUNG CLEARED', r.line || 'Next one.', 'green');
  drawGauntlet();
  return r;
}

export function openRun() { return RUN; }

/* ============================================================ THE ARTS === */

export async function paintArts() {
  D.leave();
  HOST.panel('THE SECRET ARTS', `
    <p class="small muted">Ninety-six of them across six disciplines — sixteen
    for yours, one to a sanctum. Each one is a line of typed Python you can
    actually cast, and none of them can be bought.</p>
    <div id="arts-body"><p class="small muted">Opening the book…</p></div>`);
  const body = $('#arts-body');
  const r = await api.arts().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'THE BOOK IS SHUT' }); return; }
  const ladder = r.ladder || [];
  const known = (r.known || []).length;
  body.innerHTML = `
    <div class="frame" style="padding:14px">
      <div class="pixel" style="font-size:12px;color:var(--gold-hi)">
        ${esc(String(r.class || '').toUpperCase())}</div>
      <p class="small muted">${known} of ${ladder.length} rung(s) known ·
        ${(r.sanctums || []).length} sanctum(s) cleared ·
        ${(r.moves || []).length} move(s) in the book.</p>
    </div>
    ${ladder.map(row => `
      <div class="list-item ${row.known ? '' : 'locked'}" style="cursor:default">
        <span class="t" style="color:${row.known ? 'var(--violet)' : 'var(--ink-faint)'}">
          ${esc(row.numeral || row.rank)} · ${esc(row.known ? row.name : '— not yet —')}
          <span class="tag">${esc(row.region_name || '')}</span>
          ${row.element ? `<span class="tag violet">${esc(row.element)}</span>` : ''}
          <span class="tag">${esc(row.shape || '')}</span></span>
        <span class="d">${row.known
          ? `complexity ${num(row.complexity)}${row.fade
              ? ` · fading at ${Math.round(num(row.fade) * 100)}%` : ''}`
          : `The sage of ${esc(row.region_name || '')} teaches this one, and
             nothing about their trial can be skipped.`}</span>
      </div>`).join('')}`;
}

/* ========================================================== THE REGALIA === */

export async function paintRegalia() {
  D.leave();
  HOST.panel('REGALIA', `
    <p class="small muted">Twenty-four objects, one for each companion, each
    earned by a deed. They buy how SOON and how OFTEN a companion may speak.
    They do not buy how DEEP, and nothing here ever will.</p>
    <div id="reg-body"><p class="small muted">Reading what is worn…</p></div>`);
  const body = $('#reg-body');
  const r = await api.regalia().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NOT WHILE THIS RUNS' }); return; }
  const s = r.schedule || {};
  body.innerHTML = `
    <div class="frame" style="padding:16px;border-left:4px solid var(--violet)">
      <div class="section-title" style="margin-top:0">IN FORCE RIGHT NOW</div>
      <p class="small">${esc(r.pet_name || 'Nobody')} is walking with you in
        ${esc(r.region_name || 'this region')}, at rank
        <b>${esc(s.rank_label || s.rank || '—')}</b>.</p>
      <div class="skill-row"><span class="sn">THRESHOLD</span>
        <span class="sv">×${num(s.threshold_scale, 1).toFixed(3)}</span>
        <span class="stage">${s.floored ? 'AT THE FLOOR' : ''}</span></div>
      <div class="skill-row"><span class="sn">INTERVENTIONS</span>
        <span class="sv">${num(s.interventions)}</span>
        <span class="stage">${s.capped ? 'AT THE CEILING' : ''}</span></div>
      <p class="small muted">The floor is ${num(r.floor, 0.4).toFixed(2)} and the
      ceiling is ${num(r.ceiling, 4)}. There is one of each, and everything that
      moves these two numbers — the objects here and the quest-awarded pieces
      both — is folded through them before it reaches this line. That is what
      stops two systems that chose the same levers independently reaching past
      what either of them declares legal.</p>
      ${s.line ? `<p class="small" style="color:var(--gold)">${esc(s.line)}</p>` : ''}
      ${r.helps_through ? `<p class="small muted">Whatever it wears,
        ${esc(r.pet_name || 'it')} helps through ${esc(r.helps_through)} and no
        further. An object cannot buy a companion a chapter it does not have.</p>` : ''}
      ${prose(r.lines, 'small')}
    </div>
    <div class="section-title">FOR THE ONE WALKING WITH YOU</div>
    <div id="reg-choices" class="grid2"></div>
    <div class="section-title">THE WHOLE CATALOGUE</div>
    <div id="reg-cat"></div>`;

  const host = $('#reg-choices');
  for (const g of (r.choices || [])) host.appendChild(regaliaCard(g, s));
  if (!(r.choices || []).length) {
    host.innerHTML = '<p class="small muted">No companion in the field, so nothing '
      + 'to hang an object on.</p>';
  }
  if (s.regalia) {
    const off = el('button', 'btn small', `TAKE OFF ${String(s.regalia_name || '').toUpperCase()}`);
    off.onclick = () => wear('', off);
    host.appendChild(off);
  }

  const cat = $('#reg-cat');
  for (const row of (r.catalogue || [])) {
    cat.appendChild(el('div', 'list-item', `
      <span class="t">${esc(String(row.pet || '').toUpperCase())}
        <span class="tag">${esc(row.species || '')}</span>
        <span class="tag violet">${esc(row.tier || '')}</span>
        ${row.worn ? `<span class="tag green">wearing ${esc(row.worn)}</span>` : ''}</span>
      <span class="d">${esc(row.note || '')}<br>
        <span class="muted small">${(row.regalia || []).map(g =>
          `${esc(g.name)}${g.found ? '' : ' (unfound)'}`).join(' · ')}</span></span>`));
  }
}

function regaliaCard(g, schedule) {
  const worn = !!g.worn_now;
  const node = el('div', 'frame', `
    <div class="pixel" style="font-size:11px;color:${esc(g.colour || 'var(--gold-hi)')}">
      ${esc(String(g.name || '').toUpperCase())}
      <span class="tag violet">${esc(g.kind_label || g.kind || '')}</span>
      ${worn ? '<span class="tag green">WORN</span>' : ''}</div>
    <p class="small" style="margin:8px 0 4px"><b>${esc(g.buys || '')}</b> —
      ${esc(g.kind_blurb || '')}</p>
    <p class="small muted">${esc(g.blurb || '')}</p>
    <p class="small" style="font-style:italic">“${esc(g.line || '')}”</p>
    ${g.found
      ? `<p class="small muted">${esc(g.worn || '')}<br>
         In its home regions it is worth ${num(g.home_value).toFixed(2)};
         elsewhere ${num(g.away_value).toFixed(2)}.
         ${g.at_home ? '<b style="color:var(--green)">You are in one of them.</b>' : ''}</p>`
      : `<p class="small" style="color:var(--orange)"><b>Where:</b> ${esc(g.where || '')}</p>
         <p class="small" style="color:var(--orange)"><b>How:</b> ${esc(g.how || '')}</p>`}`);
  node.style.padding = '14px';
  if (g.found && !worn) {
    const btn = el('button', 'btn small good', 'PUT IT ON');
    btn.onclick = () => wear(g.id, btn);
    node.appendChild(btn);
  }
  return node;
}

async function wear(id, btn) {
  btn.disabled = true;
  const r = await api.wearRegalia(id).catch(e => ({ error: e.message }));
  btn.disabled = false;
  if (!r || r.error) {
    /* An unfound object answers with `how`, which is the deed. That is a thing
     * to go and do, so it is shown rather than swallowed. */
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT YET YOURS',
      r && r.how ? r.how : refusal(r), 'red');
    return;
  }
  HOST.sfx('unlock');
  HOST.toast(id ? 'WORN' : 'TAKEN OFF', r.line || '', 'green');
  await HOST.refresh();
  await paintRegalia();
}

/* ======================================================= THE SANCTUARIES === */

export async function paintSanctuaries() {
  D.leave();
  HOST.panel('THE HIDDEN HEALERS', `
    <p class="small muted">Seventeen of them, and not one is found by searching.
    They are found by being hurt in the right place — which is why the journal
    below is a record rather than a map.</p>
    <div id="sanc-body"><p class="small muted">Turning the page…</p></div>`);
  const body = $('#sanc-body');
  const r = await api.sanctuaries().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NO PAGE HERE' }); return; }
  const j = r.journal || {};
  const need = r.needed || {};
  const limits = j.limits || {};
  body.innerHTML = `
    <div class="frame" style="padding:16px;border-left:4px solid ${
      need.urgent ? 'var(--red)' : 'var(--green)'}">
      <div class="section-title" style="margin-top:0">RIGHT NOW</div>
      <p class="small">${num(need.health)}/${num(need.health_max, 1)} health,
        band <b>${esc(need.band || '—')}</b>,
        ${num(need.failures_left)} bad submission(s) of grace.
        ${(need.fainted_companions || []).length
          ? `<span style="color:var(--red)">${
              esc(need.fainted_companions.join(' and '))} is down.</span>` : ''}</p>
      <p class="small" style="color:${need.urgent ? 'var(--red)' : 'var(--ink-faint)'}">
        ${need.urgent
          ? 'One of them would show itself to you in the right place right now.'
          : 'None of them is urgent. They show themselves to people who need them.'}</p>
    </div>
    ${card('THE TERMS', `
      <p class="small">Sitting down is <b>free</b>, for the same reason the Mender
      is free.</p>
      <p class="small muted">${esc(j.free_because || '')}</p>
      <div class="gate pass"><span class="mark">·</span><span>One rest to a
        descent.</span></div>
      <div class="gate pass"><span class="mark">·</span><span>${
        num(limits.cooldown_clears)} clear(s) between rests, counted save-wide —
        ${num(limits.cooldown_left)} to go.</span></div>
      <div class="gate pass"><span class="mark">·</span><span>The toll is
        ${esc(limits.toll || 'armour integrity, never gold')} —
        ${num(limits.toll_points).toFixed(1)} point(s). Gold cost:
        ${num(limits.gold_cost)}.</span></div>`)}
    ${card('THE JOURNAL', `
      <p class="small muted">${num(j.found_count)} of ${num(j.total)} found ·
        ${num(j.still_hidden)} still hidden · ${num(j.rests)} rest(s) taken.</p>
      ${(j.found || []).map(f => `<div class="list-item" style="cursor:default">
        <span class="t">${esc(f.name || f.id)}
          <span class="tag">${esc(f.trade || '')}</span>
          <span class="tag violet">${esc(f.kind || '')}</span>
          ${f.dungeon ? '<span class="tag">underground</span>' : ''}</span>
        <span class="d">${esc(f.place || '')}<br>
          <span class="muted small">${esc(f.why || '')}
          ${num(f.cooldown_left) ? ` · ${num(f.cooldown_left)} clear(s) before they
            will sit you down again` : ' · ready'}</span></span></div>`).join('')
      || '<p class="small muted">Nothing found yet. That is the normal state of '
        + 'this page for a long while, and it is not a failure — go and get hurt '
        + 'somewhere interesting.</p>'}`)}
    <div id="sanc-marks"></div>`;

  const marks = $('#sanc-marks');
  const rows = r.marks || [];
  if (!rows.length) return;
  marks.innerHTML = `<div class="section-title">ON THIS FLOOR</div>`;
  for (const m of rows) {
    const row = el('div', `list-item${m.available ? '' : ' locked'}`, `
      <span class="t">${esc(m.name || m.id || 'A TENT')}
        <span class="tag">${esc(m.trade || '')}</span>
        <span class="tag ${m.available ? 'green' : 'red'}">room ${num(m.room)}</span></span>
      <span class="d">${m.available
        ? 'Sitting down here is free and revives a fainted companion. It costs '
          + 'armour integrity and a place in the town clock, and nothing else.'
        : 'Not this descent. One rest to a descent, and one clock for all '
          + 'seventeen of them.'}</span>`);
    if (m.available) row.onclick = () => rest(m.id);
    marks.appendChild(row);
  }
}

export async function rest(sanctuaryId) {
  const r = await api.sanctuaryRest(sanctuaryId).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT THIS TIME', refusal(r), 'red');
    return null;
  }
  HOST.sfx('unlock');
  HOST.toast('YOU SIT DOWN', `+${num(r.restored)} health${
    (r.revived || []).length ? `, ${r.revived.join(' and ')} back up` : ''}. Free.`,
    'green');
  if (lines(r.lines).length) {
    HOST.say(String((r.healer || {}).name || 'THE HEALER').toUpperCase(),
      [...lines(r.scene), ...lines(r.lines), ...lines(r.toll_lines)], 'druid');
  } else if (lines(r.toll_lines).length) {
    HOST.say(String((r.healer || {}).name || 'THE HEALER').toUpperCase(),
      lines(r.lines), 'druid');
  }
  await HOST.refresh();
  return r;
}

/* ========================================================= THE ROLL CALL === */

export async function paintRollCall() {
  D.leave();
  HOST.panel('THE ROLL CALL', `
    <p class="small muted">The people each boss took out of its village. They are
    freed when it falls, and the ones still held are listed beside them in the
    same shape — because the ending of this game is a eucatastrophe and not a
    restoration, and a roll call that quietly rounded up would be the game
    telling a lie about itself.</p>
    <div id="roll-body"><p class="small muted">Reading the names…</p></div>`);
  const body = $('#roll-body');
  const r = await api.rollCall().catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NO NAMES' }); return; }
  const freed = r.freed || [];
  const held = r.still_held || [];
  // THE THIRD LIST, and leaving it out was the same lie in the other
  // direction. There are two roads out of a niche: carried out by the player
  // when the boss holding you fell, or up on your own feet when the index
  // stopped pointing. This screen used to know only the first, so a save where
  // the index fell read "0 walked out · 0 still in a niche · 25 in total" —
  // twenty-five people out and the panel counting none of them.
  //
  // They are kept apart rather than added together on purpose. `captives.py`
  // is explicit that the ending is a eucatastrophe and not a restoration, and
  // the finale's own ribbon says the same thing in one sentence:
  // "{count} BY YOUR HAND. {released} BY THE FALL OF IT."
  const released = r.released || [];
  body.innerHTML = `
    <div class="frame" style="padding:14px">
      <p class="small"><b style="color:var(--green)">${freed.length}</b> walked out ·
        ${released.length ? `<b style="color:var(--gold)">${released.length}</b>
          got up on their own · ` : ''}
        <b style="color:var(--orange)">${held.length}</b> still in a niche ·
        ${num(r.total)} in total.</p>
      ${(r.changes || []).length ? `<p class="small muted">${
        esc(lines(r.changes).slice(0, 3).join(' '))}</p>` : ''}
    </div>
    ${freed.length ? `<div class="section-title">OUT</div>
      <div id="roll-freed" class="grid2"></div>` : ''}
    ${released.length ? `<div class="section-title">THE ONES NOBODY CAME FOR</div>
      <div id="roll-released" class="grid2"></div>` : ''}
    <div class="section-title">STILL HELD</div>
    <div id="roll-held" class="grid2"></div>`;
  const f = $('#roll-freed');
  if (f) for (const row of freed) f.appendChild(captiveCard(row, true));
  const rel = $('#roll-released');
  if (rel) for (const row of released) rel.appendChild(captiveCard(row, true));
  const h = $('#roll-held');
  for (const row of held) h.appendChild(captiveCard(row, false));
}

function captiveCard(c, out) {
  const node = el('div', 'frame', `
    <div style="display:flex;gap:12px">
      <div class="cap-face" style="flex:0 0 56px"></div>
      <div style="flex:1;min-width:0">
        <div class="pixel" style="font-size:10px;color:${out ? 'var(--green)' : 'var(--ink-dim)'}">
          ${esc(String(c.name || '').toUpperCase())}</div>
        <div class="small muted" style="margin:4px 0">${esc(c.trade || '')} of
          ${esc(c.home_name || c.home || '')}</div>
        <p class="small">${esc(c.bearing || '')}</p>
        <p class="small muted" style="font-style:italic">${
          esc(c.released_line || lines(c.lines)[0] || '')}</p>
        ${out ? `<p class="small" style="color:var(--green)">${esc(c.afterwards || '')}</p>
                 <p class="small muted">${esc(c.change || '')}</p>`
              : `<p class="small muted">Held in ${esc(c.held_in || '')} by
                 ${esc(String(c.boss || '').replace(/_/g, ' '))}.</p>`}
      </div>
    </div>`);
  node.style.padding = '12px';
  drawFace(node.querySelector('.cap-face'), c.sprite || 'villager', 56);
  return node;
}

/* ------------------------------------------------------------------ faces */

function drawFace(host, kind, size = 72) {
  if (!host) return;
  let img;
  try { img = sprites.portrait(faceFor(kind)); } catch (e) { return; }
  if (!img) return;
  const c = el('canvas');
  c.width = img.width; c.height = img.height;
  c.style.cssText = `width:${size}px;height:${size}px;image-rendering:pixelated;display:block`;
  c.getContext('2d').drawImage(img, 0, 0);
  host.innerHTML = '';
  host.appendChild(c);
}
