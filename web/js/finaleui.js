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
 * `the_prompt_stays` (pass) / `the_prompt_waits` (rematch) are the final beat. A
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
import { createCinema } from './cinema.js';

export const FINALE_UI_VERSION = '2.0.0';

const D = makeDisposer();
export const leave = () => { FINISHED = true; DONE = null; stop(); D.leave(); };

let SCENE = null;
let LAYER = null;
let CLOCK = null;
let DONE = null;
let FINISHED = true;
let RUN = 0;
let CINEMA = null;
let PRESENTATION = {};


/** Pure scene clock. A stopped/cancelled clock cannot emit completion twice.
 * Pausing consumes wall time without moving the script or repeating a beat. */
export function createSceneClock(scene, { startAt = 0, onBeat = () => {}, onFrame = () => {},
  onCoda = () => {}, onDone = () => {} } = {}) {
  const beats = scene.beats || [], total = Math.max(1, num(scene.duration_ms, 1));
  let held = null, pausedFor = 0, shown = -1, coda = false, closed = false;
  const elapsed = now => Math.max(0, (held ?? now) - startAt - pausedFor);
  function stop(skipped = true) {
    if (closed) return;
    closed = true;
    onDone(skipped);
  }
  return {
    step(now) {
      if (closed) return;
      const ms = elapsed(now);
      let index = -1;
      for (let i = 0; i < beats.length; i++) {
        if (ms >= num(beats[i].at_ms)) index = i; else break;
      }
      if (index >= 0 && index !== shown) {
        shown = index;
        onBeat(beats[index]);
        if (!coda && ['the_prompt_stays', 'the_prompt_waits'].includes(beats[index].id)) {
          coda = true;
          onCoda();
        }
      }
      onFrame(ms, index);
      if (ms >= total) stop(false);
    },
    togglePause(now) {
      if (closed) return false;
      if (held === null) held = now;
      else { pausedFor += now - held; held = null; }
      return held !== null;
    },
    stop,
    cancel() { closed = true; },
    get paused() { return held !== null; },
    get closed() { return closed; },
  };
}

/* -------------------------------------------------------------- the door */

/* Staged AFTER the practical is scored and never before. The exam report the
 * player was just handed is passed straight through — this file does not read
 * it, finale.py does. */
export async function play(examReport, presentation = {}) {
  const r = await api.finale(examReport || {}).catch(e => ({ error: e.message }));
  if (!r || r.error) {
    HOST.toast(isSealed(r) ? sealedTitle(r) : 'NOT YET', refusal(r), 'red');
    return null;
  }
  playScene(r, presentation);
  return r;
}

/** Play an already-authorized ending payload. Both staged outcomes and the
 * standalone finale share this player. The gallery uses createCinema directly;
 * demonstration payloads additionally suppress coda bookkeeping here. */
export function playScene(scene, presentation = {}, done = null) {
  leave();
  const run = ++RUN;
  SCENE = scene;
  PRESENTATION = presentation;
  DONE = typeof done === 'function' ? done : null;
  FINISHED = false;
  const session = {
    stop() { if (run === RUN && !FINISHED) { if (CLOCK) CLOCK.stop(true); else finish(true); } },
    get active() { return run === RUN && !FINISHED; },
  };
  if (!scene || !(scene.beats || []).length) { finish(true); return session; }
  mount();
  return session;
}

/* The read-only version: what the scene WOULD be, as a page. Reachable from the
 * ledger so a player can find out there is one without finishing the game. */
export async function paintFinaleCard() {
  leave();
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
  if (go) go.onclick = () => playScene(r);
}

/* ------------------------------------------------------------- the stage */

function mount() {
  stop();
  D.leave();
  ensureStyle();
  LAYER = el('div', 'fin-layer');
  LAYER.setAttribute('role', 'dialog');
  LAYER.setAttribute('aria-modal', 'true');
  LAYER.setAttribute('aria-label', SCENE.title || 'The last scene');
  LAYER.innerHTML = `
    <div class="fin-stage">
      <canvas class="fin-art" id="fin-art" width="960" height="540" aria-hidden="true"></canvas>
      <div class="fin-lines" id="fin-lines" tabindex="0" aria-label="Scene dialogue"></div>
      <div class="fin-card" id="fin-card"></div>
      <div class="fin-rail" id="fin-rail"></div>
    </div>
    <div class="fin-bar">
      <span class="fin-act" id="fin-act"></span>
      <span class="fin-prog"><i id="fin-prog"></i></span>
      <button class="btn small" id="fin-pause" aria-pressed="false">PAUSE</button>
      <button class="btn small" id="fin-skip">SKIP</button>
    </div>`;
  document.body.appendChild(LAYER);
  const reducedMotion = PRESENTATION.reducedMotion ?? document.body.classList.contains('reduced-motion');
  LAYER.classList.toggle('fin-reduced', !!reducedMotion);
  CINEMA = createCinema(SCENE, { ...PRESENTATION, reducedMotion });
  const pause = $('#fin-pause', LAYER);
  if (pause) pause.onclick = () => {
    if (!CLOCK) return;
    const held = CLOCK.togglePause(performance.now());
    pause.textContent = held ? 'RESUME' : 'PAUSE';
    pause.setAttribute('aria-pressed', String(held));
  };
  D.keep(() => { if (LAYER && LAYER.isConnected) LAYER.remove(); LAYER = null; });

  const skip = $('#fin-skip', LAYER);
  if (skip) skip.onclick = () => CLOCK?.stop(true);
  const esckey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); CLOCK?.stop(true); }
    if (e.key === 'Tab' && LAYER) {
      const dialogue = $('#fin-lines', LAYER);
      const controls = [dialogue && dialogue.innerHTML.trim() ? dialogue : null, pause, skip].filter(Boolean);
      const first = controls[0], last = controls[controls.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  D.onWindow('keydown', esckey);

  CLOCK = createSceneClock(SCENE, {
    startAt: performance.now(),
    onBeat: showBeat,
    onFrame: tick,
    onCoda: () => {
      if (!SCENE.demonstration) api.markCodaSeen().catch(() => { /* bookkeeping, never a gate */ });
    },
    onDone: finish,
  });
  // The first beat owns the soundtrack. scene.music is a list of tracks, not
  // a playable key; do not start an unrelated fallback before the first cut.
  CLOCK.step(performance.now());
  D.frames(LAYER, () => {
    try { CLOCK?.step(performance.now()); }
    catch (error) {
      // A drawing failure must release the overlay and return the report.
      finish(true);
      HOST.toast('SCENE INTERRUPTED', error.message || String(error), 'red');
    }
  });
  if (skip) skip.focus();
}

function tick(t) {
  if (!SCENE || !LAYER) return;
  const total = Math.max(1, num(SCENE.duration_ms, 1));
  const bar = $('#fin-prog', LAYER);
  if (bar) bar.style.width = `${Math.min(100, (t / total) * 100)}%`;
  const art = $('#fin-art', LAYER);
  if (art && CINEMA) {
    const frame = CINEMA.draw(art.getContext('2d'), art.width, art.height, t);
    const rail = $('#fin-rail', LAYER);
    if (rail && frame && rail.dataset.current !== String(frame.castIndex)) {
      rail.dataset.current = String(frame.castIndex);
      Array.from(rail.children).forEach((node, i) => {
        node.classList.toggle('current', i === frame.castIndex);
        if (i === frame.castIndex) node.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      });
    }
  }
}

function showBeat(beat) {
  if (!LAYER) return;
  const act = $('#fin-act', LAYER);
  if (act) act.textContent = beat.act || '';

  /* The canvas renders the complete stage/camera vocabulary. DOM text stays
   * outside its pixel effects so dialogue remains readable. */
  const fx = beat.fx || [];
  LAYER.classList.toggle('letterbox', fx.indexOf('letterbox') >= 0);
  LAYER.classList.toggle('blowout', fx.indexOf('palette_blowout') >= 0);
  LAYER.classList.toggle('cursor', fx.indexOf('cursor_blink') >= 0);
  LAYER.classList.toggle('has-card', fx.includes('title_card'));
  LAYER.classList.toggle('black-stage', (beat.stage || []).includes('black'));

  const host = $('#fin-lines', LAYER);
  if (host) {
    host.scrollTop = 0;
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
  showRail(beat.rows || []);


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
  delete rail.dataset.current;
  rail.innerHTML = rows.map(r =>
    `<span class="fin-name">${esc(r.name || r)}</span>`).join('');
}

function finish(skipped) {
  if (FINISHED) return;
  FINISHED = true;
  const done = DONE;
  DONE = null;
  stop();
  D.leave();
  // Staged endings return to their exact report. Standalone playback keeps its
  // existing return route. Neither dismissal path grants learning evidence.
  if (done) done({ skipped: !!skipped });
  else {
    if (!skipped) HOST.sfx('unlock');
    HOST.back();
  }
}

function stop() {
  if (CLOCK) CLOCK.cancel();
  CLOCK = null;
  if (CINEMA) CINEMA.dispose();
  CINEMA = null;
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
  position: fixed; inset: 0; z-index: 9000; background: #07070a;
  display: flex; flex-direction: column; color: var(--ink,#e6e4dc); --scale: 1;
}
.fin-layer.blowout { background: #0a0a0c; }
.fin-layer.letterbox .fin-stage::before, .fin-layer.letterbox .fin-stage::after {
  content: ''; position: absolute; left: 0; right: 0; height: 3vh;
  background: #000; z-index: 3; pointer-events: none;
}
.fin-layer.letterbox .fin-stage::before { top: 0; }
.fin-layer.letterbox .fin-stage::after { bottom: 0; }
.fin-stage {
  flex: 1; position: relative; display: grid; grid-template-rows: minmax(0,1fr) auto auto;
  padding: 0 3vw 12px; overflow: hidden; min-height: 0;
}
.fin-art { grid-row: 1; width: 100%; height: 100%; min-height: 0; object-fit: contain; image-rendering: pixelated; }
.fin-lines { grid-row: 2; position: relative; z-index: 4; width: min(88ch,100%); max-height: 25vh; overflow-y: auto;
  margin: 0 auto; padding: 8px 18px; border-left: 2px solid #9d7b59;
  background: #0b1220ed; box-shadow: 0 3px 0 #050a12; }
.fin-lines:empty { display: none; }
.fin-lines:focus-visible { outline: 2px solid #d2ae79; outline-offset: 2px; }
.fin-layer.black-stage .fin-lines { grid-row: 1; align-self: center; margin: auto; text-align: center; background: none; border: 0; box-shadow: none; }
.fin-layer.black-stage .fin-art { display: none; }
.fin-line { margin: 8px 0; font-size: calc(16px * var(--scale)); line-height: 1.6; text-shadow: none; }
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
  position: absolute; inset: 4vh 3vw auto; min-height: 43%; z-index: 3; display: none;
  flex-direction: column; align-items: center; justify-content: center;
  text-align: center; gap: 12px; padding: 12px 0; pointer-events: none; background: #080d165c;
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
  font-size: calc(10px * var(--scale)); color: #b7a8a1; letter-spacing: 2px;
}
.fin-rail {
  grid-row: 3; z-index: 2; max-height: 8vh; overflow-y: auto;
  display: flex; gap: 18px; flex-wrap: wrap; justify-content: center;
  padding: 0 8vw; opacity: .75;
}
.fin-rail:empty { display: none; }
.fin-name.current { color: #f2d6a6; text-decoration: underline; text-underline-offset: 4px; }
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
.fin-reduced .fin-card.slam, .fin-reduced.cursor .fin-line.code::after { animation: none; }
@media (max-width: 650px) {
  .fin-bar { flex-wrap: wrap; gap: 8px; }
  .fin-act { font-size: 7px; flex-basis: 100%; }
  .fin-lines { max-height: 34vh; padding: 6px 12px; }
  .fin-slab { font-size: calc(15px * var(--scale)); }
  .fin-shout { font-size: calc(10px * var(--scale)); }
  .fin-eyebrow, .fin-stinger { font-size: 8px; }
  .fin-card { gap: 8px; min-height: 32%; }
}
`;
  document.head.appendChild(node);
}
