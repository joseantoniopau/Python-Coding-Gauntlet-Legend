/* Python Coding Gauntlet Legend — THE LAST SCENE.
 *
 * finale.py hands over a SCRIPT, not a picture: sixteen beats with `at_ms` and
 * `duration_ms`, a freeze at 25 700ms with a guitar hit on the same frame, a
 * title card with its own bevel and overshoot, and a roll call whose pullback
 * is a number. All this file does is run a clock against that script. Every
 * word, every timing and every colour below came off the wire.
 *
 * THE DIRECTION OF THE GATE, said once. The practical gates the finale and the
 * finale does not gate the practical. A player who freed nobody sits the same
 * sealed, timed, unassisted exam and can pass it, and this scene plays for them
 * too, with an empty gallery behind them and a ribbon that says so. Rounding
 * that up would be the game lying about itself.
 *
 * THE TWO HALVES. `title_card_at_ms` is the freeze frame and it is NOT the end.
 * `the_prompt_stays` is, and `markCodaSeen()` fires there and nowhere else — a
 * player who walked out at the title card has seen half of this.
 *
 * TIMERS. One rAF loop and nothing else, registered in the disposer, killed by
 * every dismissal path there is: the skip button, Escape, the end of the
 * script, and the screen being torn down underneath it.
 */
import { api } from './api.js';
import {
  $, el, esc, lines, num, makeDisposer, HOST, refusal, isSealed, sealedTitle,
  refusalCard,
} from './uikit.js';
import { audio } from './audio.js';

export const FINALE_UI_VERSION = '1.0.0';

const D = makeDisposer();
export const leave = () => { stop(); D.leave(); };

let SCENE = null;
let LAYER = null;
let T0 = 0;
let PAUSED = false;
let CODA_SENT = false;
let SHOWN = -1;

/* -------------------------------------------------------------- the door */

/* Staged AFTER the practical is scored and never before. The exam report the
 * player was just handed is passed straight through — this file does not read
 * it, finale.py does. */
export async function play(examReport) {
  const r = await api.finale(examReport || {}).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT YET', refusal(r), 'red');
    return null;
  }
  SCENE = r;
  CODA_SENT = false;
  SHOWN = -1;
  mount();
  return r;
}

/* The read-only version: what the scene WOULD be, as a page. Reachable from the
 * ledger so a player can find out there is one without finishing the game. */
export async function paintFinaleCard() {
  D.leave();
  HOST.panel('THE LAST SCENE', `
    <p class="small muted">It is staged after the practical is scored and never
    before. The practical gates this; this does not gate the practical.</p>
    <div id="fin-body"><p class="small muted">Reading the script…</p></div>`);
  const body = $('#fin-body');
  const r = await api.finale({}).catch(e => ({ error: e.message }));
  if (!body.isConnected) return;
  if (!r || r.error) { body.innerHTML = refusalCard(r, { title: 'NOT YET' }); return; }
  const roll = r.roll_call || {};
  const send = r.send_off || {};
  const st = r.state || {};
  body.innerHTML = `
    <div class="frame" style="padding:16px;border-left:4px solid var(--orange)">
      <div class="pixel" style="font-size:13px;color:var(--gold-hi)">
        ${esc(r.title || '')}</div>
      <p class="small muted">${esc((r.room || {}).name || '')} —
        ${esc((r.room || {}).where || '')}</p>
      <p class="small">${esc((r.room || {}).law || '')}</p>
      <p class="small muted">${(r.acts || []).length} act(s),
        ${(r.beats || []).length} beat(s), ${Math.round(num(r.duration_ms) / 1000)}s,
        the freeze at ${(num(r.freeze_at_ms) / 1000).toFixed(1)}s.</p>
    </div>
    <div class="frame" style="padding:16px;margin-top:12px">
      <div class="section-title" style="margin-top:0">WHO IS BEHIND YOU</div>
      <p class="small">${esc(roll.ribbon || '')}</p>
      <p class="small muted">${esc(roll.narration || '')}</p>
      <p class="small">${num(roll.count)} of ${num(roll.total)} freed —
        ${esc(roll.scale_label || '')}.</p>
    </div>
    <div class="frame" style="padding:16px;margin-top:12px">
      <div class="section-title" style="margin-top:0">${esc(send.headline || '')}</div>
      ${lines(send.lines).map(l => `<p class="small">${esc(l)}</p>`).join('')}
      <p class="small muted">${esc(send.honest || '')}</p>
    </div>
    <p class="small muted" style="margin-top:12px">${esc(r.changes_nothing || '')}</p>
    <p class="small muted">Played ${num(st.plays)} time(s).
      ${st.coda_seen ? 'You have seen the second half.'
        : 'The second half — the part after the title card — has not been watched.'}</p>
    <div class="actions"><button class="btn primary" id="fin-play">PLAY IT</button></div>`;
  const go = $('#fin-play');
  if (go) go.onclick = () => { SCENE = r; CODA_SENT = false; SHOWN = -1; mount(); };
}

/* ------------------------------------------------------------- the stage */

function mount() {
  stop();
  ensureStyle();
  LAYER = el('div', 'fin-layer');
  LAYER.innerHTML = `
    <div class="fin-stage">
      <div class="fin-note" id="fin-note"></div>
      <div class="fin-lines" id="fin-lines"></div>
      <div class="fin-card" id="fin-card"></div>
      <div class="fin-rail" id="fin-rail"></div>
    </div>
    <div class="fin-bar">
      <span class="fin-act" id="fin-act"></span>
      <span class="fin-prog"><i id="fin-prog"></i></span>
      <button class="btn small" id="fin-skip">SKIP</button>
    </div>`;
  document.body.appendChild(LAYER);
  D.keep(() => { if (LAYER && LAYER.isConnected) LAYER.remove(); LAYER = null; });

  const skip = $('#fin-skip', LAYER);
  if (skip) skip.onclick = () => finish(true);
  const esckey = (e) => { if (e.key === 'Escape') finish(true); };
  D.onWindow('keydown', esckey);

  T0 = performance.now();
  PAUSED = false;
  try { audio.play('final'); } catch (e) { /* muted is fine */ }
  D.frames(LAYER, tick);
}

function tick() {
  if (!SCENE || !LAYER || PAUSED) return;
  const t = performance.now() - T0;
  const beats = SCENE.beats || [];
  const total = Math.max(1, num(SCENE.duration_ms, 1));

  const bar = $('#fin-prog', LAYER);
  if (bar) bar.style.width = `${Math.min(100, (t / total) * 100)}%`;

  let idx = -1;
  for (let i = 0; i < beats.length; i++) {
    if (t >= num(beats[i].at_ms)) idx = i; else break;
  }
  if (idx < 0) return;
  if (idx !== SHOWN) {
    SHOWN = idx;
    showBeat(beats[idx]);
  }
  if (t >= total) finish(false);
}

function showBeat(beat) {
  if (!LAYER) return;
  const act = $('#fin-act', LAYER);
  if (act) act.textContent = beat.act || '';

  /* `fx` is a list of names a renderer may honour. Three of them change what is
   * on screen rather than decorating it, so those three are read and the rest
   * are left to whoever draws this properly one day. */
  const fx = beat.fx || [];
  LAYER.classList.toggle('letterbox', fx.indexOf('letterbox') >= 0);
  LAYER.classList.toggle('blowout', fx.indexOf('palette_blowout') >= 0);
  LAYER.classList.toggle('cursor', fx.indexOf('cursor_blink') >= 0);

  const note = $('#fin-note', LAYER);
  if (note) note.textContent = beat.note || '';

  const host = $('#fin-lines', LAYER);
  if (host) {
    host.innerHTML = lines(beat.lines).map(l => `
      <div class="fin-line ${esc(l.kind || 'prose')}">
        ${l.name ? `<span class="fin-who">${esc(l.name)}</span>` : ''}
        <span class="fin-text">${esc(l.text)}</span></div>`).join('');
  }

  /* The title card slams in on the freeze and comes off again at `unfreeze` —
   * finale.py lists `title_card` on exactly three beats and stops, and the
   * point of the second half is that the frame starts moving again. A card left
   * up over it is the scene ending at the title, which is the half of this
   * ending a player is supposed to stay past. */
  if (fx.indexOf('title_card') >= 0) showCard(); else hideCard();
  if ((beat.sfx || []).indexOf('finale_hit') >= 0 || fx.indexOf('guitar_hit') >= 0) {
    try { audio.sfx('crit'); } catch (e) { /* no context yet */ }
  }
  /* finale.py says `cut`, and it means cut — the guitar hit is the only sound
   * in the room on the freeze frame. Stopping is not the same as playing
   * nothing: play(undefined) falls through to the overworld track. */
  if (beat.music === 'cut') { try { audio.stop(); } catch (e) { /* ignore */ } }
  else if (beat.music) { try { audio.play(beat.music); } catch (e) { /* ignore */ } }

  /* The name rail: everyone who walked out, scrolling past. `pullback` is the
   * roll call's own number for how far the camera has to go to fit them. */
  if ((beat.rows || []).length) showRail(beat.rows);

  /* THE CODA. Fires on `the_prompt_stays` and on nothing else. */
  if (beat.id === 'the_prompt_stays' && !CODA_SENT) {
    CODA_SENT = true;
    api.markCodaSeen().catch(() => { /* bookkeeping, not a gate */ });
  }
}

function hideCard() {
  const host = LAYER && $('#fin-card', LAYER);
  if (!host || !host.dataset.up) return;
  delete host.dataset.up;
  host.classList.remove('slam');
  host.innerHTML = '';
}

function showCard() {
  const host = $('#fin-card', LAYER);
  if (!host || host.dataset.up) return;
  host.dataset.up = '1';
  const c = (SCENE || {}).title_card || {};
  const style = c.style || {};
  /* THE BEVEL IS A STACK OF SHADOWS, not a filter. finale.py asks for a chrome
   * bevel of `bevel_steps` faces, an outline and a hard drop shadow at a named
   * offset — which is exactly what a column of offset text-shadows in the
   * given face colours draws, and it stays crisp at any text scale because
   * nothing is being blurred.
   *
   * `paint-order: stroke fill` matters more than it looks: without it the
   * three-pixel outline is painted OVER the letterform and eats a small pixel
   * face alive, which is what the first version of this did. */
  const faces = style.faces || ['#f2ead8'];
  const steps = Math.max(1, Math.min(8, num(style.bevel_steps, 4)));
  const drop = style.drop_shadow || {};
  const bevel = [];
  for (let i = 1; i <= steps; i++) {
    bevel.push(`0 ${i}px 0 ${faces[Math.min(i, faces.length - 1)]}`);
  }
  bevel.push(`${num(drop.dx, 6)}px ${num(drop.dy, 8)}px 0 ${drop.colour || '#0a0a0c'}`);
  host.innerHTML = `
    <div class="fin-eyebrow">${esc(c.eyebrow || '')}</div>
    <div class="fin-slab" style="color:${esc(faces[0])};
      text-shadow:${esc(bevel.join(','))};
      -webkit-text-stroke:3px ${esc(style.outline || '#0a0a0c')};
      paint-order:stroke fill">
      ${esc(c.slab || '')}</div>
    <div class="fin-shout" style="color:${esc(style.rim || '#ff8a2b')}">
      ${esc(c.shout || '')}</div>
    <div class="fin-ribbon">${esc(c.ribbon || '')}</div>
    <div class="fin-stinger">${esc(c.stinger || '')}</div>`;
  host.style.setProperty('--slam', `${num(style.slam_ms, 90)}ms`);
  host.style.setProperty('--over', String(num(style.overshoot, 1.08)));
  host.classList.add('slam');
}

function showRail(rows) {
  const rail = $('#fin-rail', LAYER);
  if (!rail) return;
  rail.innerHTML = rows.slice(0, 40).map(r =>
    `<span class="fin-name">${esc(r.name || r)}</span>`).join('');
}

function finish(skipped) {
  /* Skipping is allowed and is not punished. `skippable` is false on the freeze
   * and the coda in finale.py's own script, but a player holding Escape has
   * asked to leave and a scene that refuses is a scene holding somebody
   * hostage. What skipping does NOT do is mark the coda seen. */
  stop();
  D.leave();
  if (!skipped) HOST.sfx('unlock');
  HOST.back();
}

function stop() {
  PAUSED = true;
  if (LAYER && LAYER.isConnected) LAYER.remove();
  LAYER = null;
}

/* ---------------------------------------------------------------- styling
 *
 * In here rather than in game.css for the same reason fx.js and incantui.js do
 * it: one screen owns these nodes and nothing else in the game has an opinion
 * about a letterboxed freeze frame. */
function ensureStyle() {
  if (document.getElementById('finale-style')) return;
  const node = document.createElement('style');
  node.id = 'finale-style';
  node.textContent = `
.fin-layer {
  position: fixed; inset: 0; z-index: 120; background: #07070a;
  display: flex; flex-direction: column; color: var(--ink);
}
.fin-layer.blowout { background: #0a0a0c; }
.fin-layer.letterbox::before, .fin-layer.letterbox::after {
  content: ''; position: absolute; left: 0; right: 0; height: 11vh;
  background: #000; z-index: 3; pointer-events: none;
}
.fin-layer.letterbox::before { top: 0; }
.fin-layer.letterbox::after { bottom: 0; }
.fin-stage {
  flex: 1; position: relative; display: flex; flex-direction: column;
  justify-content: flex-end; padding: 6vh 8vw 4vh; overflow: hidden;
}
.fin-note {
  position: absolute; top: 6vh; left: 8vw; right: 8vw;
  font-size: calc(11px * var(--scale)); color: #4a4658; font-style: italic;
  line-height: 1.6; max-width: 60ch;
}
.fin-lines { position: relative; z-index: 2; max-width: 78ch; }
.fin-line { margin: 10px 0; font-size: calc(14px * var(--scale)); line-height: 1.75; }
.fin-line.prose { color: #cfcbdd; }
.fin-line.stage { color: #8f98a6; font-style: italic; }
.fin-line.code {
  font-family: 'Courier New', monospace; color: #8fd07a;
  font-size: calc(18px * var(--scale));
}
.fin-who {
  display: block; font-family: 'Press Start 2P', monospace;
  font-size: calc(9px * var(--scale)); color: var(--gold); margin-bottom: 6px;
}
.fin-layer.cursor .fin-line.code::after {
  content: '_'; animation: fincur .53s steps(2) infinite; color: #8fd07a;
}
@keyframes fincur { 0%,49% { opacity: 1 } 50%,100% { opacity: 0 } }
.fin-card {
  position: absolute; inset: 0; z-index: 4; display: none;
  flex-direction: column; align-items: center; justify-content: center;
  text-align: center; gap: 12px; pointer-events: none;
}
.fin-card.slam { display: flex; animation: finslam var(--slam,90ms) steps(3) 1; }
@keyframes finslam {
  from { transform: scale(var(--over,1.08)); opacity: 0 }
  to { transform: scale(1); opacity: 1 }
}
.fin-eyebrow {
  font-family: 'Press Start 2P', monospace; font-size: calc(10px * var(--scale));
  color: #8f98a6; letter-spacing: 3px;
}
.fin-slab {
  font-family: 'Press Start 2P', monospace;
  font-size: calc(26px * var(--scale)); line-height: 1.35; max-width: 22ch;
}
.fin-shout {
  font-family: 'Press Start 2P', monospace; font-size: calc(13px * var(--scale));
  letter-spacing: 2px;
}
.fin-ribbon {
  font-family: 'Press Start 2P', monospace; font-size: calc(9px * var(--scale));
  color: #f2ead8; background: #4a5260; padding: 5px 14px;
}
.fin-stinger {
  font-size: calc(10px * var(--scale)); color: #6a6685; letter-spacing: 2px;
}
.fin-rail {
  position: absolute; bottom: 2vh; left: 0; right: 0; z-index: 2;
  display: flex; gap: 18px; flex-wrap: wrap; justify-content: center;
  padding: 0 8vw; opacity: .75;
}
.fin-name {
  font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: #8fd07a;
}
.fin-bar {
  flex: 0 0 auto; display: flex; align-items: center; gap: 12px;
  padding: 8px 16px; background: #0b0a12; border-top: 2px solid var(--line);
  z-index: 5;
}
.fin-act {
  font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: var(--violet); flex: 0 0 auto;
}
.fin-prog { flex: 1; height: 4px; background: #171426; display: block; }
.fin-prog > i { display: block; height: 100%; width: 0; background: var(--gold); }
`;
  document.head.appendChild(node);
}
