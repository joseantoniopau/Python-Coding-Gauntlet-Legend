/* Python Coding Gauntlet Legend — THE HUNT.
 *
 * Seventeen roaming apex monsters, one per region, scaled to PREPARATION and to
 * nothing else — not to level, not to mastery. This file draws three things and
 * decides none of them:
 *
 *   THE READOUT    what is out there, what it examines, and how long this will
 *                  take AT THE DOOR. `scaling.blurb` says fifty-two casts before
 *                  the fight, so a player at readiness zero can look at that and
 *                  walk away rather than find out afterwards.
 *   THE TELEGRAPH  hunters.TELEGRAPH, mirrored onto the region card. The canvas
 *                  half of it is overworld.js and apex.js's and was already
 *                  written; what was missing was the row reaching them and the
 *                  words beside it.
 *   THE ESCAPE     always visible, never refused, never a roll.
 *
 * THE DIVISION OF LABOUR, because getting it wrong puts the creature in two
 * places at once. `hunters.hunt_step` is the authority on the chase and the
 * ENGINE runs it, one resolved encounter at a time. `client_payload()` is the
 * contract — speeds, distances, the telegraph table — and it is static for the
 * life of the process, so it is fetched once and kept. NOTHING HERE ADVANCES A
 * HUNT. The row is read, mirrored and drawn; when it changes, it changed on the
 * server.
 *
 * WHAT THIS FILE DOES RUN is the FIGHT, and that is deliberate and is in the
 * contract: `hunt_engage` freezes the scaling and hands back a pool and a
 * per-cast number, and `hunt_resolve({casts, killed})` is told how many lines
 * actually landed. The engine grades nothing here and grants no mastery,
 * because the casting was already paid for where casting is paid for — every
 * one of those casts was an ordinary graded submission through the ordinary
 * door. The pool is bookkeeping over work that already happened.
 *
 * FLEE ALWAYS SUCCEEDS. No roll, turn one included, no gold, no items, no
 * mastery, and it is the one door here that is never sealed. The button is on
 * screen for the whole fight for that reason — a door that could refuse it
 * would trap a player in a fight they were told they could always leave.
 */
import { api } from './api.js';
import * as bosses from './bosses.js';
import {
  $, el, esc, lines, num, card, prose, meter, makeDisposer,
  HOST, refusal, isSealed, sealedTitle, refusalCard,
} from './uikit.js';

export const HUNT_UI_VERSION = '1.0.0';

const D = makeDisposer();
export const leave = D.leave;

/* hunters.client_payload(): forty kilobytes, static for the life of the
 * process. Kept after the first read and ignored thereafter, exactly as api.js
 * asks. */
let CLIENT = null;
/* The last readout, per region. */
let VIEW = null;
/* The fight, while one is open. Frozen at engage and never recomputed:
 * { region, apex, name, colour, hp, hpLeft, perCast, casts, targetCasts, blurb } */
let FIGHT = null;
/* The banner node, if it is up. One node, reused. */
let BANNER = null;
/* The last stage the overworld reported, and the info it came with. Read by
 * `stage()` so a caller can ask what is happening without a fetch. */
let STAGE = { state: 'DORMANT', info: null };

export function stage() { return STAGE; }

const STORE_KEY = 'gauntlet-hunt-fight';

/* ------------------------------------------------------------- the readout */

export async function paintHunt(regionId) {
  D.leave();
  HOST.panel('THE HUNT', `
    <p class="small muted">One apex to a region. It is scaled to what you brought,
    not to what you are — and the readout says how long it will take before you
    turn round, never after.</p>
    <div id="hunt-body"><p class="small muted">Looking at the ground…</p></div>`);
  const body = $('#hunt-body');
  const r = await read(regionId);
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NOTHING HUNTS HERE' }); return; }
  if (!r.apex) {
    body.innerHTML = `<div class="frame" style="padding:16px">
      <p class="small">${esc(r.line || 'Nothing hunts here.')}</p></div>`;
    return;
  }
  drawReadout(body, r);
}

/* One fetch. `client` is adopted once and dropped from everything after. */
export async function read(regionId) {
  const r = await api.hunt(regionId || '').catch(e => ({ error: e.message }));
  if (r && r.client && !CLIENT) CLIENT = r.client;
  if (r && !r.error) VIEW = r;
  return r;
}

export function payload() { return CLIENT; }
export function view() { return VIEW; }

function drawReadout(body, r) {
  const apex = r.apex || {};
  const hunt = r.hunt || {};
  const ready = r.readiness || {};
  const scaling = r.scaling || {};
  const lesson = r.lesson || {};
  const tele = r.telegraph || {};
  const parts = ready.parts || {};
  const engageable = ['TRACKING', 'CLOSING', 'ENGAGED'].indexOf(hunt.state) >= 0;

  body.innerHTML = `
    <div class="frame" style="padding:16px;display:flex;gap:18px;flex-wrap:wrap;
         border-left:4px solid ${esc(apex.colour || 'var(--line-hi)')}">
      <div id="apex-art" style="flex:0 0 168px"></div>
      <div style="flex:1 1 340px;min-width:280px">
        <div class="pixel" style="font-size:14px;color:${esc(apex.colour || 'var(--gold-hi)')}">
          ${esc(String(apex.name || '').toUpperCase())}</div>
        <div class="small" style="margin:6px 0">
          <span class="tag violet">${esc(apex.element || 'NEUTRAL')}</span>
          <span class="tag">${esc(apex.exam_difficulty || '')}</span>
          <span class="tag gold">${num(r.kills)} killed</span>
          <span class="tag ${engageable ? 'red' : ''}">${esc(hunt.state || 'DORMANT')}</span>
        </div>
        <p class="small">${esc(apex.silhouette || '')}</p>
        <p class="small muted">${esc(apex.presence || '')}</p>
        ${tele.line ? `<p class="small" style="color:var(--orange)">${
          esc(telegraphLine(tele, { name: apex.name,
                                    regionName: apex.region_name }))}</p>` : ''}
      </div>
    </div>

    <div class="grid2" style="margin-top:12px">
      ${card('WHAT IT EXAMINES', `
        <p class="small">${esc(lesson.lesson || apex.lesson || '')}</p>
        <p class="small muted"><b>The tell:</b> ${esc(lesson.tell || apex.tell || '')}</p>
        ${lesson.counter ? `<p class="small" style="color:var(--green)">Countered by
          ${esc(lesson.counter)}.</p>` : ''}
        ${lesson.ward ? `<p class="small" style="color:var(--blue)">Warded by
          ${esc(lesson.ward)}.</p>` : ''}
        <p class="small muted">It examines ${esc(lesson.examines_hardest || '—')} hardest.</p>`,
        { accent: apex.colour })}

      ${card('HOW LONG THIS WILL TAKE', `
        <div class="pixel" style="font-size:16px;color:${scalingColour(scaling.band)}">
          ${num(scaling.target_casts)} CASTS</div>
        <p class="small" style="margin:8px 0">${esc(scaling.blurb || '')}</p>
        ${meter('READINESS', ready.score, 100, scalingColour(ready.band),
          esc(ready.band || ''))}
        <p class="small muted">Pool ${num(scaling.hp)} · your line lands
          ${num(scaling.per_cast_damage).toFixed(2)} of it · it hits at
          ×${num(scaling.strike_multiplier, 1).toFixed(2)} · matchup
          ${esc(scaling.matchup || 'NEUTRAL')}.</p>
        <p class="small muted">Said here rather than afterwards. At readiness zero
        this is not a fight the design expects you to win; it expects you to look
        at it and leave, and leaving is free.</p>`, { accent: scalingColour(scaling.band) })}
    </div>

    ${card('THE FIVE THINGS IT WEIGHS', Object.keys(parts).map(k => {
      const p = parts[k] || {};
      return `<div class="list-item" style="cursor:default">
        <span class="t">${esc(k.toUpperCase())}
          <span class="tag ${num(p.fraction) >= 0.99 ? 'green'
            : num(p.fraction) > 0 ? 'orange' : 'red'}">${
            Math.round(num(p.earned))} of ${Math.round(num(p.weight))}</span></span>
        <span class="d">${esc(p.note || '')}</span></div>`;
    }).join('') + (lines(ready.advice).length
      ? `<div class="section-title">WHAT TO FIX FIRST</div>${prose(ready.advice, 'small')}`
      : ''))}

    <div id="hunt-actions" class="actions" style="margin:12px 0"></div>

    ${card('THE EIGHT PROMISES', Object.keys(r.guarantees || {}).map(k => {
      const g = (r.guarantees || {})[k] || {};
      return `<div class="gate ${g.holds ? 'pass' : 'fail'}">
        <span class="mark">${g.holds ? '✔' : '✘'}</span>
        <span>${esc(g.says || k)}</span></div>`;
    }).join('') || '<p class="small muted">Not reported.</p>',
      { accent: 'var(--green)' })}`;

  drawApex($('#apex-art'), apex);

  const actions = $('#hunt-actions');
  if (FIGHT) {
    actions.innerHTML = '<span class="small muted">A fight is already open — '
      + 'the strip at the bottom of the screen is it.</span>';
  } else if (engageable) {
    const go = el('button', 'btn danger', 'TURN AND FACE IT');
    go.onclick = () => engage(r.region, go);
    const walk = el('button', 'btn', 'WALK AWAY');
    walk.onclick = () => HOST.back();
    actions.append(go, walk);
    actions.appendChild(el('span', 'small muted',
      'Engaging freezes the scaling. That is what stops a player stripping their '
      + 'gear mid-fight to shrink the pool, and it stops the pool growing under '
      + 'somebody who upgrades between rounds.'));
  } else {
    actions.innerHTML = `<span class="small muted">It is ${
      esc(String(hunt.state || 'DORMANT').toLowerCase())}. You cannot turn and face
      something that is not on your trail — keep clearing encounters here and it
      will find you.</span>`;
  }
}

function scalingColour(band) {
  return band === 'READY' || band === 'PREPARED' ? 'var(--green)'
    : band === 'THIN' ? 'var(--orange)'
    : band === 'BARE' || band === 'NONE' ? 'var(--red)' : 'var(--gold)';
}

/* The creature, at MAP scale, through bosses.drawBoss. `sprite` is the authored
 * key nobody has drawn yet and `sprite_fallback` is an archetype that resolves
 * today, so this has a face now and a better one the hour somebody draws it —
 * resolveBoss walks that list itself and never returns nothing. */
function drawApex(host, apex) {
  if (!host) return;
  const c = el('canvas');
  c.width = 168; c.height = 156;
  c.style.cssText = 'width:168px;height:156px;image-rendering:pixelated;display:block';
  host.innerHTML = '';
  host.appendChild(c);
  const ctx = c.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const key = apex.sprite || apex.sprite_fallback || apex.id;
  const t0 = performance.now();
  const reduced = document.body.classList.contains('reduced-motion');
  const paint = () => {
    ctx.clearRect(0, 0, c.width, c.height);
    try {
      // MAP form, not the battle-stage form: `map: true` is what picks the
      // forty-eight-pixel body the overworld uses, and the scale on top of it
      // is only how big it is drawn on this page. An apex has one silhouette
      // and this is it, larger.
      bosses.drawBoss(ctx, key, c.width / 2, c.height - 10, {
        scale: 3, map: true, time: performance.now() - t0,
        colour: apex.colour, element: apex.element, reducedMotion: reduced,
      });
    } catch (e) { /* a face that will not draw is not a reason to lose the page */ }
  };
  paint();
  if (!reduced) D.frames(c, paint);
}

/* ------------------------------------------------------------- the fight */

export async function engage(regionId, btn) {
  // The contact prompt may still be standing — the creature arrived on the
  // overworld while the player was reading the readout, and both doors lead
  // here. Two ways in, one fight, and no modal left over it.
  D.dismiss();
  if (btn) btn.disabled = true;
  const r = await api.huntEngage(regionId || '').catch(e => ({ error: e.message }));
  if (btn) btn.disabled = false;
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'IT IS NOT THERE', refusal(r), 'red');
    return null;
  }
  const scaling = r.scaling || {};
  const apex = (VIEW || {}).apex || {};
  FIGHT = {
    region: regionId || (VIEW || {}).region || '',
    apex: scaling.apex || apex.id || '',
    name: apex.name || scaling.apex || 'IT',
    colour: apex.colour || '#ff6a7a',
    hp: num(scaling.hp),
    hpLeft: num(scaling.hp),
    perCast: num(scaling.per_cast_damage),
    targetCasts: num(scaling.target_casts),
    casts: 0,
    blurb: scaling.blurb || r.line || '',
  };
  save();
  HOST.sfx('boss');
  HOST.toast('IT TURNS', r.line || scaling.blurb || '', 'red');
  showBanner();
  return FIGHT;
}

/* A graded submission landed in the region the fight is in. THE TYPING IS THE
 * ATTACK: this is the only thing that moves the pool, it is called from the
 * result path and nowhere else, and it counts what the grader already
 * counted. */
export function castLanded({ region, solved, measured }) {
  if (!FIGHT) return null;
  if (region && FIGHT.region && region !== FIGHT.region) return null;
  /* A measured run pays nothing into the world, and an apex pool is the world.
   * The engine already refuses to resolve a hunt during one; draining the pool
   * anyway would leave a player who sat an exam mid-hunt with a creature the
   * interface says is nearly dead and the server says is untouched. The banner
   * stays up — walking away is never sealed — and nothing counts. */
  if (measured) { showBanner(); return FIGHT; }
  if (!solved) { showBanner(); return FIGHT; }
  FIGHT.casts += 1;
  FIGHT.hpLeft = Math.max(0, FIGHT.hpLeft - FIGHT.perCast);
  save();
  showBanner();
  if (FIGHT.hpLeft <= 0) { resolve(true); return null; }
  return FIGHT;
}

export function fight() { return FIGHT; }

export async function flee() {
  if (!FIGHT) return null;
  const r = await api.huntFlee().catch(e => ({ error: e.message }));
  FIGHT = null;
  save();
  hideBanner();
  /* The refusal branch is here for honesty and is not expected to fire: flee is
   * the one door in this feature that is never sealed. If it ever answers no,
   * the player is told rather than left standing in a fight the interface has
   * quietly forgotten about. */
  if (!r || r.error) {
    HOST.toast('YOU WALK ANYWAY', refusal(r) || 'It does not get to decide that.', '');
    return null;
  }
  HOST.sfx('select');
  HOST.toast('YOU WALK', r.line || 'It does not get to decide whether that works.', '');
  await HOST.refresh();
  return r;
}

export async function resolve(killed) {
  const f = FIGHT;
  if (!f) return null;
  FIGHT = null;
  save();
  hideBanner();
  const r = await api.huntResolve(f.casts, !!killed).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast('THE BOUNTY WENT UNPAID', refusal(r), 'red');
    return null;
  }
  if (!killed) { await HOST.refresh(); return r; }
  HOST.sfx('unlock');
  const paid = r.paid || r.bounty || {};
  const bits = [];
  if (num(paid.gold)) bits.push(`${num(paid.gold)} gold`);
  if (paid.metal && paid.metal.id) bits.push(`${paid.metal.count}× ${paid.metal.id}`);
  if (paid.potion && paid.potion.count) bits.push(`${paid.potion.count} draught(s)`);
  if (paid.trophy) bits.push(`the ${String(paid.trophy).replace(/_/g, ' ')}`);
  D.openModal(`<h2 style="color:var(--gold-hi)">${esc(String(f.name).toUpperCase())} IS DOWN</h2>
    <p>${esc(f.casts)} line(s) of Python landed. Nothing here graded any of them —
    the casting was already paid for where casting is paid for.</p>
    <p class="small">The bounty is priced on your readiness AT THE MOMENT THE FIGHT
    STARTED, so somebody who had no business winning is paid for having had no
    business winning.</p>
    <p style="color:var(--gold)">${esc(bits.join(' · ') || 'Nothing dropped.')}</p>
    ${r.line ? `<p class="small muted">${esc(r.line)}</p>` : ''}
    <div class="actions"><button class="btn primary" id="hunt-done">GOOD</button></div>`);
  const done = $('#hunt-done');
  if (done) done.onclick = () => D.dismiss();
  await HOST.refresh();
  return r;
}

/* ------------------------------------------------------------- the banner
 *
 * Up for the whole fight, on every screen, because the escape has to be visible
 * from wherever the player happens to be typing. It is fixed to the bottom of
 * the viewport rather than to a screen for the same reason. */
function showBanner() {
  if (!FIGHT) return;
  if (!BANNER || !BANNER.isConnected) {
    BANNER = el('div', 'hunt-banner');
    document.body.appendChild(BANNER);
  }
  const f = FIGHT;
  const left = Math.max(0, Math.ceil(f.hpLeft / Math.max(0.01, f.perCast)));
  BANNER.style.setProperty('--apex', f.colour);
  BANNER.innerHTML = `
    <div class="hb-name">${esc(String(f.name).toUpperCase())}</div>
    <div class="hb-bar"><i style="width:${(f.hpLeft / Math.max(1, f.hp)) * 100}%"></i></div>
    <div class="hb-num">${Math.ceil(f.hpLeft)} / ${Math.round(f.hp)}</div>
    <div class="hb-casts">${f.casts} cast(s) landed · about ${left} to go</div>
    <button class="btn small danger" id="hb-flee">WALK AWAY</button>`;
  const btn = $('#hb-flee', BANNER);
  if (btn) btn.onclick = () => flee();
}

function hideBanner() {
  if (BANNER && BANNER.isConnected) BANNER.remove();
  BANNER = null;
}

/* ------------------------------------------------------ the overworld glue
 *
 * overworld.js already mirrors the chase and apex.js already draws it; what did
 * not exist was the row reaching them. `stateFor` is what main.js hands its
 * stateSource, and `onStage` is what it hands onApexStage. */
export function stateFor(state) {
  if (!state) return state;
  const v = VIEW;
  if (!v || !v.hunt) return state;
  /* Mutated onto the object main.js already holds rather than spread into a new
   * one: stateSource is read EVERY FRAME by two different consumers, and a
   * fresh object per frame in that path is exactly what the per-frame budget in
   * overworld.js is written to avoid. */
  state.hunt = v.hunt;
  state.apexes = (CLIENT && CLIENT.apexes) || (v.apex ? [v.apex] : []);
  if (CLIENT) state.apex_payload = CLIENT;
  return state;
}

/* The canvas says it wordlessly on purpose. This is the words: the telegraph
 * line for the state, and at CLOSING the countdown, which is the one thing the
 * drawn telegraph deliberately is not. */
/* hunters.TELEGRAPH's lines carry three placeholders — {name}, {region} and
 * {seconds} — and they are the module's, filled here rather than rewritten.
 * Printing one raw is how a player ends up reading "{name} has your trail". */
function telegraphLine(cfg, info, fallback) {
  const raw = (cfg && cfg.line) || fallback || '';
  if (!raw) return '';
  const name = (info && info.name) ? String(info.name) : 'Something';
  const region = (info && info.regionName) ? String(info.regionName)
    : (VIEW && VIEW.apex ? VIEW.apex.region_name : '') || 'this region';
  let out = raw.replace(/\{name\}/g, name).replace(/\{region\}/g, region);
  // The countdown only exists at CLOSING and only when the mirror knows how far
  // away the creature is. Where it does not, the clause is dropped rather than
  // printed as an em dash: "— seconds." is worse than no sentence about time.
  if (info && Number.isFinite(info.seconds)) {
    out = out.replace(/\{seconds\}/g, info.seconds.toFixed(1));
  } else {
    out = out.replace(/\s*\{seconds\}[^.]*\.?/g, '').trim();
  }
  return out;
}

export function onStage(stage, info) {
  STAGE = { state: stage, info: info || null };
  const card_ = document.querySelector('#region-card');
  let note = card_ && card_.querySelector('#apex-telegraph');
  const cfg = (CLIENT && CLIENT.telegraph && CLIENT.telegraph[stage]) || {};
  const quiet = !info || stage === 'DORMANT' || stage === 'SPENT';
  if (quiet) { if (note) note.remove(); return; }
  if (!note && card_) {
    note = el('div', '');
    note.id = 'apex-telegraph';
    card_.appendChild(note);
  }
  if (!note) return;
  note.style.cssText = `margin-top:8px;padding:6px 8px;border-left:3px solid ${
    info.colour || 'var(--red)'};font-size:calc(11px * var(--scale));line-height:1.5`;
  // The line already names the creature — hunters.TELEGRAPH puts {name} in five
  // of its six — so the bold prefix would say it twice. It is the STATE that is
  // worth putting in capitals beside it.
  note.innerHTML = `<b style="color:${esc(info.colour || 'var(--red)')}">${
    esc(String(stage))}</b>
    <span class="muted"> — ${esc(telegraphLine(cfg, info, stage.toLowerCase()))}</span>
    ${Number.isFinite(info.seconds)
      ? `<br><span style="color:var(--red)">${info.seconds.toFixed(1)}s</span>` : ''}
    ${Number.isFinite(info.tiles)
      ? `<span class="muted"> · ${Math.round(info.tiles)} tile(s) off</span>` : ''}`;
}

/* It arrived. The ENGINE decides whether a fight starts; this offers the door
 * and puts the way out beside it. */
export function onContact(info) {
  if (FIGHT) return;
  D.openModal(`<h2 style="color:${esc((info && info.colour) || 'var(--red)')}">
      ${esc(String((info && info.name) || 'IT').toUpperCase())}</h2>
    <p>It has closed the distance. Turning and facing it freezes the scaling
    where it stands right now; walking costs three points of health and your
    streak, and it always works.</p>
    <div class="actions">
      <button class="btn danger" id="ap-fight">TURN AND FACE IT</button>
      <button class="btn" id="ap-walk">WALK</button>
    </div>`);
  const go = $('#ap-fight');
  const walk = $('#ap-walk');
  if (go) go.onclick = async () => { D.dismiss(); await engage((info || {}).regionId, null); };
  if (walk) walk.onclick = () => D.dismiss();
}

/* A hunt row off the result of a graded submission. The engine ticks the chase
 * once per resolved encounter and ships the new row under `hunt`; this is the
 * client hearing about it without a second fetch. */
export function noteResult(result, regionId, measured) {
  if (!result) return;
  /* `hunt` is the engine's own new row — `_tick_hunt` advanced the chase by one
   * encounter's worth of seconds and shipped the result — so the readout is
   * brought up to date without a second fetch, and the overworld's mirror sees
   * the change on the next frame through stateFor(). */
  const row = result.hunt;
  if (row && VIEW) VIEW.hunt = { ...(VIEW.hunt || {}), ...row };
  castLanded({ region: regionId || '', solved: !!result.solved, measured: !!measured });
}

/* ---------------------------------------------------------------- storage
 *
 * A fight survives a reload, because a player who alt-tabbed into a reference
 * page and came back should not find the creature quietly gone and the server
 * still holding an open fight block. */
function save() {
  try {
    if (FIGHT) localStorage.setItem(STORE_KEY, JSON.stringify(FIGHT));
    else localStorage.removeItem(STORE_KEY);
  } catch (e) { /* a full disk is not a reason to lose the fight */ }
}

export function restore() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return null;
    const f = JSON.parse(raw);
    if (!f || !f.apex) return null;
    FIGHT = f;
    showBanner();
    return f;
  } catch (e) { return null; }
}
