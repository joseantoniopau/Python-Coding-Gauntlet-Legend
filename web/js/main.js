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
import { RepoUI } from './repoui.js';
import { Overworld } from './overworld.js';
import { Visualiser, hasViz } from './viz.js';
import { WorldUI } from './worldui.js';
import * as partyui from './partyui.js';
/* The ten systems that had no door. Each one owns its own screens, its own
 * styling and its own timers, and borrows this file's chrome through uikit's
 * HOST — the same bargain partyui.js already makes. */
import * as uikit from './uikit.js';
import * as townui from './townui.js';
import * as huntui from './huntui.js';
import * as deathfx from './deathfx.js';
import { Transformation } from './transform.js';
import * as spellfx from './spellfx.js';
import * as legendui from './legendui.js';
import * as finaleui from './finaleui.js';

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
  // The wheel: elements, statuses, hazards, boots, region affinities and the
  // potion catalogue, fetched once from /api/wheel. Static for the life of the
  // server, and the ONLY copy of any of it on this side — a status's duration
  // with two homes is a tooltip that eventually disagrees with the fight.
  wheel: null,
  // The last thing the combat HUD was told. Kept so drinking a potion can
  // repaint the strip without refetching an encounter.
  hud: null,
  // { region, data } — one region's affinity, hazard and what a step across it
  // costs in the boots actually on the player's feet. Cached because the
  // overworld repaints its side panel far more often than the ground changes.
  regionElement: null,
  // The live IncantationUI. It owns #puzzle-host while it exists, which is why
  // every path that wants that node destroys this first.
  incant: null,
  incantRun: null,
  incantCards: [],
  // The worldui/partyui instance currently mounted in #panel-body.
  child: null,
  // The live Mini-Repo. It owns #repo-host and a clock, which is why every
  // path that leaves the fight destroys it first.
  repo: null,
  repoPayload: null,
  // Whether the NEXT repository is opened measured. Off by default: Adventure
  // Mode teaches, and this is the switch that says "not this time".
  repoMeasured: false,
  // -- the low-health alarm ------------------------------------------------
  // upkeep.alarm() as the SERVER last sent it, and nothing else. Every graded
  // submission carries one; so do heal(), rest() and the town square. This
  // client never works one out for itself — a threshold with two homes is a
  // sprite that flashes at one health and a heartbeat that starts at another.
  // The choices of an MCQ encounter, which ARE the encounter. See renderMcq.
  mcq: null,
  alarm: null,
  alarmNode: null,     // the red wash over the hero, while it is up
  alarmBeat: null,     // the heartbeat interval, at upkeep's own BPM
  alarmBand: '',       // latched: the band the player has already been TOLD
  // The region the player is standing in as far as the hunt is concerned, so a
  // fight's casts are only counted against the apex of the place they happened.
  huntRegion: '',
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
  // A modal owns the screen. Anything typed at it while the editor still holds
  // the caret goes into the player's code instead, unseen.
  releaseEditor();
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
  focusEditor();
}

$('#modal-bg').addEventListener('click', (e) => {
  if (e.target.id !== 'modal-bg') return;
  // A locked modal is mid-chain and owns the screen; it supplies its own exit.
  if (G.modalLocked) return;
  closeModal();
});

/* THE SPEAKER'S FACE, AND THE EMOTE AXIS IT NEVER USED.
 *
 * sprites.js carries portraitEmote / portraitFrames / portraitSet / portraitAt
 * — seven emotes, two frames each, on a 24-pixel face — and every one of them
 * had ZERO call sites. This box drew sprites.portrait(kind), a separate 12x12
 * head with no emote axis at all, so the whole portrait system was unreachable
 * from the shipped game.
 *
 * portraitAt(kind, emote, t) is the same call with two more arguments, and the
 * story entries already carry a `kind` per line. Anything that does not name an
 * emote lands on neutral, which is what the old call drew.
 *
 * The clock advances one step per LINE rather than on a timer: a portrait that
 * blinks while the player reads needs an interval, and an interval started here
 * is an interval to leak. One step per line is enough to make the second frame
 * exist. */
const PORTRAIT_STEP_MS = 900;

function paintPortrait(kind, emote, step) {
  const pc = $('#dialogue-portrait');
  if (!pc) return null;
  let img = null;
  try { img = sprites.portraitAt(kind || 'scholar', emote || 'neutral', step * PORTRAIT_STEP_MS); }
  catch (e) { img = null; }
  // A face this box has never been able to draw is still better than no box.
  if (!img) { try { img = sprites.portrait(kind || 'scholar'); } catch (e2) { return null; } }
  pc.width = img.width; pc.height = img.height;
  pc.getContext('2d').drawImage(img, 0, 0);
  return img;
}

function say(who, lines, portraitKind, emote) {
  G.dialogueQueue = Array.isArray(lines) ? lines.slice() : [lines];
  const box = $('#dialogue');
  G.dialogueFace = { kind: portraitKind || 'scholar', emote: emote || 'neutral', step: 0 };
  paintPortrait(G.dialogueFace.kind, G.dialogueFace.emote, 0);
  $('#dialogue-who').textContent = who;
  box.classList.add('show');
  // SPACE advances the dialogue, and the global key handler stands down for a
  // focused textarea. With the caret still in the editor a boss taunt is
  // unadvanceable by keyboard and every attempt lands in the player's code.
  releaseEditor();
  advanceDialogue();
}

function advanceDialogue() {
  const next = G.dialogueQueue.shift();
  if (next !== undefined && G.dialogueFace) {
    G.dialogueFace.step++;
    paintPortrait(G.dialogueFace.kind, G.dialogueFace.emote, G.dialogueFace.step);
  }
  if (next === undefined) {
    $('#dialogue').classList.remove('show');
    if (G.storyQueue && G.storyQueue.length) { setTimeout(playStoryQueue, 120); return; }
    // Nobody is talking any more: the caret goes back to the editor, which is
    // where the player was about to need it. focusEditor waits out the tail of
    // the player's SPACE taps before it does.
    focusEditor();
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

/* ======================================================================
 * WHERE TO TYPE, AND WHO HOLDS THE CARET
 * ======================================================================
 *
 * Two reports, one cause. "I can't tell where to type" is what an unlabelled
 * black rectangle in the bottom-left corner looks like, and the caret was gold
 * on gold. The caption above the editor, the ring the editor grows when it has
 * the caret and the placeholder inside an empty one are the answer, and this
 * is the switch that puts them up — and, on an encounter that has no editor,
 * takes them down and says where the answer goes instead. A "TYPE HERE"
 * pointing at nothing is worse than no label at all.
 *
 *   code    the editor, its caption and the CAST button
 *   puzzle  #puzzle-host; CAST still submits, so no caption and no pointer
 *   mcq     nothing to type: the answers are the TRIALS list, so say so
 *   incant  IncantationUI owns the pane and carries its own cast control
 */
function setEditorMode(mode, verb = 'CAST ✦') {
  const caption = $('#editor-caption');
  const answer = $('#answer-here');
  /* ONE STRING, TWO PLACES. The caption used to hard-code "CAST ✦" while
   * enterBattle relabelled the primary button to "FORGE ✦" on a TEST_FORGE
   * encounter — measured live on tf-sum-list: the caption read THEN PRESS
   * CAST ✦ while the toolbar read ["RUN ▶","FORGE ✦","RESET","RETREAT"]. The
   * one sentence that tells a new player what to press named a button that was
   * not on the screen. It is driven from the same string now. */
  const castName = caption && caption.querySelector('.ec-cast b');
  if (castName) castName.textContent = verb;
  if (caption) caption.style.display = mode === 'code' ? '' : 'none';
  if (answer) answer.style.display = mode === 'mcq' ? '' : 'none';
  const pane = $('#editor-pane');
  if (pane && mode !== 'code') pane.classList.remove('typing');
}

/* The caret belongs to the editor only when nothing is talking over it. A
 * modal and the dialogue box both own the screen while they are up, and the
 * global key handler stands down for a focused textarea — so a boss taunt with
 * the caret in the editor ate every SPACE the player pressed to advance it,
 * and typed spaces into their code instead. Hand the caret back when the thing
 * that took it is gone. */
function editorIsLive() {
  const host = $('#editor-host');
  return G.screen === 'battle' && !!G.editor && !!host && host.style.display !== 'none'
    && !$('#modal-bg').classList.contains('show')
    && !$('#dialogue').classList.contains('show');
}

/* Handing the caret back is DEBOUNCED against the keys the player is still
 * firing at the game chrome, and this is not fussiness. SPACE advances the
 * dialogue and people over-tap it; the taps that arrive after the last line is
 * gone would land in the editor, and because Editor.reset() leaves the
 * `__BLANK__` slot SELECTED, the first of them replaces the slot with a space.
 * So: hand it back once the player has stopped pressing, not on a fixed timer
 * that a fast hand outruns. */
const FOCUS_QUIET_MS = 280;

/* AND THE DEBOUNCE IS NOT ENOUGH ON ITS OWN, which is what measuring it showed:
 * it only protects against taps FASTER than its own window. At a normal human
 * cadence the caret is handed back BETWEEN taps and every tap after that one is
 * typed into the player's code. Measured on a boss taunt, eight SPACE presses:
 * at 55, 150 and 250 ms the buffer came out byte-identical; at 300, 400, 700
 * and 1500 ms seven stray spaces were appended, every run. On a starter with a
 * `__BLANK__` slot it was worse than untidy — the slot is SELECTED by
 * Editor.reset(), so `return prices[__BLANK__]` became `return prices[       ]`
 * and the marker was gone with no message.
 *
 * So two things that do not depend on timing at all:
 *
 *   (a) the selection is COLLAPSED on the way in, so a stray key can never
 *       delete what was selected — the destructive half, gone outright;
 *   (b) a capture-phase guard on the textarea swallows a BARE space or Enter
 *       for FOCUS_GUARD_MS, and every swallowed key pushes that window out
 *       again, because a key arriving in the window is evidence the player is
 *       still tapping at the chrome rather than typing. Anything else — a real
 *       character, a click, Ctrl+Enter — disarms it immediately, so the guard
 *       costs a deliberate typist nothing.
 *
 * The debounce stays as the first line of defence: it keeps the common case
 * from ever reaching the guard. */
/* 1200ms, and the number is measured rather than guessed. Eight SPACE presses
 * through a boss taunt, buffer diffed each time: 55, 150, 250, 300, 400 and
 * 700ms cadences all leak at 500ms and none of them leak at 1200. It is
 * refreshed by every key it swallows, because a key arriving inside the window
 * says the player is still tapping — so a burst of any length is covered, not
 * just the first two. A player who pauses longer than this and then presses
 * SPACE gets a space, and should: by then the caption is gold, the editor has
 * its ring and the caret is blinking in it. The two caps below are the other
 * side of that bargain — a guard is a thing that eats keys, so it is not
 * allowed to eat them forever if something goes wrong. */
const FOCUS_GUARD_MS = 1200;
const FOCUS_GUARD_LIFE_MS = 6000;   // never armed longer than this
const FOCUS_GUARD_MAX = 16;         // never eats more keys than this

function disarmFocusGuard() {
  if (!G.focusGuard) return;
  const { node, handler, click } = G.focusGuard;
  node.removeEventListener('keydown', handler, true);
  node.removeEventListener('mousedown', click, true);
  clearTimeout(G.focusGuardTimer);
  G.focusGuardTimer = null;
  G.focusGuard = null;
}

function armFocusGuard() {
  disarmFocusGuard();
  const node = G.editor && G.editor.input;
  if (!node) return;
  const armed = Date.now();
  let until = armed + FOCUS_GUARD_MS;
  let eaten = 0;
  const click = () => disarmFocusGuard();        // a click in the box is intent
  const handler = (e) => {
    const now = Date.now();
    if (now > until || now - armed > FOCUS_GUARD_LIFE_MS) { disarmFocusGuard(); return; }
    // Ctrl/⌘+Enter is RUN and CAST. It is not a stray tap and must get through.
    if (e.ctrlKey || e.metaKey || e.altKey) { disarmFocusGuard(); return; }
    // Anything the player actually typed is intent: stand down and let it land.
    if (e.key !== ' ' && e.key !== 'Enter') { disarmFocusGuard(); return; }
    e.preventDefault();
    e.stopPropagation();
    if (++eaten >= FOCUS_GUARD_MAX) { disarmFocusGuard(); return; }
    until = now + FOCUS_GUARD_MS;                 // still tapping: hold the door
    clearTimeout(G.focusGuardTimer);
    G.focusGuardTimer = setTimeout(disarmFocusGuard, FOCUS_GUARD_MS);
  };
  G.focusGuard = { node, handler, click };
  node.addEventListener('keydown', handler, true);
  node.addEventListener('mousedown', click, true);
  G.focusGuardTimer = setTimeout(disarmFocusGuard, FOCUS_GUARD_MS);
}

/* `keepSelection` is for the one focus that is not a hand-back: the first one
 * of a fresh encounter, where Editor.reset() has just selected the __BLANK__
 * slot on purpose so the first keystroke replaces it. Everything else — a
 * closing modal, a spent dialogue queue — is a hand-back and collapses.
 * `guard` is off for the RUN button, which hands the caret back mid-typing. */
function focusEditor({ keepSelection = false, guard = true } = {}) {
  clearTimeout(G.focusTimer);
  if (!editorIsLive()) return;
  if (Date.now() - (G.lastChromeKey || 0) < FOCUS_QUIET_MS) {
    G.focusTimer = setTimeout(() => focusEditor({ keepSelection, guard }), FOCUS_QUIET_MS);
    return;
  }
  G.editor.focus();
  if (!keepSelection && G.editor.collapseSelection) G.editor.collapseSelection();
  if (guard) armFocusGuard(); else disarmFocusGuard();
}

function releaseEditor() {
  disarmFocusGuard();
  const node = document.activeElement;
  if (node && node.classList && node.classList.contains('editor-input')) node.blur();
}

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
  } else if (screen === 'repo') {
    ensureRepoScreen().classList.add('active');
    G.overworld && G.overworld.stop();
  } else {
    $('#screen-panel').classList.add('active');
    G.overworld && G.overworld.stop();
  }
  // The alarm belongs to the battle screen and is drawn from here rather than
  // from enterBattle, because enterBattle paints the strip BEFORE it shows the
  // screen and a pulse that checks `G.screen` would have been asking the
  // question one line too early. Deferred once as well: the stage has no
  // geometry until the browser has laid the newly-shown screen out, and an
  // overlay positioned against a zero-size box is an overlay nobody sees.
  // The stage cannot be measured while the screen it lives on is display:none,
  // so the fit happens here rather than in enterBattle — and twice, because the
  // combat strip's own height is part of the budget and it has not been laid
  // out on the first pass. Before paintAlarm both times: the wash is positioned
  // in pixels against the stage, so it has to be told after the stage moves.
  if (screen === 'battle') fitBattleStage();
  paintAlarm();
  if (screen === 'battle') setTimeout(() => { fitBattleStage(); paintAlarm(); }, 60);
}

/* ======================================================================
 * HOW BIG THE FIGHT IS
 * ======================================================================
 *
 * THE CANVAS SCALES BY A WHOLE NUMBER OR NOT AT ALL. fx._resize() computes
 * `px = floor(min(canvas.width / 256, canvas.height / 176))` and draws the
 * 256x224 logical stage at that scale, centred, because a fractional scale is
 * what makes pixel art soft. Everything below follows from that one line. The
 * two divisors are different on purpose — 256 wide, but only the 176-line SAFE
 * AREA of the 224-line raster is fitted; see STAGE_LOGICAL below.
 *
 * The old box was a hard-coded 480x320. It is exactly 3:2, which sounds like it
 * should fit — and it drew at 2x, because 480/192 is 2.5 and the floor throws
 * the remainder away. Ninety-six by sixty-four device pixels of that frame were
 * letterbox: a fifth of the width and a fifth of the height, spent on nothing.
 * Aspect ratio is not the thing to aim at. The SCALE is.
 *
 * So: work out how much room the top band can have, ask what the largest whole
 * scale that fits is, and then size the box to THAT — art plus a gutter of a
 * few pixels, never a fifth of the frame. The gutter is deliberate: fx sizes
 * the canvas from the host's border box but the browser lays it out inside the
 * border, so a canvas sized to the art exactly would have its last column
 * clipped. GUTTER covers the border on both axes with a pixel to spare.
 *
 * The budget, in order of who gets to refuse:
 *   - the combat strip is measured, not guessed; it grows with statuses
 *   - #battle-main keeps MAIN_MIN so the editor never becomes a letterbox slot
 *   - the band asks for BAND of the screen and settles for what is left
 *   - the stage never takes more than WIDE of the width, so the brief has a
 *     column to be read in
 * devicePixelRatio is in it throughout: on a 2x display the same CSS box holds
 * twice the scale, which is the whole point of asking the canvas rather than
 * the stylesheet. */
/* THE RASTER AND THE PART OF IT WE PROMISE TO SHOW ARE TWO DIFFERENT NUMBERS.
 *
 * fx.js draws 256x224 — the SNES frame, docs/08-art-direction §A-1. This box
 * is fitted to `fitH`, the 176-line safe area, and NOT to the full 224.
 *
 * Why, measured (§A-3): a naive 256x224 fit drops 1280x800 from scale 2 to
 * scale 1 — the figure halves on screen — and at 1024x640 it leaves #battle-main
 * 167px, below the MAIN_MIN of 200 that keeps the editor from becoming a
 * letterbox slot. Buying scale 2 back at 1280x800 with all 224 lines needs
 * MAIN_MIN <= 159 and BAND >= 0.676: an editor about three code lines tall. The
 * editor is the half of this screen the game is actually about, so that price
 * is refused.
 *
 * Fitting 176 holds scale 2 at 1280x800 and keeps every window above the floor.
 * The 24 rows above and below the safe area are overscan — they still get drawn,
 * they just fall off the canvas, exactly as they fell off an NTSC tube. Nothing
 * the player must read is allowed to live there. */
const STAGE_LOGICAL = { w: 256, h: 224, fitH: 176 };

function fitBattleStage() {
  const stage = $('#battle-stage');
  const screen = $('#screen-battle');
  if (!stage || !screen) return;
  const sh = screen.clientHeight;
  const sw = screen.clientWidth;
  if (sh < 80 || sw < 80) return;   // not laid out yet

  // 0.62, and the exact number is load-bearing because THE SCALE IS AN
  // INTEGER. Measured at 1600x1000 with BAND 0.60: the height allowance came
  // to 510.8px against the 512 that scale 4 needs — short by ONE POINT TWO
  // PIXELS, so the whole stage rounded down a step and gave back 190px of
  // width it had room for. (The stage border is 6px, not the 4 I first
  // assumed, which is where the missing pixels went.)
  //
  // Measured across the sizes this actually opens at, 0.62 changes exactly
  // one of them and breaks none:
  //   1280x800   scale 2, editor 305px   (bandMax binds; unchanged)
  //   1440x940   scale 3, editor 297px   (bandMax binds; unchanged)
  //   1600x1000  scale 3 -> 4, editor 229px
  //   1920x1080  scale 4, editor 309px   (unchanged)
  // Anything past this has to come out of MAIN_MIN, and the editor is the half
  // of this screen the game is actually about.
  const BAND = 0.62;        // of the battle screen, before anything refuses
  /* 200 UNTIL THE RASTER MOVED, AND THE EIGHT PIXELS IT COST.
   *
   * At 1280x800 the fight screen is 753px tall and #combat-hud measures 148 —
   * not the 116 docs/08 §A-4 measured, because at this width the belt line in
   * the HUD wraps to a second row. That makes bandMax the binding constraint
   * rather than BAND:
   *   bandMax = 753 - 148 - 200 = 405
   *   artMaxH = 405 - 47 - 6 - 8 = 344,  344 / 176 = 1.955
   * One point nine five five. Scale 2 needs 352, so the whole stage rounded
   * down a step and the figure halved — the exact failure the safe area exists
   * to prevent, missed by eight pixels.
   *
   * 184 is the smallest move that clears it: bandMax = 421, artMaxH = 360,
   * 360 / 176 = 2.045, and #battle-main lands on 192 — which is the outcome
   * §A-5's own table predicts for this window (its "ed 208" is the same
   * quantity measured one node out). Driven live at all six sizes, 184 changes
   * exactly one of them and breaks none: 1024x640, 1440x940, 1600x1000,
   * 1920x1080 and 2560x1440 are all still limited by BAND or by the width, and
   * none of them comes within 20px of this floor.
   *
   * WHAT IT COSTS, IN CODE LINES, MEASURED. #editor-pane's shell driven live at
   * default text scale, before the raster move and after:
   *   1024x640    87px -> 63px    about 4 lines -> 3
   *   1280x800   105px -> 57px    about 5 lines -> 3
   *   1440x940   119px -> 135px   about 6 lines -> 7   (the launcher window)
   *   1600x1000   85px -> 77px    about 4 lines -> 4
   * The launcher window GAINS a line, because its stage dropped from scale 3 in
   * a 398-tall box to scale 2 in a 366-tall one. The loss is concentrated at
   * 1280x800, and it is the price §A-5 already quotes there ("ed 208"). If that
   * price is ever judged wrong, this is the one constant that buys it back: at
   * 200 that window returns to scale 1 — a 96-pixel figure instead of a
   * 192-pixel one — and the editor goes to about twelve lines. It is a single
   * number, and it is a real choice, not an oversight. */
  const MAIN_MIN = 184;     // the editor and the side tabs keep this much
  const WIDE = 0.52;        // the stage's share of the width
  const GUTTER = 8;         // slack so the border cannot clip the last column

  const dpr = Math.min(3, window.devicePixelRatio || 1);
  const cs = getComputedStyle(stage);
  const bw = (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.borderRightWidth) || 0);
  const bh = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);

  // Everything in #battle-top that is not the stage: the strip under it, the
  // gap above the strip, the band's own padding and its bottom rule.
  const top = $('#battle-top');
  const strip = $('#enemy-strip');
  const tcs = top ? getComputedStyle(top) : null;
  const chromeV = (strip ? strip.offsetHeight + 6 : 24)
    + (tcs ? (parseFloat(tcs.paddingTop) || 0) + (parseFloat(tcs.paddingBottom) || 0)
           + (parseFloat(tcs.borderBottomWidth) || 0) : 23);
  const chromeH = tcs ? (parseFloat(tcs.paddingLeft) || 0) + (parseFloat(tcs.paddingRight) || 0)
                      : 28;

  const hudNode = $('#combat-hud');
  const hudH = hudNode && hudNode.classList.contains('on') ? hudNode.offsetHeight : 0;

  const bandMax = Math.max(140, sh - hudH - MAIN_MIN);
  const band = Math.min(sh * BAND, bandMax);
  // fitH, not h. See the note on STAGE_LOGICAL: the box holds the safe area and
  // the overscan hangs off it. fx.js _resize() fits the same number, so the two
  // agree on the scale without either importing the other's box.
  const fitH = STAGE_LOGICAL.fitH || STAGE_LOGICAL.h;
  const artMaxH = Math.max(fitH, (band - chromeV - bh - GUTTER) * dpr);
  const artMaxW = Math.max(STAGE_LOGICAL.w, (sw * WIDE - chromeH - bw - GUTTER) * dpr);

  const px = Math.max(1, Math.floor(Math.min(artMaxH / fitH,
                                             artMaxW / STAGE_LOGICAL.w)));
  const boxW = Math.round(STAGE_LOGICAL.w * px / dpr + bw + GUTTER);
  const boxH = Math.round(fitH * px / dpr + bh + GUTTER);
  stage.style.width = `${boxW}px`;
  stage.style.height = `${boxH}px`;

  // THE BAND IS THE STAGE PLUS ITS CHROME, AND NOTHING ELSE DECIDES IT.
  // #battle-top is a stretch row, so its height is the tallest item's content
  // height — and #battle-brief is a wall of problem statement. A long statement
  // on a narrow window therefore grew the band past the stage and took the
  // difference out of the editor, which is how `max-height: 332px` came to be
  // nailed to the brief in the first place. Pin the row instead: the brief
  // stretches into whatever the fight leaves and scrolls inside it.
  if (top) top.style.height = `${boxH + chromeV}px`;

  /* THE LABEL GOES BEFORE THE BOX IT NAMES.
   *
   * #editor-caption and .editor-status are both `flex: 0 0 auto`, so
   * .editor-shell — the only `1 1 auto` in the column — absorbs every pixel of
   * shrink and the box disappears while the sentence pointing at it stays put.
   * Measured at 1024x640 with the shipped text_scale range: 1.0 gave 6 code
   * lines, 1.15 gave 3, 1.25 gave 2, and 1.5 gave ZERO — .editor-shell 2px tall
   * under a 66px caption, with body{overflow:hidden} leaving no scroll room to
   * reach it and 26 typed characters landing invisibly in a textarea that was
   * still the activeElement.
   *
   * So: measure the shell WITH the caption up, and if it cannot hold two lines
   * of code, take the caption down. A label pointing at nothing is worse than
   * no label — this file's own rule, game.css:314-317. Re-showing first makes
   * the decision fresh on every call, so growing the window brings it back. The
   * default text scale never reaches this: 6 lines at 1024x640, 11 at
   * 1600x1000. */
  const cap = $('#editor-caption');
  const shell = document.querySelector('#editor-pane .editor-shell');
  const host = $('#editor-host');
  if (cap && shell && host && host.style.display !== 'none') {
    cap.style.display = '';
    const lh = parseFloat(getComputedStyle(shell).lineHeight) || 18;
    if (shell.getBoundingClientRect().height < lh * 2) cap.style.display = 'none';
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
  /* THE SKY RIDES ON THE REGION RECORD, AND THE RECORD IS BEING REPLACED HERE.
   *
   * Every payload carries a fresh 24-slot weather strip — two hours of sky —
   * but the overworld holds the region OBJECT it was handed at the last
   * loadRegion(), and publishWeather() is called from nowhere else. Replacing
   * G.state without rebinding therefore leaves both renderers indexing the
   * strip that was fetched when the player last TRAVELLED: after two hours in
   * one region readSky() clamps to strip[23] and the sky is frozen there for
   * good. Measured live in graph_wastes: +115 min slot 23 and still honest;
   * +125, +150, +180 and +1440 min all clamped to slot 23 with the condition
   * stuck on `clear` while gauntlet/weather.py ran through storm, ashfall and
   * mist — 212 of the next 288 slots wrong, across every fight fought in them.
   *
   * Rebinding is the whole fix, and it fixes the BATTLE too: _pollSky() calls
   * resolveSky(record), whose rule 1 re-runs publishWeather(record), which
   * re-registers the new strip under both the region id and its palette — and
   * the palette is all main.js hands the stage. One assignment, two renderers.
   * loadRegion() is left alone: it is the only thing allowed to decide WHICH
   * region the overworld is in, and this only ever refreshes the one it holds. */
  if (G.overworld && G.overworld.region) {
    const fresh = next.regions.find(r => r.id === G.overworld.region.id);
    if (fresh) {
      G.overworld.region = fresh;
      G.overworld._pollSky();
    }
  }
  // Equipment changes the sprite. hero_look() has been computed and shipped on
  // every state payload since the armour system landed and nothing ever read it,
  // so the player's gear was invisible on the character they were playing.
  if (G.overworld && next.hero) {
    const stamp = JSON.stringify(next.hero);
    if (stamp !== G._heroStamp) {
      G._heroStamp = stamp;
      G.overworld.setEquipment(next.hero);
    }
  }
  paintVitals();
  // ensureAlarm rather than paintVitalBands: the band on screen must be dropped
  // when it no longer describes the health on screen, and that check lives in
  // exactly one place.
  ensureAlarm();
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
  /* AND THE STAGE, on the same line as the field. ensureStage() read this
   * setting once, when the first fight of the session built the stage, and
   * nothing ever told it again — so toggling Reduced Motion updated the
   * overworld and left the battle on whatever the setting had been at boot.
   * That is the same disagreement between the two renderers that the weather
   * had: one of them stops and the other does not. */
  if (G.fx) G.fx.setReducedMotion(!!s.reduced_motion);
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

  // Arriving somewhere for the first time gets its own track, once. Walking
  // back later is ordinary overworld music — the fanfare is for the discovery,
  // not for the place.
  const seenKey = 'gauntlet-seen-regions';
  let seen;
  try { seen = new Set(JSON.parse(localStorage.getItem(seenKey) || '[]')); }
  catch (e) { seen = new Set(); }
  const firstVisit = !seen.has(region.id);
  if (firstVisit) {
    seen.add(region.id);
    try { localStorage.setItem(seenKey, JSON.stringify([...seen])); } catch (e) { /* full */ }
  }
  /* NOT WHILE THE TITLE SCREEN OWNS THE SPEAKERS. Boot calls loadRegion()
   * before showTitle() so the world is built and warm behind the title, and
   * this line started the region's track every time — which the title's own
   * track then cancelled two calls later. `titling` is on <body> from
   * index.html and every deep link clears it before it gets here, so this reads
   * "is the title up right now"; leaveTitle() plays the region track itself. */
  if (!document.body.classList.contains('titling')) {
    audio.play(firstVisit ? 'newarea' : (region.music || 'overworld'));
  }
  // What roams here. One call per region: the Hunt row is per-region and the
  // forty-kilobyte client payload inside it is adopted once and ignored
  // thereafter, exactly as api.js asks.
  huntui.read(region.id).then((r) => {
    if (!r || r.error) return;
    if (currentRegion().id === region.id && G.screen === 'world') paintWorldSide();
  }).catch(() => { /* a region without a readout still walks */ });
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
  // The square. Health is free there and the player should never have to
  // wonder whether they can afford to keep going.
  const btnTown = el('button', 'btn good', 'THE TOWN SQUARE');
  btnTown.onclick = () => go('town');
  // The forty-seven voices, one call, identity first.
  const btnTalk = el('button', 'btn', 'TALK TO PEOPLE HERE');
  btnTalk.onclick = () => townui.talkOnTheOverworld(region.id);
  actions.append(btnNext, btnTown, btnBoss, btnShrine, btnForge, btnIncant, btnTalk);
  // Vess works in exactly one place. The button appears where she is standing
  // and nowhere else, which is the whole reason the map is an economy: you have
  // to carry the metal back.
  // `btnForge` above is the Armorer's DEBUG battle and has nothing to do with
  // this; the smith is a different person in a different building.
  const bench = s.forge || {};
  if (bench.smith && region.id === bench.smith.region) {
    const btnSmith = el('button', 'btn good',
      bench.ready ? '✦ VESS — SHE CAN WORK IT NOW' : 'VESS, THE VILLAGE SMITH');
    btnSmith.onclick = () => showSmith();
    actions.appendChild(btnSmith);
  } else if (bench.blade && bench.smith) {
    const hint = el('div', 'small muted',
      `The bench is in ${(G.state.regions.find(r =>
        r.id === bench.smith.region) || {}).name || 'the village'}. `
      + `${bench.held_total} bar(s) in the bag.`);
    actions.appendChild(hint);
  }
  side.appendChild(actions);

  // WHAT ROAMS HERE. Drawn from the readout the region load already fetched, so
  // this costs nothing, and it is a link to the whole thing rather than a
  // summary of it — hunters.py's own argument is that the readout is the
  // feature, and the readout does not fit in a sidebar.
  const hunted = huntui.view();
  if (hunted && hunted.apex && hunted.region === region.id) {
    side.appendChild(el('div', 'section-title', 'WHAT ROAMS HERE'));
    const h = hunted.hunt || {};
    const sc = hunted.scaling || {};
    const rd = hunted.readiness || {};
    /* THE CHAPTER RAMP, said beside the readiness score. The hunt used to cost
     * 26-52 encounters flat across the whole game — the same price in chapter I
     * as in chapter XI. It ramps now, and a player has to be able to see that
     * the number they are being quoted moved because of the ground rather than
     * because of them. `pace` is hunters.pace_for() and is computed from the
     * region id and the chapter alone, which is why it is readable even inside
     * a measured run while the readiness score beside it is not. */
    const pace = hunted.pace || null;
    const row = el('div', 'list-item',
      `<span class="t" style="color:${hunted.apex.colour}">${
         hunted.apex.name.toUpperCase()}
        <span class="tag">${h.state || 'DORMANT'}</span>
        <span class="tag ${rd.score >= 60 ? 'green' : 'orange'}">READY ${
          rd.score || 0}%</span></span>
       <span class="d">${sc.blurb || ''}<br>
         <span class="muted small">${sc.target_casts || '—'} cast(s) at your
         current preparation${hunted.kills
           ? ` · killed ${hunted.kills} time(s)` : ''}</span>
         ${pace ? `<br><span class="muted small">${pace.chapter_view.numeral} ·
           ${pace.casts_ready}–${pace.casts_unready} casts here, and this
           chapter ${pace.stance === 'TEACHES' ? 'teaches' : 'tests'}. The
           length is a property of WHERE YOU ARE STANDING; readiness only says
           where in that band you land.</span>` : ''}</span>`);
    row.onclick = () => go('hunt');
    side.appendChild(row);
  }

  // THE WEATHER HERE. Every region's element is derived from the biome it
  // already declares — elements.BIOME_AFFINITY — so this is a reading of what
  // the place physically is rather than a label somebody hung on it. Five of
  // the seventeen are neutral on purpose and say so: they are the baseline the
  // other twelve are felt against, and a map where everywhere has weather is a
  // map with no contrast in it.
  side.appendChild(el('div', 'section-title', 'THE WEATHER HERE'));
  side.appendChild(affinityPanel(region));

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

/* What this region is made of, what it does to your feet, and whether the boots
 * you are standing in answer it. All of it comes from /api/region — which calls
 * elements.hazard_step with roll pinned at 1.0, so it is a PREVIEW and cannot
 * inflict anything. Nothing here is a hint about any problem: it is the room. */
function affinityPanel(region) {
  const host = el('div');
  const cached = G.regionElement;
  if (!cached || cached.region !== region.id) {
    host.appendChild(el('div', 'small muted', 'Reading the ground…'));
    ensureRegionElement(region.id);
    return host;
  }
  const e = cached.data || {};
  const art = e.view || {};
  const hazard = e.hazard || {};
  const step = e.step || {};
  const boot = e.boots ? ((G.wheel && (G.wheel.boots || [])
    .find(b => b.id === e.boots)) || null) : null;
  if (!art.id) {
    host.appendChild(el('div', 'small muted',
      `<span style="color:var(--ink-dim)">NEUTRAL</span> — ${art.blurb
        || 'Weather-free. Whatever happens here, happens because you did it.'}`));
    return host;
  }
  const pct = Math.round((step.speed !== undefined ? step.speed : 1) * 100);
  host.appendChild(el('div', 'list-item',
    `<span class="t" style="color:${art.colour}">${art.rune || ''} ${
       art.name.toUpperCase()}</span>
     <span class="d">${art.blurb}
       ${art.opposed ? `<br><span class="muted">Countered by ${
         (wheelElement(art.opposed) || {}).name || art.opposed}. Carry that and
         the fights here are two thirds as long.</span>` : ''}</span>`));
  if (hazard.name) {
    // The RISK, not the roll. `step` is a preview taken with the die pinned, so
    // its `status` is empty by construction and reading it would report every
    // hazard as harmless. What the ground can do to you is the hazard's own
    // entry in elements.HAZARDS, which is what the wheel ships.
    const spec = (G.wheel && (G.wheel.hazards || [])
      .find(h => h.id === hazard.id)) || {};
    const risk = spec.status ? (wheelStatus(spec.status) || {}) : null;
    const cost = [];
    if (pct !== 100) cost.push(`you move at ${pct}% of your pace`);
    if (risk) {
      cost.push(`roughly one step in ${Math.max(1,
        Math.round(1 / (spec.chance || 1)))} leaves you
        ${(risk.name || spec.status).toLowerCase()}`);
    }
    host.appendChild(el('div', 'list-item',
      `<span class="t" style="color:${step.protected
         ? 'var(--green)' : 'var(--orange)'}">${hazard.name.toUpperCase()}</span>
       <span class="d">${hazard.blurb}<br><span class="muted">${
         step.protected
           ? `${boot ? boot.name : 'Your boots'} answer it. Full speed, and the
              ground cannot touch you.`
           : `Unprotected — ${cost.length ? cost.join(', and ')
               : 'it costs you nothing you can measure'}. ${
               boot ? `${boot.name} do not cover this.`
                    : 'Nothing on your feet answers it.'}`}</span></span>`));
  }
  return host;
}

/* One fetch per region, cached. The overworld repaints its side panel often and
 * a request per repaint would be a request per keystroke. */
function ensureRegionElement(regionId) {
  if (G._regionElementPending === regionId) return;
  G._regionElementPending = regionId;
  api.region(regionId).then((view) => {
    G._regionElementPending = null;
    if (!view || view.error) return;
    G.regionElement = { region: regionId, data: view.element || {} };
    // Only if the player is still standing where the answer is about.
    if (G.screen === 'world' && currentRegion().id === regionId) paintWorldSide();
  }).catch(() => { G._regionElementPending = null; });
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
  // A person. The mentor is one voice and banter.py has forty-seven more, so
  // the mentor opens and whoever else is standing here speaks after them —
  // ONE townTalk() call for all of them, never a speak() per face, or the town
  // disagrees with itself about the weather.
  if (marker.kind === 'npc') { mentorTalk(); return; }
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
  // And then everybody else who is standing here. Queued behind the mentor
  // rather than spoken over them, and drawn IDENTITY FIRST — the sentence that
  // says who this person is comes before the one that says what they noticed,
  // which is the difference between a town and an advice kiosk.
  G.afterStory = () => townui.talkOnTheOverworld(region.id);
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
  // A Mini-Repo left mounted keeps a clock running behind the battle screen.
  destroyRepo();
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
  // Cleared before the branch, so a code fight after a question never inherits
  // the question's answers as its trials.
  G.mcq = null;
  if (puzzleui.isPuzzle(p.encounter_kind)) {
    renderPuzzle(p);
  } else if (p.entry && p.entry.kind === 'mcq') {
    renderMcq(p);
  } else {
    G.editor.reset(p.starter_code || '');
    $('#editor-host').style.display = '';
    $('#puzzle-host').style.display = 'none';
    // One verb, set on the button and on the sentence that points at it.
    const verb = p.entry.kind === 'test_forge' ? 'FORGE ✦' : 'CAST ✦';
    setEditorMode('code', verb);
    $('#btn-run').style.display = '';
    $('#btn-submit').textContent = verb;
  }

  // Which region's apex this fight's casts count against. Read off the
  // encounter rather than off the player, because a memory ambush can be set
  // somewhere the player is not standing.
  G.huntRegion = (payload.encounter && payload.encounter.region)
    || (payload.region || {}).id || currentRegion().id;

  startTimer();
  // The alarm BEFORE the strip, so a player who walked into this fight already
  // hurt is told on the frame the fight appears rather than one cast later.
  noteAlarm(payload.alarm);
  // The turn, both pairs of bars, the statuses and the belt. Drawn before the
  // screen is shown so the fight never appears without its own state on it.
  paintCombatHud(hudFromPayload(payload));
  // An MCQ stays on trials even in a measured run: `approach` would hide the
  // only way to answer, and the seal is about help, not about the question.
  setTab(G.mcq ? 'trials' : visibleTab(interview ? 'approach' : 'trials'));
  show('battle');
  // AFTER show(), and this is the whole reason the caret was never in the
  // editor: Editor.reset() focuses the textarea, but it runs while
  // #screen-battle is still display:none and focusing a node in a hidden
  // subtree does nothing at all. So the fight opened with the caret on <body>,
  // no ring, no clue, and every report of "I can't tell where to type" was
  // literally true. A boss taunt takes it straight back — say() releases it and
  // advanceDialogue hands it over when the talking stops.
  //
  // keepSelection: this is the ONE focus that is not a hand-back. Editor.reset()
  // has just selected the __BLANK__ slot on purpose so the first keystroke
  // replaces it, and collapsing that here would delete the feature rather than
  // protect it. The guard still swallows the tail of the SPACE tap that walked
  // the player into this fight.
  focusEditor({ keepSelection: true });
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
  /* THE FIGHT'S OWN PHASE, CARRIED TO THE SPRITE BUILDER.
   *
   * web/js/bosses.js has drawn six art stages since it was written and nothing
   * in the tree ever asked it for one: every boss in every fight was rendered
   * at stage 0. The fight knew its phase, the art knew how to draw one, and no
   * line carried the number from one to the other. This is that line.
   *
   * `payload.boss.fight` is gauntlet/bestiary.view() — phase, phases and the
   * art stage the SERVER computed, so the client never has to infer a stage
   * from a health fraction again. It also means walking back into a fight
   * three phases deep opens on the right creature instead of a whole one. */
  const fight = (payload.boss || {}).fight || null;
  const enemy = fight
    ? { ...payload.enemy, phase: fight.phase, phases: fight.phases,
        art_phase: fight.art_phase }
    : payload.enemy;
  fx.setScene({
    region: (payload.region || {}).palette || 'spring',
    enemy,
    pattern: payload.problem.pattern,
    heroLook: G.state && G.state.hero,
    // The rung the player actually paid for, in the hand, on the stage. The
    // server ships it inside hero_look because that is the one place that
    // already knows what is equipped.
    gear: G.state && G.state.hero && G.state.hero._gear,
  });
  /* A boss's pips are its PHASES, not its trials: one per phase, lit for the
   * ones still standing, which is bestiary.view's `pips`/`pips_lit` exactly.
   * The trial bar above it still counts hidden tests, and the two are
   * deliberately different numbers — one says how close this answer is, the
   * other says how much fight is left. */
  if (fight) fx.setEnemyHp(fight.pips_lit, fight.pips);
  else fx.setEnemyHp(payload.enemy.hp, payload.enemy.hp_max);
  // The ground this is being fought on. `element.region` is the region's biome
  // pushed through elements.BIOME_AFFINITY, so a cold place reads cold because
  // of what it physically is — and a neutral region gets nothing added, which
  // is what makes the other twelve feel like somewhere. Sealed runs send an
  // empty string here and the stage stays plain; that is the crutch going, not
  // the mechanic.
  const elt = payload.element || {};
  fx.setAffinity(elt.region || '', { hazard: (elt.hazard || {}).id || '' });
  fx.start();
  return fx;
}

/* ======================================================================
 * THE TURN, THE BARS, THE STATUSES AND THE BELT
 * ======================================================================
 *
 * One strip between the stage and the editor, and it is the only place in this
 * client that draws the tactical layer. Everything on it is read off the
 * server's own payload — engine._encounter_payload and the result of a graded
 * submission ship the same keys — so nothing here recomputes a number the
 * engine already decided, and nothing here decides one.
 *
 * WHY IT EXISTS AT ALL. A player losing a fight has to be able to see WHY. An
 * elemental multiplier that only ever appears as a smaller number is not a
 * mechanic, it is a rumour; a poison tick with nothing on screen is the game
 * appearing to cheat. Everything below is the difference between a tactical
 * layer and noise with numbers in it.
 *
 * WHAT IT IS NOT. It is not a way to win a fight. The attack in this game is
 * the line of Python in the editor to the right of it, and the loudest thing on
 * this strip — the belt — is deliberately the thing that cannot end a turn.
 */

/* The rulebook, fetched once at boot from /api/wheel. Every status name, every
 * duration, every hazard and every matchup label lives in elements.py; this is
 * the lookup side of that and it holds no opinions of its own. Empty until the
 * fetch lands, and every reader below tolerates that, because a HUD that throws
 * because a codex has not arrived is worse than a HUD with fewer words on it. */
/* Everything below builds title= attributes out of prose that comes from
 * elements.py, potions.py and bestiary.py. None of it is player input, but a
 * module author writing an apostrophe or a quote in a blurb should not be able
 * to break a tooltip, so it goes through here rather than being trusted. */
function attr(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function wheelStatus(id) {
  const w = G.wheel || {};
  return (w.statuses || []).find(s => s.id === id) || null;
}

function wheelElement(id) {
  const w = G.wheel || {};
  if (!id) return w.neutral || null;
  return (w.elements || []).find(e => e.id === id) || w.neutral || null;
}

function wheelMatchup(kind) {
  const w = G.wheel || {};
  return ((w.matchups || {})[kind]) || null;
}

function wheelSpecial(id) {
  const w = G.wheel || {};
  return (w.specials || []).find(sp => sp.id === id) || null;
}

function ensureCombatStyle() {
  if (document.getElementById('combat-style')) return;
  const node = document.createElement('style');
  node.id = 'combat-style';
  node.textContent = `
/* max-height, because this strip's height is otherwise UNBOUNDED: it grows with
   the enemy's statuses, the belt and the turn rule, and every pixel of it comes
   straight off the editor below. Measured at 1024x640 it ran 153px at text
   scale 1 and 210px at 1.5, on a fight with nothing much in it. 22vh is a fifth
   of the screen and the rest scrolls inside itself. */
#combat-hud {
  flex: 0 0 auto; display: none; gap: 8px;
  padding: 6px 14px; background: var(--panel-2);
  border-bottom: 3px solid var(--line); flex-direction: column;
  max-height: 22vh; overflow-y: auto;
}
#combat-hud.on { display: flex; }
.chud-top { display: flex; gap: 12px; align-items: stretch; }
.chud-side { flex: 1 1 0; min-width: 0; }
.chud-side.them { text-align: right; }
.chud-name {
  font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: var(--ink-dim); margin-bottom: 5px; letter-spacing: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chud-el {
  display: inline-block; padding: 1px 5px; margin-left: 6px;
  border: 1px solid currentColor; font-size: calc(7px * var(--scale));
}
.chud-bar { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.chud-side.them .chud-bar { flex-direction: row-reverse; }
.chud-bar .lb {
  flex: 0 0 30px; font-family: 'Press Start 2P', monospace;
  font-size: calc(6px * var(--scale)); color: var(--ink-faint);
}
.chud-bar .bar { flex: 1 1 auto; height: 10px; }
.chud-bar .vv {
  flex: 0 0 62px; font-size: calc(10px * var(--scale)); color: var(--ink-dim);
  text-align: right; font-variant-numeric: tabular-nums;
}
.chud-side.them .chud-bar .vv { text-align: left; }
.bar.focus > i { background: linear-gradient(90deg,#5a4f95,#a89aff); }
/* The mark on the enemy's focus bar is where its cheapest special becomes
   affordable. A gauge filling toward nothing in particular teaches nothing;
   a gauge filling toward a line teaches the player to watch it. */
.chud-bar .bar .mk {
  position: absolute; top: -2px; bottom: -2px; width: 2px;
  background: var(--gold-hi); opacity: .85;
}
.chud-stats { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.chud-side.them .chud-stats { justify-content: flex-end; }
.chud-stat {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 6px;
  border: 1px solid currentColor; font-size: calc(9px * var(--scale));
  cursor: help;
}
.chud-stat b { font-variant-numeric: tabular-nums; }
.chud-turn {
  flex: 0 0 148px; text-align: center; border-left: 2px solid var(--line);
  border-right: 2px solid var(--line); padding: 0 10px;
}
.chud-turn .tn {
  font-family: 'Press Start 2P', monospace; font-size: calc(12px * var(--scale));
  color: var(--gold-hi);
}
.chud-turn .tw {
  font-family: 'Press Start 2P', monospace; font-size: calc(7px * var(--scale));
  color: var(--green); margin-top: 5px; letter-spacing: 1px;
}
.chud-turn .tm {
  font-size: calc(10px * var(--scale)); margin-top: 5px; line-height: 1.5;
}
.chud-said {
  border-left: 3px solid var(--orange); background: var(--panel);
  padding: 5px 9px; font-size: calc(11px * var(--scale));
  color: var(--ink-dim); line-height: 1.6;
}
.chud-said b { color: var(--orange); }
.chud-belt { display: flex; gap: 6px; align-items: stretch; flex-wrap: wrap; }
.potion {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  min-width: 74px; padding: 5px 7px; background: var(--panel);
  border: 2px solid var(--line); cursor: pointer; color: var(--ink-dim);
  font-size: calc(9px * var(--scale)); line-height: 1.4; text-align: center;
}
.potion:hover:not(.off) { border-color: var(--line-hi); background: var(--panel-3); }
.potion .pn {
  font-family: 'Press Start 2P', monospace; font-size: calc(6px * var(--scale));
  letter-spacing: .5px;
}
.potion .pv { font-size: calc(10px * var(--scale)); }
.potion .ph { color: var(--gold-hi); font-variant-numeric: tabular-nums; }
.potion.off { opacity: .42; cursor: not-allowed; }
/* The belt and the turn rule used to be two stacked rows in a strip that was
 * already taking two hundred pixels off the top of the editor. They are short
 * and the screen is wide: one row, potions left, rule right. */
.chud-foot { display: flex; gap: 16px; align-items: flex-start; }
.chud-foot .chud-belt { flex: 0 1 auto; }
.chud-foot .chud-rule { flex: 1 1 0; min-width: 0; align-self: center; }
.chud-rule {
  font-size: calc(10px * var(--scale)); color: var(--ink-faint);
  font-style: italic; line-height: 1.6;
}
.chud-rule b { color: var(--green); font-style: normal; }
.chud-empty { font-size: calc(10px * var(--scale)); color: var(--ink-faint); }
`;
  document.head.appendChild(node);
}

/* Built here rather than in index.html because it belongs to the fight and not
 * to the page: every screen that is not a battle hides it, and a node that only
 * one screen uses is a node that screen should own. */
function ensureCombatHud() {
  ensureCombatStyle();
  let node = $('#combat-hud');
  if (node) return node;
  node = el('div', '');
  node.id = 'combat-hud';
  node.innerHTML = `
    <div class="chud-top">
      <div class="chud-side you">
        <div class="chud-name" id="chud-you-name">YOU</div>
        <div class="chud-bar"><span class="lb">HP</span>
          <div class="bar hp"><i id="chud-you-hp" style="width:100%"></i></div>
          <span class="vv" id="chud-you-hp-v">—</span></div>
        <div class="chud-bar"><span class="lb">FOCUS</span>
          <div class="bar focus"><i id="chud-you-fp" style="width:100%"></i></div>
          <span class="vv" id="chud-you-fp-v">—</span></div>
        <div class="chud-stats" id="chud-you-stats"></div>
      </div>
      <div class="chud-turn">
        <div class="tn" id="chud-turn-n">TURN 1</div>
        <div class="tw" id="chud-turn-w">YOURS</div>
        <div class="tm" id="chud-match"></div>
      </div>
      <div class="chud-side them">
        <div class="chud-name" id="chud-them-name">—</div>
        <div class="chud-bar"><span class="lb">HP</span>
          <div class="bar hp"><i id="chud-them-hp" style="width:100%"></i></div>
          <span class="vv" id="chud-them-hp-v">—</span></div>
        <div class="chud-bar"><span class="lb">FOCUS</span>
          <div class="bar focus"><i id="chud-them-fp" style="width:0%"></i></div>
          <span class="vv" id="chud-them-fp-v">—</span></div>
        <div class="chud-stats" id="chud-them-stats"></div>
      </div>
    </div>
    <div class="chud-said" id="chud-said" style="display:none"></div>
    <div class="chud-foot">
      <div class="chud-belt" id="chud-belt"></div>
      <div class="chud-rule" id="chud-rule"></div>
    </div>`;
  const main = $('#battle-main');
  main.parentNode.insertBefore(node, main);
  return node;
}

function hideCombatHud() {
  const node = $('#combat-hud');
  if (node) node.classList.remove('on');
  G.hud = null;
  // The WASH goes with the fight it belonged to. The beat does not: walking out
  // of a battle at two health does not make two health safe, and the field is
  // where the potions and the Mender are. paintAlarmBeat re-decides from the
  // screen the player is actually on.
  stopWash();
  paintAlarmBeat();
}

/* ======================================================================
 * THE LOW-HEALTH ALARM
 * ======================================================================
 *
 * upkeep.py's brief, in its own words: "At low health the player sprite blinks
 * red with a heartbeat so it is impossible to miss." Two channels, ONE CLOCK —
 * `pulse_hz` is literally `bpm / 60` — because a sprite flashing at one speed
 * over a heart thumping at another reads as two unrelated warnings and a player
 * tunes both out.
 *
 * WHERE THE NUMBERS COME FROM, and this is the whole of the design here: the
 * server. `upkeep.alarm_for` ships the band, the colour, the two alphas, the
 * rate and the advice, and every door that can change a player's health hands
 * one back — a graded submission, the Mender, a hidden healer, the square. This
 * file stores the last one and draws it. It does NOT hold a copy of
 * ALARM_BANDS: WORN is at 0.50 and CRITICAL at 0.35 in exactly one file, and a
 * second copy here is how the pulse and the bar end up disagreeing about when
 * things got bad.
 *
 * WORN does not pulse, on purpose. An alarm that starts at half health runs for
 * most of every fight, and an alarm that is always on is decoration.
 */
/* The wash sits over the hero on the battle stage. fx.js places the sprite at
 * STAGE.heroX on a letterboxed, whole-number-scaled canvas and publishes `px`,
 * `ox` and `oy` for exactly this kind of question, so the overlay is positioned
 * off those rather than guessed at in percentages. If the stage has not been
 * built yet the fallback is the proportion, which is close enough to be
 * unmistakable and is never wrong by more than a letterbox. */
function placeAlarm(node) {
  const stage = $('#battle-stage');
  if (!stage) return;
  const rect = stage.getBoundingClientRect();
  // Fallback proportions are against the VISIBLE box, which is the safe area
  // (rows 24..199), not the whole 224-line raster: heroX 64 of 256 across, and
  // the ground line 175 sits (175-24)/176 down what the player can see.
  let cx = rect.width * (64 / 256);
  let cy = rect.height * ((175 - 24) / 176) - rect.height * 0.16;
  let size = Math.min(rect.width, rect.height) * 0.42;
  const fx = G.fx;
  if (fx && fx.canvas && fx.px) {
    const dpr = fx.canvas.width / Math.max(1, parseFloat(fx.canvas.style.width) || 1);
    const scale = fx.px / (dpr || 1);
    // STAGE.heroX is 64 and STAGE.ground is 175, in fx.js's 256x224 stage
    // space. The hero is sixteen by twenty-four source pixels, so its body runs
    // from ground-24 to the ground; centring 36 above the ground and covering
    // 66 puts the wash on the torso rather than on the shadow. Those two are
    // offsets from the ground line and the figure did not change size, so they
    // carry across the raster move unaltered. fx.oy is now NEGATIVE — the
    // overscan hangs off the canvas — which is exactly why this reads it rather
    // than assuming the art starts at the top of the box.
    cx = ((fx.ox / (dpr || 1)) + 64 * scale);
    cy = ((fx.oy / (dpr || 1)) + (175 - 36) * scale);
    size = 66 * scale;
  }
  node.style.left = `${Math.round(cx - size / 2)}px`;
  node.style.top = `${Math.round(cy - size / 2)}px`;
  node.style.width = `${Math.round(size)}px`;
  node.style.height = `${Math.round(size)}px`;
}

/* WHERE EACH HALF OF THE ALARM IS ALLOWED TO EXIST.
 *
 * The WASH is a node positioned over #battle-stage, so it is battle-only by
 * construction — there is no stage to hang it on anywhere else.
 *
 * The BAR and the SOUND are not. "health and focus meter should always be
 * visible even in the overworld and when at 10% the health bar should beat and
 * glow red with the sound of the heartbeats" — an alarm that only fires on the
 * screen where you cannot heal is a warning delivered too late to act on. The
 * topbar is outside .screen and therefore always up, so the band paints on
 * every screen and the heart is audible in the field as well as the fight.
 *
 * Neither half decides anything. Both read G.alarm, which is upkeep.alarm() as
 * the server last sent it — see ensureAlarm: when it goes stale this draws
 * NOTHING rather than guessing, because a copy of ALARM_BANDS living in the
 * client is how the bar and the pulse end up with two opinions. */
function paintAlarm() {
  const alarm = G.alarm;
  const on = !!(alarm && alarm.pulse && G.screen === 'battle');
  const label = $('#chud-you-hp-v');
  if (label) label.classList.toggle('alarming', !!(alarm && alarm.pulse));
  paintVitalBands();
  paintAlarmBeat();
  if (!on) { stopWash(); return; }
  const stage = $('#battle-stage');
  if (!stage) return;
  if (getComputedStyle(stage).position === 'static') stage.style.position = 'relative';
  if (!G.alarmNode || !G.alarmNode.isConnected) {
    G.alarmNode = el('div', '');
    G.alarmNode.id = 'hero-alarm';
    stage.appendChild(G.alarmNode);
  }
  const node = G.alarmNode;
  placeAlarm(node);
  node.style.background = `radial-gradient(circle, ${alarm.colour} 0%, `
    + `${alarm.colour}00 70%)`;

  const reduced = !!(G.state && G.state.settings.reduced_motion);
  if (reduced) {
    // A player who turned the movement off still has to be told. The colour
    // holds at the top of the band instead of blinking, which is the same
    // warning without the flashing — and flashing is the accessibility problem
    // this setting exists to answer.
    node.style.animation = 'none';
    node.style.opacity = String(alarm.alpha_max);
  } else {
    const period = alarm.pulse_hz ? 1 / alarm.pulse_hz : 1;
    node.style.animation = `heroalarm ${period.toFixed(3)}s ease-in-out infinite`;
    node.style.setProperty('--a0', String(alarm.alpha_min));
    node.style.setProperty('--a1', String(alarm.alpha_max));
  }

  // The sound, on the SAME clock, and that is the whole of upkeep's design
  // here: `pulse_hz` is literally `bpm / 60`, so a sprite blinking at one rate
  // over a heart thumping at another reads as two unrelated warnings and gets
  // tuned out. The interval comes off the server's own `bpm` rather than out of
  // audio.heartbeatInterval — that function re-derives the tempo from severity
  // and lands two milliseconds away, which is nothing to hear and is still two
  // places deciding one number. The severity is passed on for the SHAPE of the
  // thump, which is audio's business.
}

/* The screens the heart is allowed to be heard on. A menu, a shop, the ledger
 * and the editor are all places where a thump under the text is noise rather
 * than warning; the field and the fight are the two places the player can act
 * on it. */
const BEAT_SCREENS = new Set(['battle', 'world']);

function paintAlarmBeat() {
  const alarm = G.alarm;
  if (!alarm || !BEAT_SCREENS.has(G.screen)) { stopBeat(); return; }
  const sev = Number(alarm.severity) || 0;
  const bpm = Number(alarm.bpm) || 0;
  const wanted = (alarm.heartbeat && bpm)
    ? Math.round(60000 / bpm)
    : (alarm.heartbeat ? audio.heartbeatInterval(sev) : 0);
  if (!wanted) { stopBeat(); return; }
  if (G.alarmBeat && G.alarmBeat.ms === wanted) return;
  stopBeat();
  const id = setInterval(() => {
    // Every tick re-checks its own reason for existing: a heartbeat that
    // outlives the fight is the sixth leak this file is not going to have.
    if (!BEAT_SCREENS.has(G.screen) || !G.alarm || !G.alarm.heartbeat) {
      stopBeat(); return;
    }
    audio.heartbeat(Number(G.alarm.severity) || 0);
  }, wanted);
  G.alarmBeat = { id, ms: wanted };
  audio.heartbeat(sev);
}

/* The topbar bar itself: red at CRITICAL, red AND beating at DIRE, on the same
 * clock as everything else because --beat-ms is the server's own bpm. The CSS
 * is in game.css; this only ever moves two class names and one variable. */
function paintVitalBands() {
  const bar = $('#bar-stamina');
  const vital = bar && bar.closest ? bar.closest('.vital') : null;
  if (!vital) return;
  const a = G.alarm;
  const band = (a && a.band) || '';
  vital.classList.toggle('critical', band === 'CRITICAL');
  vital.classList.toggle('dire', band === 'DIRE');
  const bpm = Number(a && a.bpm) || 0;
  if (band === 'DIRE' && bpm) {
    vital.style.setProperty('--beat-ms', `${Math.round(60000 / bpm)}ms`);
  } else {
    vital.style.removeProperty('--beat-ms');
  }
}

function stopBeat() {
  if (G.alarmBeat) clearInterval(G.alarmBeat.id);
  G.alarmBeat = null;
}

function stopWash() {
  if (G.alarmNode && G.alarmNode.isConnected) G.alarmNode.remove();
  G.alarmNode = null;
}

function stopAlarm() {
  stopBeat();
  stopWash();
}

/* ======================================================================
 * THE UNMAKING — the spell that explains the seal
 *
 * "the python last boss casts a spell on you rendering all skills and abilities
 *  obsolete thus giving a story line to the practical no help. forces you to
 *  fight in pure python"
 *
 * It plays HERE, between the player confirming the practical and the first
 * question appearing, because that is the seam the story has to cover: the
 * fourteen things finalexam.EXAM_SEAL takes are the fourteen things he is shown
 * taking, in the same order, and unmaking.py's last act is a blank editor and a
 * cursor — which is the practical.
 *
 * THE SPELL EXPLAINS THE SEAL; IT DOES NOT CHANGE IT. Nothing here is allowed
 * to alter what the exam does, and nothing does: the payload is read-only
 * narration and `finalexam.sealed()` remains the one capability check. Skipping
 * it, or failing to fetch it, changes nothing about the exam that follows.
 *
 * There are two Unmakings and this is the CHAMBER one — the full telling, once.
 * The world-map cast is unmakingfx.js via overworld.castUnmaking, is fifteen
 * seconds, and is wordless. See docs/11-the-two-unmakings.md before merging
 * them; they are not duplicates.
 */
async function playUnmaking() {
  let payload = null;
  try { payload = await api.unmaking(); } catch (e) { payload = null; }
  // A spell that will not load is silence, and the exam is unaffected.
  if (!payload || payload.error) return;

  const reduced = !!(G.state && G.state.settings && G.state.settings.reduced_motion);
  let seq;
  try {
    spellfx.warmUnmaking({ cinematic: payload });
    seq = spellfx.createUnmakingCinematic({ cinematic: payload, reducedMotion: reduced });
  } catch (e) { return; }

  const host = el('div', '');
  host.id = 'unmaking-screen';
  host.style.cssText = 'position:fixed;inset:0;z-index:8900;background:#000';
  const cv = document.createElement('canvas');
  cv.style.cssText = 'width:100%;height:100%;display:block';
  // spellfx draws the title card and deliberately does NOT own the subtitle
  // layer, so his lines are rendered here, in the game's own voice styling.
  const line = el('div', '');
  line.style.cssText = 'position:absolute;left:0;right:0;bottom:6%;text-align:center;'
    + 'padding:0 8%;font-size:15px;line-height:1.7;color:#cfc9d8;'
    + 'text-shadow:0 2px 0 #000;pointer-events:none';
  const hint = el('div', '');
  hint.style.cssText = 'position:absolute;right:14px;bottom:10px;font-size:10px;'
    + 'color:#4a4458;pointer-events:none';
  host.append(cv, line, hint);
  document.body.appendChild(host);
  const ctx = cv.getContext('2d');
  const fit = () => {
    cv.width = Math.max(1, host.clientWidth);
    cv.height = Math.max(1, host.clientHeight);
  };
  fit();
  window.addEventListener('resize', fit);

  audio.silence();
  try { seq.begin({ cinematic: payload }); } catch (e) { /* drawn anyway */ }

  await new Promise((resolve) => {
    let last = 0, finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      window.removeEventListener('resize', fit);
      window.removeEventListener('keydown', onKey);
      if (host.isConnected) host.remove();
      resolve();
    };
    const onKey = (ev) => {
      // The skip arms only once the first dispossession has finished, so a key
      // that was already down cannot eat the spell. That policy is the
      // module's, asked rather than reimplemented.
      let armed = false;
      try { armed = seq.canSkip(); } catch (e) { armed = false; }
      if (!armed) return;
      ev.preventDefault();
      try { seq.skipToEnd(); } catch (e) { finish(); }
    };
    window.addEventListener('keydown', onKey);
    const step = (ms) => {
      if (finished) return;
      if (!last) last = ms;
      const dt = Math.min(0.1, (ms - last) / 1000);
      last = ms;
      try {
        seq.update(dt);
        seq.draw(ctx, cv.width, cv.height);
        const say = seq.speaking();
        line.textContent = say && say.text ? say.text : '';
        hint.textContent = seq.canSkip() ? 'ANY KEY' : '';
      } catch (e) { finish(); return; }
      if (seq.active) requestAnimationFrame(step);
      else finish();
    };
    requestAnimationFrame(step);
  });

  // Latch it, so a second sitting gets the wordless short form rather than two
  // minutes the player has already watched.
  try { await api.unmakingSeen(); } catch (e) { /* cosmetic */ }
}

/* ======================================================================
 * THE TRANSFORMATION — "BY THE SOURCE, I NAME IT."
 *
 * docs/09-story-bible.md §7, and transform.js's own header states the gate:
 * it fires on a CLUTCH CLEAR, and the timing is the whole point. "The sequence
 * is a reward for a thing the player did well, so it has to be gated on
 * evidence rather than on a cooldown, or it becomes an interruption instead of
 * a payoff."
 *
 * So the gate is deliberately narrow, and both halves are read off the result
 * the engine already built:
 *   - a BOSS went down while the player was in the red, or
 *   - an S rank taken with no probe spent and no hint taken.
 * Anything looser and a four-second cinematic starts landing on ordinary
 * clears, which is how a payoff becomes a thing people press escape through.
 */
/* WHAT A CLUTCH CLEAR IS NOT, learned by playing it: my first gate fired the
 * whole four-second cinematic on ENCOUNTER ONE, for correctly answering a
 * multiple-choice question about `print(10 - 4)`. An S rank with no hints is
 * not evidence of anything when the problem is GUIDED and the answer is one of
 * four buttons — the corpus is 473 GUIDED/TUTORIAL problems deep precisely so
 * the opening hours are easy, and a reward that fires there fires constantly.
 *
 * So the difficulty is part of the gate, and so is having actually WRITTEN
 * something. transform.js's own header is the specification: "a hard problem
 * solved unaided, a boss taken down at low health", and "gated on evidence
 * rather than on a cooldown, or it becomes an interruption instead of a
 * payoff". */
const CLUTCH_DIFFICULTY = new Set(['MEDIUM', 'HARD']);

function isClutchClear(result) {
  if (!result || !result.solved) return false;
  const p = (G.state && G.state.player) || {};
  const max = Math.max(1, Number(p.stamina_max) || 1);
  const ratio = (Number(result.stamina) || 0) / max;
  // A boss taken down in the red, at any difficulty: the fight is the evidence.
  if ((result.boss || {}).defeated && ratio <= 0.35) return true;

  // Otherwise it has to be a hard problem the player actually wrote, cleanly.
  const prob = G.problem || {};
  if (!CLUTCH_DIFFICULTY.has(String(prob.difficulty || '').toUpperCase())) return false;
  // Picking the right button is not writing code, however clean the pick.
  if ((prob.entry || {}).kind === 'mcq') return false;
  const probes = Number((result.combat || {}).probes_used) || 0;
  const hints = Number((result.combat || {}).hints_used || result.hints_used) || 0;
  return result.rank === 'S' && probes === 0 && hints === 0;
}

function playTransformation(title) {
  const reduced = !!(G.state && G.state.settings && G.state.settings.reduced_motion);
  // A player who turned movement off is not shown a four-second strobe. They
  // are told instead — the same information, without the thing the setting
  // exists to remove.
  if (reduced) {
    toast('BY THE SOURCE', `${(title || 'ARCHITECT').toUpperCase()} — I NAME IT.`, 'gold');
    return Promise.resolve();
  }
  const host = el('div', '');
  host.id = 'transform-screen';
  host.style.cssText = 'position:fixed;inset:0;z-index:8800;background:#000';
  const cv = document.createElement('canvas');
  cv.style.cssText = 'width:100%;height:100%;display:block';
  host.appendChild(cv);
  document.body.appendChild(host);
  const ctx = cv.getContext('2d');
  const fit = () => {
    cv.width = Math.max(1, host.clientWidth);
    cv.height = Math.max(1, host.clientHeight);
  };
  fit();
  window.addEventListener('resize', fit);

  const seq = new Transformation();
  return new Promise((resolve) => {
    let last = 0;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      window.removeEventListener('resize', fit);
      window.removeEventListener('keydown', onKey);
      if (host.isConnected) host.remove();
      resolve();
    };
    const onKey = () => seq.cancel();
    window.addEventListener('keydown', onKey);
    seq.begin(title, finish);
    const step = (ms) => {
      if (done) return;
      if (!last) last = ms;
      const dt = Math.min(0.1, (ms - last) / 1000);
      last = ms;
      ctx.clearRect(0, 0, cv.width, cv.height);
      seq.update(dt);
      seq.draw(ctx, cv.width, cv.height);
      if (seq.active) requestAnimationFrame(step);
      else finish();
    };
    requestAnimationFrame(step);
  });
}

/* ======================================================================
 * DYING
 *
 * "when the player reaches 0 health points hp, the screen goes black a
 *  heartbeat noise slowly does 1 then 2 then 3 progressively slower beats and
 *  blacks out. the player then wakes up at the last save point."
 *
 * The engine has already done the irreversible half by the time this runs:
 * gauntlet/death.py rewound the game, wrote the state through, and handed back
 * the report. This function is the telling of it, and it owns no rules — every
 * duration, every tempo and every word comes off `payload.heartbeat` and
 * `payload.report`, which is why the beats here and the alarm the player was
 * ignoring a second ago are one continuous heart: the first death beat is
 * upkeep.BPM_MAX, exactly where the alarm left off.
 *
 * It deliberately does not gate on a screen. You can die in a fight or in an
 * incantation out in the field, and both end the same way.
 */
function playDeath(payload) {
  if (!payload) return Promise.resolve();
  // The alarm is over; it was right, and leaving it ticking under the death
  // beats would be two hearts.
  stopAlarm();
  audio.silence();

  const reduced = !!(G.state && G.state.settings && G.state.settings.reduced_motion);
  const seq = deathfx.createDeath({
    look: (G.state && G.state.hero) || null,
    alarmColour: (payload.colour) || deathfx.DIRE_FALLBACK,
    reduced,
    report: payload.report || null,
    seen: Number(payload.seen) || 0,
  });

  const host = el('div', '');
  host.id = 'death-screen';
  host.style.cssText = 'position:fixed;inset:0;z-index:9000;background:#000';
  const cv = document.createElement('canvas');
  cv.style.cssText = 'width:100%;height:100%;display:block';
  host.appendChild(cv);
  document.body.appendChild(host);
  const ctx = cv.getContext('2d');

  const fit = () => {
    cv.width = Math.max(1, host.clientWidth);
    cv.height = Math.max(1, host.clientHeight);
  };
  fit();
  window.addEventListener('resize', fit);

  try { audio.heartbeatStop(); } catch (e) { /* audio is never load-bearing */ }
  seq.begin();

  return new Promise((resolve) => {
    let last = 0;
    const onKey = (ev) => {
      // The skip arms on deathfx's own schedule, not ours: a key already down
      // when the screen appeared must not eat the sequence.
      if (!deathfx.skipArmedAt(seq.t)) return;
      ev.preventDefault();
      seq.skip();
    };
    window.addEventListener('keydown', onKey);

    const done = () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', fit);
      if (host.isConnected) host.remove();
      resolve();
    };

    const step = (ms) => {
      if (!last) last = ms;
      const dt = (ms - last) / 1000;
      last = ms;
      seq.update(dt);
      const st = deathfx.renderDeath(seq.t, {
        reduced, alarmColour: seq.alarmColour, look: seq.look,
        words: seq.words, report: seq.report,
      });
      deathfx.blitDeath(ctx, cv.width, cv.height, st);
      if (seq.active) { requestAnimationFrame(step); return; }
      // The words hold until the player asks to leave. `active` going false is
      // the end of the ANIMATION, not the end of the screen.
      const leave = (ev) => {
        if (ev) ev.preventDefault();
        window.removeEventListener('keydown', leave);
        host.removeEventListener('click', leave);
        done();
      };
      window.addEventListener('keydown', leave);
      host.addEventListener('click', leave);
    };
    requestAnimationFrame(step);
  }).then(async () => {
    // The engine already wrote the rewound state. Read it back rather than
    // patching what we had: this client's copy is of a game that no longer
    // exists.
    hideCombatHud();
    G.encounter = null;
    await refresh();
    const where = (payload.report && payload.report.wake) || {};
    toast('YOU WAKE', where.region
      ? `${where.label || 'Last waking point'} — ${where.region}.`
      : 'Where you fell.', 'violet');
    show('world');
    if (G.overworld) audio.play(currentRegion().music || 'overworld');
  });
}

/* One alarm, from wherever the server just sent one. The band is latched and
 * spoken only on a transition DOWNWARD, which is upkeep.py's own instruction:
 * an advice line every frame is an advice line nobody reads. */
function noteAlarm(alarm) {
  if (!alarm || !alarm.band) return;
  G.alarm = alarm;
  const order = ['DIRE', 'CRITICAL', 'WORN', 'STEADY'];
  const worse = order.indexOf(alarm.band) < order.indexOf(G.alarmBand || 'STEADY');
  if (alarm.band !== G.alarmBand) {
    G.alarmBand = alarm.band;
    if (worse && alarm.advice) {
      toast(alarm.name.toUpperCase(), alarm.advice,
            alarm.band === 'DIRE' ? 'red' : 'violet');
    }
  }
  paintAlarm();
}

/* THE ONE THING THIS MUST NOT DO IS FETCH.
 *
 * The obvious source for an alarm is `api.town()`, and it is a trap: reading the
 * square is `upkeep.town_visit`, which HEALS FOR FREE and resets the since-town
 * counters. Walking into town is supposed to do both of those; a battle screen
 * quietly doing it to light up a sprite would heal the player at the start of
 * every fight and flatten the whole upkeep loop. The encounter payload now
 * carries `alarm` for exactly this reason.
 *
 * So every alarm this client draws was handed to it by a door the player
 * actually opened: entering an encounter, a graded submission, the Mender, a
 * hidden healer, the square. When the last one it was given does not describe
 * the health on screen — a reload at low health, before the first cast — it
 * draws nothing rather than guessing, because guessing means a copy of
 * ALARM_BANDS living here, and then the pulse and the bar have two opinions
 * about when things got bad. */
function ensureAlarm() {
  const p = (G.state || {}).player;
  const a = G.alarm;
  if (!p || !a) { paintAlarm(); return; }
  if (a.health !== p.stamina || a.health_max !== p.stamina_max) {
    // Stale. Health only moves through doors that hand one of these back, so
    // the next cast replaces it; until then the sprite says nothing, which is
    // the honest reading of "nobody has told us".
    G.alarm = null;
  }
  paintAlarm();
}

/* One status, with the turns it has left. The name, the duration and the
 * sentence under it are elements.py's; this adds nothing to them. */
function statusChip(row) {
  const spec = wheelStatus(row.id) || {};
  const art = wheelElement(spec.element) || {};
  const colour = art.colour || 'var(--ink-dim)';
  const stacks = (row.stacks || 1) > 1 ? ` ×${row.stacks}` : '';
  const title = spec.blurb
    ? `${spec.name} — ${spec.blurb} ${row.turns} turn(s) left.`
    : `${row.id} · ${row.turns} turn(s) left`;
  return `<span class="chud-stat" style="color:${colour}" title="${attr(title)}">
    ${(spec.name || row.id).toUpperCase()}${stacks} <b>${row.turns}</b></span>`;
}

/* The single fact the player has to be able to read off this strip: how much of
 * the fight is their element's doing. The label is the server's word for the
 * matchup — elements.MATCHUP_LABEL — and the multiplier is its own number. */
function matchupHtml(elt, sealed) {
  if (!elt) return '';
  const mine = wheelElement(elt.player);
  const theirs = elt.enemy ? wheelElement(elt.enemy) : null;
  const kind = elt.matchup || '';
  const m = wheelMatchup(kind);
  if (!theirs || !theirs.id) {
    // Two different silences again. Under the seal the element is still there
    // and still multiplying — the reading is what was taken, not the mechanic —
    // and saying "nothing here to read" instead would be the interface telling
    // the player the fight got simpler when it did not.
    if (sealed) {
      return '<span class="muted">It is made of something. You are not being '
        + 'told what, and it still counts.</span>';
    }
    return `<span class="muted">${mine && mine.id
      ? `${mine.name} · nothing here to read` : 'no element'}</span>`;
  }
  const colour = m && (kind === 'OPPOSED' ? 'var(--green)'
    : kind === 'SAME' ? 'var(--red)'
    : kind === 'SECONDARY' ? 'var(--blue)'
    : kind === 'WEAK_INTO' ? 'var(--orange)' : 'var(--ink-dim)');
  return `<span style="color:${mine.colour}">${mine.rune || ''} ${mine.name}</span>
    <span class="muted"> into </span>
    <span style="color:${theirs.colour}">${theirs.rune || ''} ${theirs.name}</span>
    <br><span style="color:${colour}">${m ? m.label.toUpperCase() : kind}
    ${m ? `×${m.multiplier.toFixed(2)}` : ''}</span>`;
}

/* The belt. Every potion the player is carrying, what it would restore RIGHT
 * NOW — the falloff is already folded into `would_restore` by potions.py — and
 * for anything greyed out, the sentence saying why. A disabled button with no
 * reason is how a player concludes a mechanic is broken, which is why
 * potions.pouch_view ships `reason` next to `usable` and why it is rendered
 * here rather than inferred. */
function paintBelt(host, pouch) {
  host.innerHTML = '';
  const rows = (pouch && pouch.potions) || [];
  if (!rows.length) {
    host.appendChild(el('span', 'chud-empty',
      'Nothing on the belt. Monsters drop them and chests hold them; the '
      + 'deeper the room, the deeper the vessel.'));
    return;
  }
  for (const p of rows) {
    const btn = el('button', `potion${p.usable ? '' : ' off'}`,
      `<span class="pn" style="color:${p.colour}">${p.kind_label.toUpperCase()}</span>
       <span class="pv">${p.strength}</span>
       <span class="ph">×${p.held}${p.would_restore ? ` · +${p.would_restore}` : ''}</span>`);
    btn.title = p.usable
      ? `${p.name} — ${p.flavour || ''}${p.would_restore
          ? `\nRestores ${p.would_restore} now.` : ''}`
        + `\n${p.next_multiplier < 1
          ? `The ${Math.round(p.next_multiplier * 100)}% band — you have had `
            + 'one of these already this fight.' : 'Full band.'}`
        + '\nDrinking does not spend your turn.'
      : `${p.name} — ${p.reason}`;
    btn.disabled = !p.usable;
    if (p.usable) btn.onclick = () => drinkPotion(p, btn);
    host.appendChild(btn);
  }
}

/* Drink. THE WHOLE POINT OF THIS FUNCTION is what it does not do: it does not
 * submit, it does not end the turn, and it does not re-enable the CAST button
 * because the CAST button was never disabled. The server says so in two fields
 * and both of them are shown rather than paraphrased. */
async function drinkPotion(p, btn) {
  btn.disabled = true;
  let r;
  try {
    r = await api.potion(p.id);
  } catch (e) {
    btn.disabled = false;
    toast('THE STOPPER STICKS', e.message, 'red');
    return;
  }
  if (!r || !r.ok) {
    // Every refusal has a sentence attached — sealed, already drunk this turn,
    // nothing to cure, already full. Show the sentence.
    toast(r && r.error === 'sealed' ? sealedTitle(r) : 'SHE KEEPS IT CORKED',
          (r && r.message) || 'Not that one, not now.', 'red');
    if (r && r.pouch) paintBelt($('#chud-belt'), r.pouch);
    return;
  }
  audio.sfx('unlock');
  if (G.fx) {
    try {
      G.fx.drink({ colour: p.colour, amount: r.restored || 0, name: p.kind_label });
    } catch (e) { /* the draught still went down */ }
  }
  await refresh();
  // `must_still_cast` is potions.drink's own field and this is the one line of
  // interface the rule gets. It is a toast rather than a modal on purpose: a
  // modal would be a pause, and a pause is the first half of an inventory game.
  toast('DOWN IT GOES', `${r.prompt || ''} ${r.applied.join(' ')}`, 'green');
  // The belt, the statuses and the dose pool all moved. Repaint from the
  // server's answer rather than from what we think happened.
  paintCombatHud({
    ...(G.hud || {}),
    pouch: r.pouch,
    statuses: r.statuses || (G.hud || {}).statuses,
    drunk: r.id,
  });
}

/* Normalise the two payload shapes into one. An encounter payload and the
 * result of a graded submission carry the same keys for all of this — the
 * engine ships `turn`, `statuses`, `enemy_statuses`, `enemy_vitals`, `element`
 * and `pouch` on both — which is what lets one painter serve the whole fight. */
function paintCombatHud(view) {
  if (!view) { hideCombatHud(); return; }
  const node = ensureCombatHud();
  node.classList.add('on');
  G.hud = view;

  const p = (G.state && G.state.player) || {};
  const hp = Math.max(0, p.stamina || 0), hpMax = Math.max(1, p.stamina_max || 1);
  const fp = Math.max(0, p.mana || 0), fpMax = Math.max(1, p.mana_max || 1);
  const elt = view.element || {};
  const mine = wheelElement(elt.player);

  $('#chud-you-name').innerHTML = `YOU${mine && mine.id
    ? `<span class="chud-el" style="color:${mine.colour}">${mine.rune || ''} ${
        mine.name.toUpperCase()}</span>` : ''}`;
  $('#chud-you-hp').style.width = `${(hp / hpMax) * 100}%`;
  $('#chud-you-hp-v').textContent = `${hp} / ${hpMax}`;
  $('#chud-you-fp').style.width = `${(fp / fpMax) * 100}%`;
  $('#chud-you-fp-v').textContent = `${fp} / ${fpMax}`;
  $('#chud-you-stats').innerHTML = (view.statuses || []).map(statusChip).join('')
    || '<span class="chud-empty">nothing on you</span>';

  // THEM. `enemy_vitals` is bestiary.vitals(): a real health pool and a real
  // focus pool, which are what the fight looks like — neither is sealed, because
  // neither is a reading of the answer. The element beside the name IS sealed,
  // and the engine has already emptied it when it is.
  const v = view.enemy_vitals || {};
  // An empty element means one of two different things and they must not read
  // alike: either this creature is not made of anything — five of the seventeen
  // regions are neutral on purpose — or the run is measured and the reading has
  // been taken away. The engine empties the field in both cases; the seal is
  // what tells them apart.
  const theirs = elt.enemy ? wheelElement(elt.enemy)
    : (view.sealed_element ? null : ((G.wheel || {}).neutral || null));
  const ehp = Math.max(0, v.hp || 0), ehpMax = Math.max(1, v.hp_max || 1);
  const efp = Math.max(0, v.focus || 0), efpMax = Math.max(1, v.focus_max || 1);
  const name = (view.enemy_name || 'IT').toUpperCase();
  $('#chud-them-name').innerHTML = `${name}${theirs
    ? `<span class="chud-el" style="color:${theirs.colour}">${theirs.rune || ''} ${
        theirs.name.toUpperCase()}</span>`
    : '<span class="chud-el" style="color:var(--ink-faint)" title="A measured '
      + 'run is not given readings. It still has an element and it still '
      + 'multiplies; you are simply not told which.">? UNREADABLE</span>'}`;
  $('#chud-them-hp').style.width = `${(ehp / ehpMax) * 100}%`;
  $('#chud-them-hp-v').textContent = `${ehp} / ${ehpMax}`;
  // A fight whose other side has no focus pool — an incantation field is names
  // rather than a creature — says so rather than drawing an empty gauge and
  // letting the player wonder what is meant to fill it.
  const hasFocus = !!v.focus_max;
  $('#chud-them-fp').style.width = hasFocus ? `${(efp / efpMax) * 100}%` : '0%';
  $('#chud-them-fp-v').textContent = hasFocus ? `${efp} / ${efpMax}` : '—';
  // What it is saving up for, and the line on the gauge where it can afford it.
  // bestiary.take_turn will not always fire once it can — an enemy that always
  // spent would be a metronome, and a metronome is something the player stops
  // reading — so this is a warning rather than a countdown, which is the
  // honest way to draw it.
  const specials = (v.specials || []).map(wheelSpecial).filter(Boolean)
    .sort((a, b) => a.cost - b.cost);
  const saving = specials.find(sp => sp.cost > efp) || specials[0] || null;
  const mark = $('#chud-them-fp').parentNode;
  const oldMark = mark.querySelector('.mk');
  if (oldMark) oldMark.remove();
  if (saving && hasFocus && saving.cost <= efpMax) {
    const pin = el('span', 'mk');
    pin.style.left = `${(saving.cost / efpMax) * 100}%`;
    pin.title = `${saving.name} costs ${saving.cost} focus.`;
    mark.appendChild(pin);
  }
  $('#chud-them-stats').innerHTML =
    ((view.enemy_statuses || []).map(statusChip).join('')
      || '<span class="chud-empty">nothing on it</span>')
    + (saving ? `<span class="chud-stat" style="color:${
        (wheelElement(saving.element) || {}).colour || 'var(--gold-hi)'}"
        title="${attr(saving.line.replace('{who}', name) + ' ' + saving.why)}">${
        efp >= saving.cost ? 'CAN AFFORD' : 'SAVING FOR'} ${
        saving.name.toUpperCase()} <b>${saving.cost}</b></span>` : '');

  // `turn` is already the CURRENT turn on both payloads — Encounter.turn starts
  // at one and potions.cast_resolved is the only thing that moves it. The
  // pouch's own copy is preferred because it is the counter the belt's one-per-
  // turn rule is measured against, and those two must never disagree on screen.
  $('#chud-turn-n').textContent =
    `TURN ${(view.pouch || {}).turn || view.turn || 1}`;
  // Whose turn it is, and it is almost always the player's: the enemy acts once,
  // in response to a missed cast, and then the turn comes straight back. Saying
  // so is how a player learns that the fight waits for them and the clock does
  // not — which is the difference between pressure and panic.
  const drunk = (view.pouch || {}).may_drink === false;
  $('#chud-turn-w').textContent = view.theirs ? 'THEIRS' : 'YOURS — CAST';
  $('#chud-turn-w').style.color = view.theirs ? 'var(--orange)' : 'var(--green)';
  $('#chud-match').innerHTML = matchupHtml(elt, view.sealed_element);

  // What the enemy just did. Without this a player watching their own bar drop
  // has no way to tell a special from a status from an ordinary swing, and
  // "it just kills me sometimes" is the review that follows.
  const said = $('#chud-said');
  const lines = view.said || [];
  if (lines.length) {
    said.style.display = '';
    said.innerHTML = lines.map(l => `<div>${l}</div>`).join('');
  } else {
    said.style.display = 'none';
    said.innerHTML = '';
  }

  // The alarm rides on the same repaint as the bars, because it is a reading of
  // the same number. `ensureAlarm` only reaches for the wire when the health it
  // was last told about is not the health on screen.
  ensureAlarm();

  paintBelt($('#chud-belt'), view.pouch);
  const pouch = view.pouch || {};
  $('#chud-rule').innerHTML = pouch.sealed
    ? 'The belt is sealed for this run. What you can survive is what you '
      + 'brought in your head.'
    : `<b>${pouch.rule || 'A draught is free. A second draught costs a cast.'}</b>
       ${drunk ? ' You have drunk this turn — the cast is still yours.'
               : ' Drinking does not spend your turn; only a graded cast does.'}
       ${(view.hazard && view.hazard.name)
         ? `<br>${view.hazard.name}: ${view.hazard.blurb}` : ''}`;
}

/* The encounter payload, as the HUD reads it. */
function hudFromPayload(payload) {
  const elt = payload.element || {};
  return {
    turn: payload.turn || 0,
    statuses: payload.statuses || [],
    enemy_statuses: payload.enemy_statuses || [],
    enemy_vitals: payload.enemy_vitals || {},
    enemy_name: (payload.enemy || {}).name || '',
    element: {
      player: elt.player || '',
      enemy: elt.enemy || '',
      region: elt.region || '',
      // The encounter payload ships the enemy's element but not the matchup —
      // it is the one number the client can work out for itself, from a table
      // the server also sent. Anything else would be a second opinion.
      matchup: matchupKind(elt.player, elt.enemy),
    },
    sealed_element: !!(payload.seal && (payload.seal.sealed || []).includes('WEAKNESS_MAP')),
    hazard: (elt.hazard && elt.hazard.id) ? elt.hazard : null,
    pouch: payload.pouch || {},
    said: [],
    theirs: false,
  };
}

/* elements.matchup, client side, off the table the server sent. The five kinds
 * and the three pairs are elements.py's; this walks them and invents nothing.
 * Unknown and empty both resolve to NEUTRAL rather than throwing, for the same
 * reason elements.matchup does: an unelemented enemy is a normal thing and a
 * crash mid-fight is not. */
function matchupKind(attacker, defender) {
  const w = G.wheel || {};
  const a = attacker && (w.opposed || {})[attacker] !== undefined ? attacker : '';
  const d = defender && (w.opposed || {})[defender] !== undefined ? defender : '';
  if (!a || !d) return 'NEUTRAL';
  if ((w.opposed || {})[a] === d) return 'OPPOSED';
  if (a === d) return 'SAME';
  if ((w.secondary || {})[a] === d) return 'SECONDARY';
  if ((w.secondary || {})[d] === a) return 'WEAK_INTO';
  return 'NEUTRAL';
}

/* The result of a graded submission, as the HUD reads it. The difference from
 * the payload is the narration: `enemy_turn` and `turn_open` say what the other
 * side did and what the player's new turn opened with, and both go in `said`. */
function hudFromResult(result) {
  const elt = result.element || {};
  const et = result.enemy_turn || null;
  const open = result.turn_open || null;
  const said = [];
  if (et) {
    if (et.special) {
      said.push(`<b>${et.special.name.toUpperCase()}</b> — ${
        et.special.line.replace('{who}', (result.enemy || {}).name || 'It')}
        <span class="muted">(${et.special.cost} focus)</span>`);
    }
    if (et.cured) {
      said.push(`<b>IT DRANK</b> — ${et.cured.line} <span class="muted">${
        et.cured.aside || ''}</span>`);
    }
    // Everything the turn said EXCEPT the blow's own line, which is
    // elements._damage_line and opens with the bare number — printed as-is it
    // reads as a stray "2." above a sentence that says two again.
    const hitLine = (et.hit || {}).line || '';
    for (const line of et.lines || []) {
      if (line !== hitLine) said.push(line);
    }
    if (et.damage) {
      // The number, then whatever the wheel and the armour had to say about it:
      // "4 off your health — a counter, 2 stopped by plate, burning."
      const extra = hitLine.replace(/^\d+,?\s*/, '').replace(/\.$/, '').trim();
      said.push(`<b>${et.damage}</b> off your health${extra ? ` — ${extra}` : ''}.`);
    }
  }
  if (open) {
    for (const line of open.lines || []) said.push(line);
    if (open.regen_blocked) {
      said.push('<b>No focus returned</b> — something is holding it shut.');
    } else if (open.focus_regained) {
      said.push(`+${open.focus_regained} focus as your turn opened.`);
    }
  }
  return {
    turn: result.turn || 0,
    statuses: result.statuses || [],
    enemy_statuses: result.enemy_statuses || [],
    enemy_vitals: result.enemy_vitals || {},
    enemy_name: (result.enemy || {}).name || (G.hud || {}).enemy_name || '',
    element: {
      player: elt.player || '',
      enemy: elt.enemy || '',
      region: elt.region || '',
      // The engine names the matchup itself on the way out. Preferred over the
      // client's own walk of the table, because on a sealed run it is the one
      // that knows what was withheld.
      matchup: elt.matchup || matchupKind(elt.player, elt.enemy),
    },
    sealed_element: !!(G.hud || {}).sealed_element,
    hazard: (G.hud || {}).hazard || null,
    pouch: result.pouch || (G.hud || {}).pouch || {},
    said,
    theirs: false,
  };
}

/* The exchange, on the stage. Everything below is playback: the numbers were
 * decided by elements.resolve_damage before this function was called, and a
 * cast that landed nothing plays as nothing landing. */
async function playElementalExchange(result, fb) {
  if (!G.fx) return;
  // The beats between the fx module's own awaits. Short, and shorter still when
  // the player has asked for less movement — a pause is movement's pacing, and
  // holding one for somebody who turned the movement off is just a delay.
  const reduced = !!(G.state && G.state.settings.reduced_motion);
  const beat = (ms) => new Promise(r => setTimeout(r, reduced ? 0 : ms));
  const elt = result.element || {};
  const kind = elt.matchup || matchupKind(elt.player, elt.enemy);
  const m = wheelMatchup(kind);

  // The player's blow, with the element on it. No damage number — the trials
  // have already counted the hits and a second total would be two truths about
  // one exchange. What this adds is the READING: what the element did, in the
  // element's own motion, scaled by the multiplier the server applied.
  if (fb.passed > 0 && elt.player && elt.enemy) {
    await G.fx.elemental({
      element: elt.player,
      multiplier: m ? m.multiplier : 1,
      kind, damage: 0, side: 'enemy',
      label: m ? m.label : '',
    });
  }

  // Its turn. `hit` is elements.DamageResult.to_dict() straight off the wire,
  // which is every number this needs and none it has to work out.
  const et = result.enemy_turn;
  if (et && et.acted) {
    if (et.special) {
      G.fx.statusTick({ status: et.special.name, element: et.special.element,
                        damage: 0, side: 'enemy', label: et.special.name });
      await beat(220);
    }
    const hit = et.hit || {};
    if (et.damage || hit.damage) {
      await G.fx.elemental({
        element: hit.attacker_element || (result.enemy_vitals || {}).element || '',
        multiplier: hit.multiplier !== undefined ? hit.multiplier : 1,
        kind: hit.kind || 'NEUTRAL',
        damage: et.damage || hit.damage || 0,
        label: hit.label || '',
        side: 'hero',
        absorbed: hit.armour_absorbed || 0,
        resisted: hit.resisted || 0,
      });
    }
    if (et.inflicted) {
      const spec = wheelStatus(et.inflicted) || {};
      G.fx.statusTick({ status: et.inflicted, element: spec.element,
                        damage: 0, side: 'hero', label: spec.name || et.inflicted });
    }
  }

  // The tick that opens the player's next turn. Poison has to be VISIBLE on the
  // victim or the bar appears to drop on its own, and a bar that drops on its
  // own is a game that appears to cheat.
  const open = result.turn_open;
  if (open && open.damage) {
    const carried = (result.statuses || [])[0] || {};
    const spec = wheelStatus(carried.id) || {};
    G.fx.statusTick({ status: carried.id || 'POISONED',
                      element: spec.element || 'POISON',
                      damage: open.damage, side: 'hero',
                      label: spec.name || '' });
    await beat(260);
  }
}

function renderPuzzle(p) {
  $('#editor-host').style.display = 'none';
  setEditorMode('puzzle');
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

/* THE CHOICES ARE THE ENCOUNTER, so they cannot live in a node somebody else
 * owns. They used to be appended straight into #battle-side-body — which
 * `setTab` empties on every call — and `enterBattle` calls `setTab` four lines
 * after rendering the problem. The result was the FIRST ENCOUNTER OF A NEW GAME
 * showing its question, hiding the CAST button (correctly: the answers are the
 * button), and offering nothing to click. Clicking any tab did the same thing.
 *
 * So the choices are registered as what the trials tab IS for this encounter,
 * and repainting is now what restores them rather than what destroys them. */
function renderMcq(p) {
  $('#editor-host').style.display = 'none';
  // No editor and no CAST: the pane says where the answers are instead of
  // sitting there as an empty black rectangle.
  setEditorMode('mcq');
  $('#btn-run').style.display = 'none';
  // The answers ARE the choices. Leaving a primary submit button on screen
  // just offers a way to fail an encounter without answering it.
  $('#btn-submit').style.display = 'none';
  G.mcq = p.mcq;
  setTab('trials');
}

/* Painted by setTab, so it survives a tab round-trip and the repaint at the
 * end of enterBattle. */
function paintMcq(body) {
  const mcq = G.mcq;
  if (!mcq) return;
  if (mcq.code) body.appendChild(el('pre', 'spell-body', mcq.code));
  (mcq.choices || []).forEach((choice, i) => {
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
  // An MCQ owns the trials slot: there are no trials to show, and the choices
  // are the only way to answer the encounter.
  if (G.mcq && tab === 'trials') { paintMcq(body); return; }
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
  /* A forged blade is drawn from a different table at a different size —
   * lootart.drawItem routes it there on its own, and a 24-pixel canvas would
   * clip the top quarter off every rung above five. */
  const px = lootart.isForged(item) ? lootart.FORGE_SIZE : lootart.ITEM_SIZE;
  canvas.width = px;
  canvas.height = px;
  canvas.style.width = size + 'px';
  canvas.style.height = size + 'px';
  canvas.style.imageRendering = 'pixelated';
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const forged = lootart.forgeOf(item);
  const frames = forged
    ? lootart.forgeFrameCount(forged.tier, forged)
    : lootart.itemFrameCount(item);
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
      Probes, items and gear effects are all withheld in Interview Mode — the
      forged blade among them, technique and all. What you bring to a real
      screen is what you know.</div>`));
    return;
  }

  const t = G.encounter.tactics || {};
  const charges = G.probeCharges !== undefined
    ? G.probeCharges : (G.encounter.probe_charges || 0);

  body.appendChild(el('div', 'muted small', t.advice || ''));

  // The blade in your hand, and what its technique is buying you in THIS fight.
  // It is stated here rather than only on the gear screen because this is the
  // panel a player reads while deciding how to open, and a technique that
  // changes how you engage is no use if you find out about it afterwards.
  const blade = (G.state && G.state.forge) || {};
  if (blade.tier && blade.technique) {
    ensureForgeStyle();
    body.appendChild(el('div', 'section-title', 'YOUR BLADE'));
    body.appendChild(el('div', 'frame', `<div style="padding:10px">
      <div class="forge-tech">${blade.technique.rank}</div>
      <div class="small" style="color:var(--green);line-height:1.6">
        ${blade.technique.text}</div>
      <div class="small muted" style="margin-top:6px">${
        (blade.item && blade.item.name) || ''} · rung ${blade.tier} of 9.
        It changes what you can ask and how long you have. It does not know the
        answer and never will.</div></div>`));
  }

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
        // A rung the companion in the field cannot read is NOT a seal and NOT
        // an empty focus bar, and toasting it as either would teach the player
        // the wrong thing about a system whose entire point is the distinction.
        // partyui draws the refusal with the roads out attached.
        if (r.error === 'above_tier') { partyui.showHintRefusal(r); return; }
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
  /* AND GIVE THE CARET BACK. Disabling a button that holds focus drops focus to
   * <body>, and re-enabling it does not bring it back: measured, a mouse-click
   * RUN left activeElement BODY, #editor-host outline `none`, #editor-pane
   * without its `typing` class, and the next seventeen typed characters grew
   * the buffer by zero. write → RUN → keep writing is the most common loop in a
   * code fight. closeModal() already does this, which is the only reason CAST
   * recovers. No guard: nothing was talking over the screen, the player is
   * mid-sentence, and a space here is a space they meant. */
  focusEditor({ keepSelection: true, guard: false });
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
      // The technique opens the exchange, because the technique IS the cast.
      // What it BUYS — another probe, a longer clock, a ward — was resolved
      // server-side through the same effect path items and class nodes already
      // use, and none of that is rendered here. What is rendered is the swing,
      // and the swing is scaled entirely by the rung: a tier-eight blade is
      // bigger, brighter, shakes harder and holds the impact frame four times
      // as long as a tier-one one.
      const blade = (G.state && G.state.forge) || {};
      if (blade.tier && blade.item && G.encounter.mode !== 'interview') {
        await G.fx.technique({
          tier: blade.tier,
          // The name only slams up when the blow actually landed on something.
          // A technique announcing itself over a cast that passed no trial at
          // all is the game congratulating you for nothing.
          name: fb.passed > 0 ? ((blade.technique || {}).name || '') : '',
          rank: (blade.technique || {}).rank || '',
          colour: (blade.item.forge || {}).accent || blade.item.rarity_colour,
          accent: blade.item.rarity_colour,
          crit: !!(result.combat && result.combat.crits.length),
        });
      }
      await G.fx.resolveTrials(trialsFromFeedback(fb, result.combat), {});
      G.fx.setEnemyHp(Math.max(0, fb.total - fb.passed), fb.total);
      // The wheel's half of the exchange, after the trials and before the
      // close: what the element did to the blow, what the enemy spent its focus
      // on, and the tick that opened the next turn. Playback only — every one
      // of those numbers was decided server-side before this ran.
      await playElementalExchange(result, fb);
      /* THE PHASE TURN, BEFORE THE VICTORY FANFARE AND INSTEAD OF IT.
       *
       * A phase falling is not a win — the thing is still standing and about
       * to be harder — so playing `victory()` here would be the game
       * congratulating the player for a third of a fight. The beat plays in
       * its place: freeze, flash, the silhouette changes under the white, the
       * boss speaks, and then one sentence saying what just got worse. */
      if ((result.boss || {}).advanced) await playPhaseTurn(result);
      else if (result.solved) await G.fx.victory({ rank: result.rank, xp: result.xp,
                                                   loot: result.loot });
      else await G.fx.defeat({ cause: (result.analysis || {}).root_cause });
    } catch (err) { /* the report must appear even if the animation cannot */ }
  }
  // Outside the try: the numbers must land on the strip whether or not the
  // stage managed to animate them. This is the screen a player reads to find
  // out why they are losing, and an exception in a particle effect is not a
  // reason to withhold it.
  if (G.encounter) paintCombatHud(hudFromResult(result));

  // -- upkeep, the hunt, and the six systems that pay out on a clear --------
  //
  // Every one of these arrived on the result payload the engine already built.
  // None of them is a second request and none of them is a second opinion: the
  // alarm is upkeep's, the hunt row is the chase's own next state, and the
  // rest are discoveries the engine made while resolving this encounter.
  noteAlarm(result.alarm);
  // DEATH SHORT-CIRCUITS THE REST OF THE RESULT. Everything below this line
  // reports on a game that death.py has already rewound — spoils from a fight
  // that no longer happened, a hunt row for a chase that was rolled back. The
  // engine hands `death` back only when it actually killed somebody.
  if (result.death) { await playDeath(result.death); return; }
  huntui.noteResult(result, G.huntRegion,
    (G.encounter || {}).mode === 'interview');
  noteWorldSpoils(result);

  if (result.solved) {
    audio.sfx(result.rank === 'S' ? 'victory' : 'crit');
    // After the spoils have been counted, so the rank it names is the one the
    // player just earned rather than the one they walked in with.
    if (isClutchClear(result)) {
      await playTransformation((G.state.player || {}).title);
    }
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
  html += metalHtml(result.metal);
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
    html += bossReport(result.boss);
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
  /* The barrow goes FIRST, before any meeting. It is the only thing this game
   * takes away, it happens inside the fight the report is describing, and it
   * has to be the next thing on screen rather than something the player finds
   * out about later on the companion page. If it is missed anyway — a refresh
   * between the fight and the modal — the server hands it back on every
   * catalogue read until partyui acknowledges it, so it cannot be lost. */
  let fall = result.companion_fell || null;
  const afterReport = (then) => {
    if (fall) {
      const scene = fall; fall = null;
      partyui.showTheFall(scene, { onClose: () => afterReport(then) });
      return;
    }
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
  if (result.boss && !result.boss.defeated && !result.boss.advanced) {
    paintBossTeaching(m, result.boss);
  }
  // The one button that did not exist before there were phases: the way back
  // into a fight that is only partly won.
  const next = m.querySelector('[data-boss-next]');
  if (next) next.onclick = () => faceNextPhase(next.dataset.bossNext);
  // Over the kill and over the key, after the report is on screen rather than
  // instead of it.
  if (result.boss) heWatches(result.boss.watching);
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
  if (result.metal) {
    audio.sfx('unlock');
    toast('METAL', `${result.metal.units} ${result.metal.name} — ${
      result.metal.held} in the bag.`, 'gold');
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

/* What this encounter paid into the world that nothing was drawing. All six
 * arrive on the result the engine already built; none of them costs a request,
 * and none of them is worth a modal — a modal here is a pause between the
 * player and the next problem, and the next problem is the game. */
function noteWorldSpoils(result) {
  const trial = result.trial;
  if (trial && trial.counted) {
    toast('ORIN TALLOW WEIGHS IT',
      `${trial.done || 0} of ${trial.need || 0} on the contract.${
        trial.failed ? ' That one went against you.' : ''}`,
      trial.failed ? 'red' : 'gold');
  }
  for (const row of (result.found_regalia || [])) {
    audio.sfx('unlock');
    toast('★ REGALIA', `${row.name || row.regalia} — it buys how soon and how `
      + 'often, never how deep.', 'violet');
  }
  for (const row of (result.found_sages || [])) {
    audio.sfx('levelup');
    toast('SOMEBODY WAS WATCHING',
      `${row.name || row.sage} will see you now. Their trial is a ladder of `
      + 'real problems and the art is behind the last rung.', 'violet');
  }
  // The overworld sanctuary tell: two regions have no dungeon to hide a healer
  // in, so out there a hurt traveller simply finds the tent. `tell` is the only
  // field that means anything — the blank row comes back everywhere else.
  const tent = result.sanctuary;
  if (tent && tent.tell) {
    toast('SOMETHING IN THE TREE LINE', tent.tell, 'green');
    G.sanctuaryTell = tent;
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
  /* The emote rides on the story entry when the writing supplies one, and
   * EMOTE_ALIAS in sprites.js already translates the words writing actually
   * uses ("happy", "grim", "shock") into the seven this game draws. A milestone
   * with nothing to say about its own tone is PLEASED, because that is what a
   * milestone is. */
  const tone = entry.emote || entry.tone
    || (entry.kind === 'milestone' ? 'pleased' : 'neutral');
  say(String(speaker).toUpperCase(), lines, portraitKind, tone);
  return true;
}

function returnToWorld() {
  clearInterval(G.timer);
  stopViz();
  // IncantationUI holds #puzzle-host, a document key listener and its own
  // clock. Leaving the screen without destroying it leaks all three.
  destroyIncant();
  destroyChild();
  destroyRepo();
  // The companion card belongs to the fight, not to the screen behind it.
  partyui.clearIntervention();
  if (G.fx) G.fx.stop();
  // The strip belongs to the fight. Left up, it goes on showing the last
  // enemy's focus bar over an overworld screen. hideCombatHud also stops the
  // heartbeat and takes the red wash off the sprite.
  hideCombatHud();
  // A rung of a sage's gauntlet that was opened from the trial screen is
  // settled HERE, on the way out, and it is settled by asking the server what
  // the record says. The client does not get to assert that it passed.
  legendui.settlePendingRung().catch(() => {});
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
  setEditorMode('incant');
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
  paintCombatHud(hudFromIncant(payload));
  setTab('trials');
  show('battle');
  audio.play('battle');
}

/* An incantation field, as the HUD reads it. The same strip, because it is the
 * same fight: the enemy is a bound name instead of a creature, but the player's
 * two bars, the statuses riding on them and the belt are identical — and the
 * turn rule is identical too, which is the reason not to build a second one. */
function hudFromIncant(payload) {
  const inc = payload.incantation || {};
  const elt = inc.element || {};
  const alive = (inc.enemies || []).filter(e => e.alive);
  return {
    // ctx.turn counts resolved casts from zero; every other turn number in this
    // client is one-based. Normalised here so the strip never has two rules.
    turn: (inc.turn || 0) + 1,
    statuses: inc.statuses || [],
    enemy_statuses: [],
    // The field, as one health pool. Every name on it is a separate target and
    // the side panel lists them individually; this is the "how much is left"
    // number, which is the one a bar is for.
    enemy_vitals: {
      hp: alive.reduce((a, e) => a + (e.hp || 0), 0),
      hp_max: (inc.enemies || []).reduce((a, e) => a + (e.hp_max || 0), 0) || 1,
      focus: 0, focus_max: 0,
    },
    enemy_name: `THE FIELD · ${alive.length} STANDING`,
    element: {
      player: elt.player || '',
      // A name is not made of anything. The region still is, and that is what
      // the strip reports here rather than inventing an element for a variable.
      enemy: '',
      region: elt.region || '',
      matchup: 'NEUTRAL',
    },
    sealed_element: false,
    hazard: null,
    pouch: payload.pouch || {},
    said: (inc.log || []).slice(-3),
    theirs: false,
  };
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
  // A field battle can kill you too, and it ends the same way a fight does.
  // Asked before anything paints: the bars below would be drawn from a run that
  // death.py has already rolled back.
  if (r.death) {
    await playDeath(r.death);
    return { ok: false, layer: 'semantics', detail: 'You fell.', teach: '' };
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
  // The strip moves with the fight: the field's log is what the other side just
  // did, and the belt's lock cleared the moment this cast resolved.
  paintCombatHud(hudFromIncant({ incantation: inc, pouch: r.pouch }));

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

/* ---------------- mini-repo battles ---------------- */

/* The screen is built here rather than in index.html because the Mini-Repo owns
 * the whole viewport while it is running — a tree, tabs, an editor and a suite
 * do not fit in the battle screen's side panel, and pretending otherwise is how
 * this ends up feeling like a quiz again. */
function ensureRepoScreen() {
  let node = $('#screen-repo');
  if (node) return node;
  node = el('section', 'screen');
  node.id = 'screen-repo';
  node.innerHTML = '<div id="repo-host" style="display:flex;flex:1;min-height:0"></div>';
  $('#app').appendChild(node);
  return node;
}

function destroyRepo() {
  if (!G.repo) return;
  const ui = G.repo;
  G.repo = null;
  G.repoPayload = null;
  try { ui.destroy(); } catch (e) { /* a destroyed panel is still destroyed */ }
}

/* The board. Sixteen repositories, what each one costs in minutes, and which
 * ones have already been handed back green. */
async function paintRepos() {
  const board = (G.state.mini_repos || { repos: [] });
  const openId = G.state.active_encounter && G.state.active_encounter.repo_id;
  const open = openId
    && ((board.repos || []).find(r => r.id === openId) || { title: openId }).title;
  panel('MINI-REPO BATTLES', `
    <p class="small muted">${board.blurb || ''}</p>
    ${open ? `<div class="frame" style="padding:12px;margin-bottom:12px">
      <div class="section-title">A REPOSITORY IS OPEN</div>
      <p class="small">You are part-way through <b>${open}</b>. The clock has not
      stopped and your edits are where you left them.</p>
      <button class="btn primary" id="repo-resume">GO BACK TO IT</button>
      <button class="btn" id="repo-abandon">PUT IT DOWN</button>
    </div>` : ''}
    <div class="list-item" id="repo-measured" style="margin-bottom:10px">
      <span class="t">MEASURED: <b id="repo-measured-state">OFF</b></span>
      <span class="d">Turn this on and the next repository you open is a
        practical rather than a lesson: no pointer at the file to start in, no
        task shapes, no list of which tests are the targets, no companion, and
        a clock that is running whether or not you are typing. Nothing is
        taught while it is on — which is what makes the result mean something.
      </span>
    </div>
    <div class="grid2" id="repo-list"></div>
    <p class="small muted" style="margin-top:12px">A Mini-Repo has no spells, no
    probes and no worked solution while it is running. It does not need them:
    nothing is hidden from you, the suite can be run as often as you like, and
    the debrief afterwards always names the lesson and the file it lived in —
    including when the attempt fails.</p>`);
  const host = $('#repo-list');
  for (const card of board.repos || []) {
    const row = el('div', 'list-item',
      `<span class="t">${card.cleared ? '✔ ' : ''}${card.title}</span>
       <span class="d">${(card.shapes || []).join(' · ').replace(/_/g, ' ').toLowerCase()}
         <br><span class="muted small">${card.difficulty} · ${card.files} files ·
         ${Math.round(card.target_seconds / 60)} min · ${(card.tags || []).join(', ')}</span>
       </span>`);
    row.onclick = () => startRepo(card.id, G.repoMeasured ? 'interview' : 'adventure');
    host.appendChild(row);
  }
  const measured = $('#repo-measured');
  const state = $('#repo-measured-state');
  state.textContent = G.repoMeasured ? 'ON' : 'OFF';
  state.style.color = G.repoMeasured ? 'var(--red)' : '';
  measured.onclick = () => {
    G.repoMeasured = !G.repoMeasured;
    state.textContent = G.repoMeasured ? 'ON' : 'OFF';
    state.style.color = G.repoMeasured ? 'var(--red)' : '';
    audio.sfx('select');
  };
  const resume = $('#repo-resume');
  if (resume) resume.onclick = () => openRepo();
  const abandon = $('#repo-abandon');
  if (abandon) {
    abandon.onclick = async () => {
      const r = await api.leaveRepo();
      toast('PUT DOWN', r.message || 'Nothing was graded.', '');
      await refresh();
      paintRepos();
    };
  }
}

/* Open one. `mode` is 'adventure' unless the player deliberately asks to be
 * measured, in which case the server takes the pointer, the shapes, the target
 * list and the companion away — through finalexam.sealed(), like everything
 * else that Interview Mode takes. */
async function startRepo(repoId, mode = 'adventure') {
  const payload = await api.startRepo(repoId, mode);
  if (payload.error) {
    toast('NOT THIS ONE', payload.message || payload.error, 'red');
    // A repository already open is not a refusal to be stared at: the board is
    // where it can be gone back to or put down, so that is where this lands.
    if (payload.error === 'a mini-repo is already open') go('repos');
    return;
  }
  enterRepo(payload);
}

/* Resume the repository already open on the server, with the edits it kept. */
async function openRepo() {
  const payload = await api.repo();
  if (payload.error) {
    toast('NOTHING OPEN', payload.message || payload.error, 'red');
    return;
  }
  enterRepo(payload);
}

function enterRepo(payload) {
  destroyIncant();
  destroyChild();
  destroyRepo();
  clearInterval(G.timer);
  stopViz();
  partyui.beginEncounter();
  G.encounter = payload;
  G.problem = null;
  G.repoPayload = payload;
  G.seal = payload.seal || null;
  document.body.classList.toggle('interview-mode', payload.mode === 'interview');
  ensureRepoScreen();
  G.repo = new RepoUI($('#repo-host'), payload, {
    onRun: repoRun,
    onSubmit: repoSubmit,
    onLeave: leaveRepo,
    /* The banner across the top says INTERVIEW MODE and carries a clock. It is
     * the shell's, not the repo's, so the repo tells it what time it is rather
     * than letting it show the last fight's. */
    onTick: (elapsed, limit) => {
      if (payload.mode !== 'interview') return;
      const node = $('#interview-timer');
      if (!node) return;
      const left = (limit || payload.target_seconds || 0) - elapsed;
      node.textContent = fmtTime(left);
      node.classList.toggle('critical', left < 300);
    },
  });
  show('repo');
  audio.play('battle');
  const mentor = payload.mentor;
  if (mentor && payload.reason !== 'RESUME') {
    say(mentor.name, [
      'Somebody else wrote this, and they are not here to ask.',
      'Read it before you change it. The tests that are green now are green '
      + 'when you hand it back, or you have broken something that already shipped.',
    ], mentor.sprite);
  }
}

/* Ungraded. The server runs the project's own suite with the pristine test
 * files laid down last, so this cannot be used to find out what a weakened
 * test would say. */
async function repoRun(files) {
  const report = await api.repoRun(files);
  if (!report.tests) {
    // A refusal or a project that did not survive its own import. Say it out
    // loud AND hand it back, so the suite panel says what happened rather than
    // going on showing the run before it.
    toast('THE SUITE DID NOT RUN', report.message || report.error
      || 'nothing came back', 'red');
    return report;
  }
  audio.sfx(report.all_passed ? 'select' : 'hit');
  return report;
}

/* The attempt. The whole working tree goes; the server refuses it outright if
 * the suite is not the suite it handed out. */
async function repoSubmit(files) {
  const result = await api.repoSubmit(files);
  if (result.error) {
    toast('REFUSED', result.message || result.error, 'red');
    return;
  }
  await showRepoResult(result);
}

async function leaveRepo() {
  const r = await api.leaveRepo();
  destroyRepo();
  say('PUT IT DOWN', [r.message || 'Nothing was graded, so nothing was earned.'],
      'scholar');
  await refresh();
  returnToWorld();
}

const REPO_HEADLINE = {
  SOLVED: 'GREEN, ALL OF IT',
  INCOMPLETE: 'NOT DONE YET',
  REGRESSED: 'YOU BROKE SOMETHING THAT WORKED',
  BROKEN: 'THE PROJECT DOES NOT RUN',
  TAMPERED: 'THE ATTEMPT IS VOID',
};

async function showRepoResult(result) {
  G.lastResult = result;
  await refresh();
  const mr = result.mini_repo || {};
  const verdict = mr.verdict || {};
  const debrief = mr.debrief || {};
  const rankColour = { S: 'var(--gold-hi)', A: 'var(--green)', B: 'var(--blue)',
    C: 'var(--orange)', LEARNING_CLEAR: 'var(--violet)' }[result.rank] || 'var(--red)';
  audio.sfx(result.solved ? (result.rank === 'S' ? 'victory' : 'crit') : 'fail');

  let html = `<h2 style="color:${result.solved ? rankColour : 'var(--red)'}">
      ${REPO_HEADLINE[verdict.outcome] || 'HANDED BACK'}${
        result.solved ? ` — RANK ${result.rank}` : ''}</h2>
    <div class="row" style="flex-wrap:wrap;gap:6px;margin-bottom:12px">
      <span class="tag gold">+${result.xp} XP</span>
      <span class="tag blue">${fmtTime(result.seconds)} / target
        ${fmtTime(result.target_seconds)}</span>
      <span class="tag ${verdict.passed === verdict.total && verdict.total
        ? 'green' : 'red'}">${verdict.passed || 0} / ${verdict.total || 0} TESTS</span>
      ${result.skill ? `<span class="tag violet">${result.skill.replace(/_/g, ' ')}
        → ${result.skill_state ? Math.round(result.skill_state.mastery) : '—'}</span>` : ''}
      ${verdict.in_time === false ? '<span class="tag red">OVER THE CLOCK</span>' : ''}
    </div>
    <p>${markdownish(verdict.message || '')}</p>`;

  if ((verdict.tests || []).length) {
    html += '<h3>THE SUITE</h3>';
    for (const row of verdict.tests) {
      const icon = row.status === 'pass' ? '✔' : row.status === 'timeout' ? '⧗'
        : row.status === 'missing' ? '∅' : '✖';
      const colour = row.status === 'pass' ? 'var(--green)' : 'var(--red)';
      html += `<div class="small" style="line-height:1.7">
        <span style="color:${colour}">${icon}</span>
        <span class="muted">${row.id.split('::')[0]} ::</span>
        ${row.id.split('::')[1] || ''}
        ${row.target ? '<span class="tag gold">TARGET</span>' : ''}
        ${row.message ? `<br><span class="muted" style="margin-left:18px">${
          markdownish(row.message)}</span>` : ''}</div>`;
    }
  }
  if ((verdict.regressions || []).length) {
    html += `<p class="small" style="color:var(--red)">⛊ ${verdict.regressions.length}
      test(s) that were green when you arrived are not green now. That is the
      whole of what PRESERVE CONTRACT means.</p>`;
  }

  /* Learning never dead-ends, including here. The lesson and the file the cause
   * lived in arrive even after a tampered attempt; the reference patch is the
   * worked solution and follows the same rule worked solutions always do. */
  if (debrief.lesson) {
    html += `<h3>WHAT THIS WAS ABOUT</h3><p>${markdownish(debrief.lesson)}</p>`;
  }
  if (debrief.where) {
    html += `<p class="small muted">The cause lived in
      <code>${debrief.where}</code>.</p>`;
  }
  if ((debrief.solution || []).length) {
    html += '<h3>THE REFERENCE PATCH</h3>';
    for (const fix of debrief.solution) {
      html += `<p class="small"><b>${fix.path}</b></p>
        <pre class="spell-body" style="color:var(--red)">${
          (fix.old || '(new file)').replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>
        <pre class="spell-body" style="color:var(--green)">${
          (fix.new || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')}</pre>
        ${fix.why ? `<p class="small muted">${markdownish(fix.why)}</p>` : ''}`;
    }
    html += `<p class="small muted">That is one way, not the only one. A suite
      that goes green on your version is your version passing, not this one.</p>`;
  }

  if (result.coach && result.coach.available) {
    if (result.coach.questions.length) {
      html += '<h3>THE COACH ASKS</h3><ul style="line-height:1.9;color:var(--ink-dim)">'
        + result.coach.questions.map(q => `<li>${q}</li>`).join('') + '</ul>';
    }
    if (result.coach.analysis) html += `<p>${markdownish(result.coach.analysis)}</p>`;
  }
  if (result.training_camp && !result.solved) {
    html += `<h3>TRAINING CAMP — ${result.training_camp.name.toUpperCase()}</h3>
      <p>${result.training_camp.why}</p>`;
  }
  html += lootHtml(result.loot);
  // A Mini-Repo resolves through the same outcome path, so it pays metal too.
  html += metalHtml(result.metal);
  if (result.achievements && result.achievements.length) {
    html += result.achievements.map(a =>
      `<p class="small"><span class="tag gold">ACHIEVEMENT</span> ${a.name} —
        ${a.desc}</p>`).join('');
  }
  if (result.companion_line) {
    html += `<p class="small" style="color:var(--violet)">${result.companion_line}</p>`;
  }

  // The server closes the encounter on a clear, and on any result in a
  // measured run. When it has, the working surface behind this report has
  // nothing left to run against and says so.
  const retryable = !!(G.state.active_encounter
    && G.state.active_encounter.repo_id);
  if (!retryable && G.repo) {
    G.repo.finish(result.solved ? 'HANDED BACK — GREEN' : 'HANDED BACK');
  }
  html += `<div class="actions">
      ${retryable ? '<button class="btn primary" id="rr-retry">BACK TO THE CODE</button>' : ''}
      ${retryable ? '' : '<button class="btn primary" id="rr-next">ANOTHER REPOSITORY</button>'}
      <button class="btn" id="rr-world">RETURN TO THE WORLD</button>
    </div>`;

  const m = modal(html, { wide: true });
  const bind = (id, fn) => { const b = m.querySelector('#' + id); if (b) b.onclick = fn; };
  // The clock never restarted: the server grades on enc.started_at, so closing
  // this and carrying on is exactly what it looks like.
  bind('rr-retry', () => closeModal());
  bind('rr-next', () => { closeModal(); destroyRepo(); go('repos'); });
  bind('rr-world', () => {
    closeModal();
    destroyRepo();
    returnToWorld();
    playStoryQueue();
  });

  if (result.loot) {
    showLootDrop(result.loot);
    audio.sfx('loot');
  }
  if (result.story && result.story.length) {
    G.storyQueue = (G.storyQueue || []).concat(result.story);
  }
  if (result.levels_gained) {
    toast('LEVEL UP', `Level ${G.state.player.level} — `
      + `${result.unspent_points} point(s) waiting in GEAR.`, 'gold');
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

/* THE THREE THINGS A BOSS RESULT CAN BE, and until this pass there were two.
 *
 * A region boss used to die to ONE solved problem. It is four to six graded
 * solves now — bestiary.open_fight gives every boss its own phase ladder — so
 * a submission against one lands in one of three places:
 *
 *   ADVANCED   a phase fell and the thing behind it did not. The player gets
 *              the beat (see playPhaseTurn) and a way back in. This is the
 *              case that did not exist before.
 *   DEFEATED   the last phase fell. The key drops, and the key is named with
 *              the road it opens, because a key whose lock is a mystery is a
 *              trophy rather than a reason to have fought.
 *   STEPS BACK it is still standing. The ladder of simpler same-family
 *              problems arrives WITH the refusal, exactly as before — and the
 *              health bar now shows what the near miss took off it, which is
 *              the difference between "you failed" and "you were close and it
 *              felt that".
 */
function bossReport(boss) {
  if (boss.advanced) {
    const beat = boss.beat || {};
    return `<h3 style="color:var(--orange)">${boss.name} CHANGES</h3>
      <p class="small"><span class="tag red">PHASE ${(boss.phase | 0) + 1}
        / ${boss.phases}</span>
        ${beat.label ? `<span class="tag violet">${beat.label}</span>` : ''}</p>
      ${beat.herald ? `<p><i>“${beat.herald}”</i></p>` : ''}
      ${beat.tell ? `<p><b>${beat.tell}</b></p>` : ''}
      <p>${boss.message}</p>
      ${boss.next_rung ? `<p class="small muted">Your artifact reads one phase
        ahead: <b>${boss.next_rung.label}</b> — ${boss.next_rung.tell}</p>` : ''}
      ${boss.key ? `<p class="small muted">${boss.key.name} is still on it.
        It opens ${boss.key.opens_name}.</p>` : ''}
      <button class="btn" data-boss-next="${boss.id}">FACE THE NEXT PHASE ✦</button>`;
  }
  if (boss.defeated) {
    const key = boss.key;
    return `<h3>${boss.name} FALLS</h3>
      <p>Rank ${boss.rank} in ${fmtTime(boss.seconds)}. Rematch tier
      ${boss.rematch_tier} unlocked — the same boss, a different surface form.</p>
      ${key ? `<h3 style="color:${key.colour}">${key.name.toUpperCase()}</h3>
        <p><i>${key.line}</i></p>
        <p class="small"><span class="tag gold">OPENS</span> ${key.opens_name}</p>
        ${boss.opens ? `<p class="small muted">${boss.opens.name} is
          ${boss.opens.state === 'open' ? 'open' : boss.opens.requirement}.</p>` : ''}
        ${key.portal ? `<p class="small muted">THE STANDING PORTAL ·
          ${key.portal.held} of ${key.portal.required} wards lit.
          ${key.portal.held >= key.portal.required
            ? 'It is open.'
            : 'The practical does not need any of them — it is on the menu now.'}
          </p>` : ''}` : ''}`;
  }
  return `<h3>${boss.name} STEPS BACK</h3><p>${boss.message}</p>
    ${boss.chip ? `<p class="small"><span class="tag orange">−${boss.chip}</span>
      It felt that. The phase is at
      ${(boss.fight || {}).hp} / ${(boss.fight || {}).hp_max}, and only a
      solved problem can take the last point.</p>` : ''}
    ${boss.mentor ? `<div class="list-item">
      <span data-portrait="${boss.mentor.sprite}"></span>
      <span class="t">${boss.mentor.name}</span>
      <span class="d">${boss.mentor.greeting}</span></div>` : ''}
    <div id="boss-ladder"><p class="small muted">Reading the ladder…</p></div>`;
}

/* THE NULL KING, READING ONE LINE OUT OF YOUR FILE.
 *
 * gauntlet/antagonist.py was written and then imported by nothing — an orphan
 * in a codebase that claims none. He is wired now, to the occasions this pass
 * created: a boss down, its key taken, the fourteenth ward lit, and a region
 * stood in for the first time.
 *
 * HE IS WEATHER. `blocking` is False in every payload that module can produce
 * and its own audit proves it, so this never queues behind a modal, never asks
 * to be dismissed and never delays a transition. If he has nothing to say — a
 * measured run, where he is sealed like everything else — there is nothing
 * here to draw and nothing to skip.
 */
function heWatches(watching) {
  const rows = Array.isArray(watching) ? watching : (watching ? [watching] : []);
  const said = rows.filter(r => r && (r.lines || []).length);
  if (!said.length) return;
  // One of them. Two villains talking over each other is a cutscene, and
  // dropping the second costs nothing: nothing downstream reads what he said.
  const row = said[0];
  const who = (row.speaker || {}).name || 'THE NULL KING';
  say(String(who).toUpperCase(), row.lines, (row.speaker || {}).sprite
      || 'interviewer');
}

/* The beat, played on the stage. Everything about the timing comes from
 * gauntlet/bestiary.phase_beat() — the freeze, the flash, when the art turns,
 * when the boss speaks, when the reason lands — because the server owns the
 * fight and a client that invented its own 1900ms would drift from the combat
 * log the moment either was tuned. fx.bossPhaseTurn holds the whole sequence;
 * this only decides whether there is one to play. */
async function playPhaseTurn(result) {
  const boss = result && result.boss;
  if (!boss || !boss.advanced || !G.fx) return;
  audio.sfx('boss');
  try {
    await G.fx.bossPhaseTurn(boss.beat || {});
  } catch (err) { /* the report must appear even if the stage cannot animate */ }
}

/* Walking back in. `start_boss` serves whatever phase the fight is on, so this
 * is the same call that opened it — the fight is where it was left, including
 * across a reload. */
async function faceNextPhase(bossId) {
  try {
    const payload = await api.startBoss(bossId);
    if (payload.error) return toast('THE FIGHT IS CLOSED', payload.error, 'red');
    closeModal();
    enterBattle(payload);
  } catch (e) { toast('THE FIGHT IS CLOSED', e.message, 'red'); }
}


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
  /* YOU HAVE TO GO THERE. The server refuses a boss in a region the player is
   * not standing in — `Game.start_boss`, and the reason is written there — so
   * this says it on the row instead of letting the click earn a red toast.
   * Not `open: false`: the row stays live and the click travels, because a
   * button that names a place and then refuses to take you to it is worse than
   * no button. */
  const here = (G.state.player || {}).region;
  if (here && b.region && b.region !== here) {
    const there = (G.state.regions || []).find(r => r.id === b.region);
    return { open: true, travel: b.region, label: 'ELSEWHERE', colour: 'blue',
      why: `${b.name} is in ${there ? there.name : b.region.replace(/_/g, ' ')}. `
        + 'You are not. Walking there is the first move.' };
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
  // The ladder the player walked out of, if they walked out of one. Four to six
  // solves is long enough that "where was I" is a question this list has to be
  // able to answer.
  const fight = G.state.boss_fight || null;
  const list = (bosses.length ? bosses : G.state.bosses).map(b => {
    const best = b.records.filter(r => r.defeated)
      .reduce((a, r) => (a === null || r.seconds < a.seconds ? r : a), null);
    const gate = bossGate(b);
    gates.set(b.id, gate);
    /* WHAT IT IS HOLDING, named before the fight rather than after it. A boss
     * that drops a key the player only hears about on the corpse is a boss with
     * no reason to be fought twice; a key named at the door is a road on the
     * map with a monster in front of it. */
    const key = b.key;
    const open = fight && fight.boss === b.id ? fight : null;
    return `<div class="list-item ${gate.open ? '' : 'locked'}" data-boss="${b.id}">
      <span class="t">${b.cleared ? '☑ ' : gate.open ? '' : '⚿ '}${b.name.toUpperCase()}
        ${gate.label ? `<span class="tag ${gate.colour}">${gate.label}</span>` : ''}
        ${open ? `<span class="tag red">PHASE ${(open.phase | 0) + 1} / ${open.phases}
          — STILL OPEN</span>` : ''}</span>
      <span class="d">${b.taunt}<br>
      ${key ? `<span class="small" style="color:${key.colour}">⚿ ${key.name}</span>
        <span class="muted small"> — ${b.cleared ? 'taken' : 'still on it'};
        opens ${key.opens_name}</span><br>` : ''}
      <span class="muted small">${b.region.replace(/_/g, ' ')} ·
      ${b.records.length} attempt(s)${best ? ` · best ${fmtTime(best.seconds)} rank ${best.rank}` : ''}
      <br>${gate.why}</span>
      </span></div>`;
  }).join('');
  const held = G.state.keys_held | 0;
  const need = G.state.keys_required | 0;
  const m = modal(`<h2>BOSSES</h2>
    <p class="small">A boss is never a wall. Fail one and it enters its teaching phase —
    a mentor arrives, the complexity is reduced, and you climb back up.</p>
    <p class="small">Each one is <b>four to six graded solves</b>, one per phase,
    and it gets stronger at every turn — a heavier blow, a second element, a
    status it did not leave before, plate it was not wearing. Only a solved
    problem takes a phase down. Getting close moves the bar and never finishes
    it.</p>
    <p class="small"><span class="tag gold">${held} / ${need} KEYS</span>
    The Standing Portal in Python Village wants all fourteen. It opens the
    story's last room — never the practical, which is on the menu now.</p>
    ${list}<div class="actions"><button class="btn" id="m-close">CLOSE</button></div>`);
  m.querySelectorAll('[data-boss]').forEach(n => {
    n.onclick = async () => {
      const gate = gates.get(n.dataset.boss) || { open: true };
      // A locked boss says why it is locked rather than handing out a fight the
      // player cannot win and a one-line error afterwards.
      if (!gate.open) { toast(gate.label, gate.why, 'red'); return; }
      // And a boss that is simply somewhere else hands the player the map
      // rather than an error. The road is the answer to this one.
      if (gate.travel) {
        closeModal();
        toast('ELSEWHERE', gate.why, 'blue');
        // The road if one leaves from here, the map if it is further than that.
        // Same fallback `things_to_do` uses for a travel item; see line ~624.
        const road = roadsFromHere().find(e => e.to === gate.travel);
        if (road && road.passable) return takeRoad(road);
        return go('map');
      }
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
          : r.state === 'skipped'
          ? `<br><span class="muted small">The Trial placed you past this one. It is open, not finished — everything in it is still served.</span>`
          : ''}</span>
      <span>${r.state === 'done' ? '✔'
        : r.state === 'skipped' ? 'SKIPPED'
        : r.state === 'current' ? `${r.progress.percent}%` : ''}</span>
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
        (run.index || 0) + 1} of ${run.total || 0} ·
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
    <div class="frame" style="padding:14px;margin-top:12px;
         border-left:4px solid var(--green)">
      <div class="section-title" style="margin-top:0">NOTHING UNLOCKS THIS</div>
      <p class="small">${(s.practical || {}).line || `A measured run is a
        measurement, not a reward. It is reachable from this menu at any time,
        at level one, holding nothing.`}</p>
      <p class="small muted">You are holding ${s.keys_held | 0} of
        ${s.keys_required | 0} boss keys. Those open the Standing Portal and the
        story's last room. They have never had anything to do with this screen,
        and gating the one honest number in the game behind fourteen boss kills
        would make it something you have to earn twice.</p>
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
        // He takes the fourteen things first. The exam is identical either way
        // — this is the reason for it, not a gate on it.
        await playUnmaking();
        try {
          enterBattle(await api.interviewCurrent());
        } catch (e) { toast('CANNOT START', e.message, 'red'); }
      };
      m.querySelector('#iv-cancel').onclick = closeModal;
    };
  });
}

/* THE ENDING, AND THE REPORT BEHIND IT.
 *
 * `report.ending` comes back on EVERY interview run — it is the one place in
 * the codebase where the two exams are told apart, and for every ordinary run
 * it says `triggered: false` and this function does exactly what it always
 * did. It says `triggered: true` only for a practical that was started from
 * the last room, which is the only route that stages one.
 *
 * When it does trigger, the scene plays FIRST and the debrief waits behind it:
 * PASS is the freeze frame and the title card, FAIL is the way back down. Both
 * are scripts off the wire and both are skippable. */
function showInterviewReport(report) {
  const end = report.ending || {};
  if (end.triggered && end.cutscene) {
    /* The run is over and the seal is off, so the battle chrome comes down
     * before the scene rather than behind it. */
    document.body.classList.remove('interview-mode');
    closeModal();
    playEndingCutscene(end, () => showInterviewReportModal(report));
    return;
  }
  showInterviewReportModal(report);
}

function showInterviewReportModal(report) {
  document.body.classList.remove('interview-mode');
  const fired = !!((report.ending || {}).triggered && (report.ending || {}).cutscene);
  /* The ending owns the room's sound — the coda ends on a held note or on
   * nothing at all, and a victory sting over the top of it would be this
   * screen talking across the scene it just played. */
  if (!fired) audio.play('victory');
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
    ${endingBannerHtml(report.ending)}
    <p class="small muted">The coach is available again now.</p>
    <div class="actions">
      <button class="btn primary" id="iv-done">RETURN</button>
      ${fired ? '<button class="btn" id="iv-replay">WATCH IT AGAIN</button>' : ''}
      ${fired && (report.ending || {}).outcome === 'FAIL'
        ? '<button class="btn danger" id="iv-again">SIT IT AGAIN. NOW.</button>' : ''}
      ${!fired && report.debrief && !report.debrief.unavailable
        ? '<button class="btn" id="iv-finale">THE LAST SCENE</button>' : ''}
    </div>`,
    { wide: true });
  $('#iv-done').onclick = () => {
    closeModal();
    returnToWorld();
    refresh().then(paintWorldSide).catch(() => { /* refresh already said so */ });
  };
  /* The scene that just played, played again, off the script that is still in
   * this report. NOT `api.finale()` — that composes the standalone version from
   * the roll call alone, and the ending's own scene is the one that has the
   * people nobody came for standing on the stair. */
  const replay = $('#iv-replay');
  if (replay) {
    replay.onclick = () => {
      closeModal();
      playEndingCutscene(report.ending, () => showInterviewReportModal(report));
    };
  }
  /* A FAILED climax is A WAY BACK AND NEVER A GAME OVER. Nothing was spent,
   * nothing was locked, the portal is still open and the exam recomposes — so
   * the button is here, in the report, and it goes straight back down the
   * stair as the STAGED sitting it was. */
  const again = $('#iv-again');
  if (again) {
    again.onclick = async () => {
      closeModal();
      let r;
      try {
        r = await api.startFinalTrial(G.state.player.profile);
      } catch (e) { toast('CANNOT START', e.message, 'red'); return; }
      if (r.error) { toast('CANNOT START', r.message || r.error, 'red'); return; }
      try {
        enterBattle(await api.interviewCurrent());
      } catch (e) { toast('CANNOT START', e.message, 'red'); }
    };
  }
  /* STAGED AFTER THE PRACTICAL IS SCORED AND NEVER BEFORE, and offered rather
   * than forced: the practical gates the finale and the finale does not gate
   * the practical. A player who freed nobody gets the same scene with an empty
   * gallery behind them, which is the honest version of it. The report that was
   * just handed over is passed straight through — finale.py reads it, this file
   * does not. */
  const fin = $('#iv-finale');
  if (fin) fin.onclick = () => { closeModal(); finaleui.play(report); };
}

/* ======================================================================
 * THE ENDING, PLAYED — one clock against a script that came off the wire.
 * ======================================================================
 *
 * `ending.resolve()` hands over a scene in one of two shapes and this plays
 * both, because they were deliberately built to the same beat vocabulary:
 *
 *   PASS  a finale scene. Twenty-two beats, the index going out, the roll call
 *         forming up, a freeze at `freeze_at_ms` with the guitar hit and the
 *         title card on the same millisecond, and then the frame moving again
 *         for the coda.
 *   FAIL  a rematch scene. Eight beats, three acts, no title card and no
 *         guitar hit. IT IS NOT A GAME OVER and nothing here dresses it as
 *         one: nothing was spent, the portal is still open, and the report
 *         behind this carries the button that goes straight back down.
 *
 * Every word, every timing and every colour below came off the server. This
 * file owns the clock and nothing else.
 *
 * THE TWO HALVES. The title card is the freeze frame and it is NOT the end.
 * `the_prompt_stays` (pass) and `the_prompt_waits` (failure) are, and
 * `markCodaSeen()` fires on those two beat ids and on no others — a player who
 * walked out at the title card has seen half of this. */
let ENDING = null;

function playEndingCutscene(result, done) {
  stopEndingCutscene();
  const scene = (result || {}).cutscene;
  if (!scene || !(scene.beats || []).length) { if (done) done(); return; }

  const layer = el('div', 'ending-layer');
  layer.style.cssText = 'position:fixed;inset:0;z-index:9000;background:#06060a;'
    + 'display:flex;flex-direction:column;justify-content:center;'
    + 'padding:6vh 8vw;overflow:hidden';
  layer.innerHTML = `
    <div id="ed-act" class="pixel" style="font-size:11px;color:var(--gold-hi);
      letter-spacing:2px;margin-bottom:14px;min-height:16px"></div>
    <div id="ed-lines" style="max-width:58ch;line-height:1.7"></div>
    <div id="ed-card" style="position:absolute;inset:0;display:none;
      align-items:center;justify-content:center;flex-direction:column;
      text-align:center;pointer-events:none"></div>
    <!-- THE NAME RAIL. The roll call is a list of PEOPLE and the beats carry
         them in \`rows\`; without somewhere to put them the biggest beat in the
         scene plays as one narrator sentence and not one of the twenty-five
         names reaches a screen. finaleui.js has drawn this since it shipped. -->
    <div id="ed-rail" style="position:absolute;left:0;right:0;bottom:56px;
      display:flex;flex-wrap:wrap;gap:8px;padding:0 8vw;opacity:.85"></div>
    <div style="position:absolute;left:0;right:0;bottom:0;display:flex;
      align-items:center;gap:12px;padding:12px 8vw;background:#0a0a0ccc">
      <span class="bar" style="flex:1"><i id="ed-prog" style="width:0%;
        background:var(--gold-hi)"></i></span>
      <button class="btn small" id="ed-skip">SKIP</button>
    </div>`;
  document.body.appendChild(layer);

  ENDING = {
    scene, layer, done, t0: performance.now(), shown: -1, coda: false,
    raf: 0, key: null,
  };
  ENDING.key = (e) => { if (e.key === 'Escape') stopEndingCutscene(); };
  window.addEventListener('keydown', ENDING.key);
  layer.querySelector('#ed-skip').onclick = () => stopEndingCutscene();

  try { audio.play(scene.music || 'final'); } catch (e) { /* muted is fine */ }
  const tick = () => {
    if (!ENDING || ENDING.layer !== layer) return;
    const t = performance.now() - ENDING.t0;
    const beats = scene.beats || [];
    const total = Math.max(1, Number(scene.duration_ms) || 1);
    const prog = layer.querySelector('#ed-prog');
    if (prog) prog.style.width = `${Math.min(100, (t / total) * 100)}%`;
    let idx = -1;
    for (let i = 0; i < beats.length; i++) {
      if (t >= (Number(beats[i].at_ms) || 0)) idx = i; else break;
    }
    if (idx >= 0 && idx !== ENDING.shown) {
      ENDING.shown = idx;
      showEndingBeat(beats[idx]);
    }
    if (t >= total) { stopEndingCutscene(); return; }
    ENDING.raf = requestAnimationFrame(tick);
  };
  ENDING.raf = requestAnimationFrame(tick);
}

function showEndingBeat(beat) {
  if (!ENDING) return;
  const { layer, scene } = ENDING;
  const act = layer.querySelector('#ed-act');
  if (act) act.textContent = beat.act || '';

  const host = layer.querySelector('#ed-lines');
  if (host) {
    host.innerHTML = (beat.lines || []).map((l) => `
      <div style="margin:10px 0;color:${l.speaker && l.speaker !== 'narrator'
        ? 'var(--gold-hi)' : 'var(--ink-dim)'}">
        ${l.name ? `<span class="pixel" style="font-size:10px;
          color:var(--violet);display:block">${uikit.esc(l.name)}</span>` : ''}
        ${uikit.esc(l.text || '')}</div>`).join('');
  }

  const fx = beat.fx || [];
  /* The title card slams in on the freeze and comes off again at `unfreeze`.
   * A card left up over the second half is this scene ending at the title,
   * which is the half the player is supposed to stay past. */
  const card = layer.querySelector('#ed-card');
  if (card) {
    if (fx.indexOf('title_card') >= 0 && scene.title_card) {
      const c = scene.title_card;
      card.style.display = 'flex';
      /* THE RIBBON IS THE SENTENCE THAT TELLS THE TWO KINDS OF FREEDOM APART —
       * "11 BY YOUR HAND. 14 BY THE FALL OF IT." Dropping it left the counts
       * alive as numbers in the report banner and the distinction itself on no
       * screen at all. finale.py §8 is the spec; finaleui.js draws it as
       * .fin-ribbon and this is the same row. */
      card.innerHTML = `
        <div class="pixel" style="font-size:12px;color:var(--violet);
          letter-spacing:3px">${uikit.esc(c.eyebrow || '')}</div>
        <div class="pixel" style="font-size:min(6vw,44px);color:#f2ead8;
          margin:14px 0;text-shadow:0 6px 0 #0a0a0c">${uikit.esc(c.slab || '')}</div>
        <div class="pixel" style="font-size:min(3.4vw,22px);color:${
          (c.style || {}).rim || 'var(--gold-hi)'}">${uikit.esc(c.shout || '')}</div>
        <div class="pixel" style="font-size:min(2.6vw,16px);color:var(--gold-hi);
          margin-top:10px">${uikit.esc(c.ribbon || '')}</div>
        <div class="small muted" style="margin-top:18px">${
          uikit.esc(c.stinger || '')}</div>`;
    } else {
      card.style.display = 'none';
      card.innerHTML = '';
    }
  }

  /* THE NAMES. `beat.rows` is the roll call forming up — eleven on the beat
   * that counts the ones carried out, fourteen on the ones nobody came for —
   * and it is the only place in the scene a captive's NAME appears. Ported
   * from finaleui.showRail, capped at forty the same way, and cleared on the
   * beats that carry nobody so the rail belongs to the beat that named them. */
  const rail = layer.querySelector('#ed-rail');
  if (rail) {
    rail.innerHTML = (beat.rows || []).slice(0, 40).map((r) =>
      `<span class="pixel" style="font-size:10px;color:var(--ink-dim)">${
        uikit.esc(r.name || '')}</span>`).join('');
  }

  if ((beat.sfx || []).indexOf('finale_hit') >= 0 || fx.indexOf('guitar_hit') >= 0) {
    try { audio.sfx('crit'); } catch (e) { /* no context yet */ }
  }
  /* `cut` means cut: the guitar hit is the only sound in the room on the
   * freeze frame, and stopping is not the same as playing nothing. */
  if (beat.music === 'cut') { try { audio.stop(); } catch (e) { /* ignore */ } }
  else if (beat.music) { try { audio.play(beat.music); } catch (e) { /* ignore */ } }

  /* THE CODA, on the last beat of either scene and on nothing else. */
  if ((beat.id === 'the_prompt_stays' || beat.id === 'the_prompt_waits')
      && !ENDING.coda) {
    ENDING.coda = true;
    api.markCodaSeen().catch(() => { /* bookkeeping, never a gate */ });
  }
}

function stopEndingCutscene() {
  if (!ENDING) return;
  const { layer, raf, key, done } = ENDING;
  ENDING = null;
  if (raf) cancelAnimationFrame(raf);
  if (key) window.removeEventListener('keydown', key);
  if (layer && layer.isConnected) layer.remove();
  if (done) done();
}

/* What just happened to the world, in the report, under the debrief. Every
 * number here was counted by captives.py; this file adds none of its own. */
function endingBannerHtml(end) {
  if (!end || !end.triggered) return '';
  const pass = end.outcome === 'PASS';
  const counts = end.counts || {};
  const freedNow = Number(end.captives_freed_now) || 0;
  return `<div class="frame" style="padding:14px;margin:12px 0;
      border-left:4px solid ${pass ? 'var(--gold-hi)' : 'var(--orange)'}">
    <div class="section-title" style="margin-top:0">${pass
      ? 'THE INDEX STOPPED ANSWERING' : 'THE SHELVES ARE STILL FULL'}</div>
    <p class="small">${uikit.esc(end.why || '')}</p>
    ${pass ? `<p class="small"><span class="tag gold">${freedNow} RELEASED</span>
      <span class="tag green">${Number(counts.carried) || 0} CARRIED OUT</span>
      <span class="tag">${Number(counts.total) || 0} IN ALL</span></p>` : ''}
    ${!pass ? `<p class="small muted">${uikit.esc(
      (end.rematch || {}).note || '')}</p>` : ''}
  </div>`;
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
    <div id="forge-panel-host" style="margin-top:12px"></div>
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
  // The blade, its rung, its technique, the bag and the next rung's cost. It
  // reads directly under what you are wearing, because "what am I carrying" and
  // "what am I working toward" are one question and this feature only means
  // anything if the answer to the second one is visible without a click.
  const forgeHost = $('#forge-panel-host');
  if (forgeHost) forgePanel(forgeHost);

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
      // Boots are the answer to a hazard, so what the region costs to walk
      // across has just changed. Drop the cached reading rather than showing
      // the player a stale "nothing on your feet answers it".
      G.regionElement = null;
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
      G.regionElement = null;
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

/* ======================================================================
 * THE FORGE — Vess's counter, and the blade panel that points at it.
 *
 * The whole loop this feature exists for is: a metal only drops in one place,
 * the only person who can work it stands in Python Village, and one object you
 * have owned since Chapter I becomes something people recognise across a room.
 * Two screens carry that. The PANEL says what you are carrying and what you are
 * working toward; the COUNTER says what it costs, what you are short of, where
 * that drops and how many fights it is.
 *
 * Everything below draws server data. There are no rules in here: the quote,
 * the shortfall, the substitution and the refusals are all forge.py's, read off
 * the payload rather than recomputed, so what the player was shown and what
 * they then paid cannot disagree.
 * ==================================================================== */

/* The forge's own classes, injected once rather than added to game.css, for the
 * same reason BattleFX._ensureStyle() does it: this is one screen's furniture
 * and it should arrive with the screen. Everything else on the counter is the
 * existing vocabulary — .frame, .list-item, .item-card, .tag, .section-title —
 * so a theme change reaches it without being told. */
function ensureForgeStyle() {
  if (document.getElementById('forge-style')) return;
  const node = document.createElement('style');
  node.id = 'forge-style';
  node.textContent = `
.metal-bag { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 10px; }
.metal-chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px;
  border: 2px solid var(--line); background: var(--panel-2);
  font-size: calc(11px * var(--scale)); color: var(--ink-dim);
}
.metal-chip i { width: 10px; height: 10px; display: inline-block; }
.metal-chip b { color: var(--gold-hi); font-size: calc(11px * var(--scale)); }
.blade-card {
  display: flex; gap: 12px; align-items: flex-start; padding: 10px;
  border: 2px solid var(--line); background: var(--panel-2); margin-bottom: 10px;
}
.blade-card .blade-art { flex: 0 0 auto; line-height: 0; }
.blade-card .blade-art canvas { image-rendering: pixelated; }
.blade-card .in { font-family: 'Press Start 2P', monospace;
  font-size: calc(9px * var(--scale)); line-height: 1.6; }
.blade-card .ie { font-size: calc(11px * var(--scale)); color: var(--green);
  line-height: 1.6; margin-top: 5px; }
.blade-card .if { font-size: calc(11px * var(--scale)); color: var(--ink-faint);
  font-style: italic; margin-top: 5px; line-height: 1.6; }
.forge-tech { font-family: 'Press Start 2P', monospace; font-size: calc(8px * var(--scale));
  color: var(--gold-hi); margin-top: 6px; }
.cost-list { margin: 6px 0 10px; }
.cost-row {
  display: flex; align-items: center; gap: 8px; padding: 5px 8px;
  border-left: 3px solid var(--red); background: var(--panel-2);
  margin-bottom: 4px; font-size: calc(11px * var(--scale));
}
.cost-row.met { border-left-color: var(--green); }
.cost-row i { width: 10px; height: 10px; flex: 0 0 10px; }
.cost-row .cn { flex: 1 1 auto; color: var(--ink-dim); }
.cost-row .cv { flex: 0 0 70px; text-align: right; color: var(--gold-hi); }
.cost-row .cw { flex: 0 0 45%; color: var(--ink-faint); text-align: right; }
.rank-row { display: flex; gap: 10px; padding: 5px 0;
  border-bottom: 1px solid var(--line); }
.rank-row .rn { flex: 0 0 40%; font-family: 'Press Start 2P', monospace;
  font-size: calc(8px * var(--scale)); color: var(--ink-faint); line-height: 1.7; }
.rank-row .rd { flex: 1 1 auto; font-size: calc(11px * var(--scale));
  color: var(--ink-faint); line-height: 1.6; }
.rank-row.got .rn { color: var(--gold-hi); }
.rank-row.got .rd { color: var(--ink-dim); }
.forge-anvil { display: flex; align-items: center; justify-content: center;
  min-height: 200px; }
.forge-anvil canvas { image-rendering: pixelated; }
.forge-panel .metal-bag { margin-bottom: 10px; }
.cost-row .forge-met, .list-item .forge-met { color: var(--green); }
`;
  document.head.appendChild(node);
}

/* One metal in the bag, as a chip. What a rung WANTS is the cost list's job;
 * this is only ever "what am I carrying", which is the question a player asks
 * halfway across the map. */
function metalChip(row) {
  return `<span class="metal-chip" title="${row.name} — rung ${row.rung || '?'}">
    <i style="background:${row.colour}"></i>${row.name}
    <b>${row.held}</b></span>`;
}

function metalBag(bag, { empty = 'Nothing in the bag yet.' } = {}) {
  const rows = (bag || []).filter(r => r.held > 0);
  if (!rows.length) return `<p class="small muted">${empty}</p>`;
  return `<div class="metal-bag">${rows.map(r => metalChip(r)).join('')}</div>`;
}

/* The blade, drawn from its own pipeline. lootart.drawItem routes a forged item
 * to the forge table on its own, so this is itemIcon with the caption a rung
 * wants: the line, the rung, and the one sentence that says what changed. */
function bladeCard(item, { size = 88, note = '' } = {}) {
  // Always a node. Every caller appends the result, and a function that
  // sometimes hands back a string is a function that throws on the one path
  // nobody tested.
  if (!item) return el('div', 'small muted', 'Nothing on the bench.');
  const card = el('div', 'blade-card');
  const art = el('span', 'blade-art');
  art.appendChild(itemIcon(item, size));
  card.appendChild(art);
  card.appendChild(el('div', 'grow',
    `<div class="in" style="color:${item.rarity_colour}">${item.name}
       <span class="muted">· ${item.rarity}</span></div>
     ${item.technique ? `<div class="forge-tech">${item.technique.rank}</div>
       <div class="small" style="color:var(--green)">${item.technique.text}</div>` : ''}
     <div class="ie">${(item.effect_text || []).join(' · ')}</div>
     <div class="if">${item.look || item.flavour || ''}</div>
     ${note ? `<div class="small muted">${note}</div>` : ''}`));
  return card;
}

/* The at-a-glance panel. Lives on the GEAR screen next to the slots, because
 * that is where a player goes to ask what they are wearing, and the answer to
 * "what am I working toward" belongs in the same breath. */
function forgePanel(host) {
  ensureForgeStyle();
  const f = (G.state && G.state.forge) || {};
  const frame = el('div', 'frame forge-panel');
  frame.style.padding = '14px';
  frame.appendChild(el('div', 'section-title', 'THE BLADE'));

  if (!f.blade) {
    frame.appendChild(el('p', 'small muted',
      'No line has been issued to you yet. Choose a discipline and your order '
      + 'will hand you something with your name on it — rung one of nine.'));
    host.appendChild(frame);
    return;
  }
  if (!f.tier) {
    frame.appendChild(el('p', 'small muted', 'Your line is waiting on the bench.'));
    host.appendChild(frame);
    return;
  }

  frame.appendChild(bladeCard(f.item,
    { note: f.equipped ? '' : 'Not in your hand right now.' }));

  const here = (G.state.player || {}).region;
  const atBench = !!(f.smith && here === f.smith.region);
  const q = f.quote || {};
  if (q.at_top) {
    frame.appendChild(el('p', 'small',
      `<span class="tag gold">RUNG ${f.tier} OF 9</span> ${q.text || ''}`));
  } else if (q.next) {
    const rows = (q.cost || []).map(row => `
      <div class="cost-row${row.met ? ' met' : ''}">
        <i style="background:${row.colour}"></i>
        <span class="cn">${row.name}</span>
        <span class="cv">${row.have}<span class="muted">/${row.need}</span></span>
        <span class="cw">${row.met ? '✔' : row.regions.join(' · ')}</span>
      </div>`).join('');
    frame.appendChild(el('div', '',
      `<div class="section-title">NEXT — RUNG ${q.next_tier}: ${q.next.name}</div>
       <div class="cost-list">${rows}</div>
       <div class="cost-row${q.gold_short ? '' : ' met'}">
         <i style="background:var(--gold)"></i><span class="cn">Gold</span>
         <span class="cv">${G.state.player.gold}<span class="muted">/${q.gold}</span></span>
         <span class="cw">${q.gold_short ? `${q.gold_short} short` : '✔'}</span></div>
       <div class="forge-tech" style="margin-top:8px">${
         (q.changes && q.changes.technique) ? q.changes.technique.rank[1] : ''}</div>
       <p class="small muted">${q.next.look || ''}</p>
       <p class="small ${q.ready ? '' : 'muted'}" style="${
         q.ready ? 'color:var(--green)' : ''}">${q.ready
           ? (atBench
              ? 'That is the full weight. Vess will take it.'
              : `That is the full weight. Carry it back to ${
                  (f.smith && f.smith.region === 'python_village')
                    ? 'Python Village' : 'the village'}.`)
           : 'Fight where the metal is. Vess will tell you where that is.'}</p>`));
  }

  frame.appendChild(el('div', 'section-title', 'THE BAG'));
  frame.appendChild(el('div', '', metalBag(f.bag,
    { empty: 'No metal yet. Every region but the village gives up one kind, '
             + 'and only one kind.' })));

  const go = el('button', atBench ? 'btn good' : 'btn',
                atBench ? 'TAKE IT TO THE SMITH' : 'READ THE BENCH FROM HERE');
  go.onclick = () => showSmith();
  frame.appendChild(go);
  host.appendChild(frame);
}

/* ---------------- the counter ---------------- */

/* Where a shortfall drops, how hard it hits there, and roughly how many fights
 * a bar is. This is the half of the screen that stops a player deciding a rung
 * is a wall rather than a walk. */
function counselRows(counsel) {
  if (!counsel || !counsel.length) return '';
  return `<div class="section-title">WHERE THAT COMES FROM</div>`
    + counsel.map(c => `<div class="list-item">
        <span class="t" style="color:${c.colour}">${c.name.toUpperCase()}</span>
        <span class="d">${c.line}<br>
          <span class="muted">${c.tell}</span></span></div>`).join('');
}

function techniqueLadder(tech) {
  if (!tech || !tech.ranks) return '';
  return `<div class="section-title">${tech.name} — RANK ${tech.at} OF 9</div>
    <p class="small muted">${tech.blurb || ''}</p>
    ${tech.ranks.map(r => `<div class="rank-row ${r.reached ? 'got' : ''}">
      <span class="rn">${r.rank}</span>
      <span class="rd">${r.reached ? r.text
        : `<span class="muted">${r.cost_text.join(' · ')}</span>`}</span>
    </div>`).join('')}`;
}

function swapPanel(swap) {
  if (!swap || !swap.mine) return '';
  return `<div class="section-title">OR CARRY SOMETHING YOU FOUND</div>
    <p class="small muted">${swap.trade}</p>
    <div class="list-item"><span class="t" style="color:var(--gold-hi)">
      ${swap.mine.name} — ${swap.mine.technique}</span>
      <span class="d">${swap.mine.effect_text.join(' · ')}<br>
        <span class="muted">raw rate ${Math.round(swap.mine.rate_total * 100)}
        · ${swap.mine.capabilities} capability(ies)${
          swap.mine.upgrades ? ' · grows' : ''}</span></span></div>
    ${swap.rivals.slice(0, 3).map(r => `<div class="list-item">
      <span class="t">${r.name}</span>
      <span class="d">${r.effect_text.join(' · ')}<br>
        <span class="muted">raw rate ${Math.round(r.rate_total * 100)}
        · ${r.capabilities} capability(ies) · finished</span></span></div>`).join('')}
    <p class="small">${swap.verdict}</p>`;
}

function routePanel(route) {
  if (!route || !route.length) return '';
  return `<div class="section-title">THE WHOLE ROAD</div>
    <p class="small muted">Every rung left, what it costs and where that metal
    lives. A player who can see the whole road can decide whether to walk it.</p>
    ${route.map(r => `<div class="list-item">
      <span class="t">RUNG ${r.tier} — ${r.name}
        <span class="muted">· ${r.rarity} · ${r.gold} gold · ~${r.encounters} fights</span></span>
      <span class="d">${r.technique_rank}<br>${r.cost.map(c =>
        `<span class="${c.have >= c.units ? 'forge-met' : ''}">${c.units} ${c.name}
          <span class="muted">(${c.have} held · ${c.where.join(', ')})</span></span>`
        ).join(' · ')}</span></div>`).join('')}`;
}

async function showSmith() {
  let view;
  try {
    view = await api.forge();
  } catch (e) { toast('THE BENCH IS SHUT', e.message, 'red'); return; }
  drawSmith(view);
}

function drawSmith(view) {
  ensureForgeStyle();
  if (!view || view.error === 'sealed') {
    const m = modal(`<h2>THE BENCH IS SHUT</h2>
      <p>${(view && view.message) || 'Not during a measured run.'}</p>
      <div class="actions"><button class="btn" id="m-close">BACK</button></div>`);
    m.querySelector('#m-close').onclick = closeModal;
    return;
  }
  const smith = view.smith || {};
  const q = view.quote || {};
  const ready = !!q.ready;
  const shortMetal = Object.keys(q.still_short || {}).length
    ? q.still_short : (q.short || {});
  const blocked = [];
  if (Object.keys(shortMetal).length) {
    blocked.push(Object.entries(shortMetal)
      .map(([id, n]) => `${n} more ${(view.bag.find(b => b.metal === id) || {}).name || id}`)
      .join(', '));
  }
  if (q.gold_short) blocked.push(`${q.gold_short} more gold`);

  const m = modal(`
    <h2 style="color:var(--gold)">${smith.name || 'VESS'} — ${smith.role || 'the smith'}</h2>
    <p class="small muted">${smith.greeting || ''}</p>
    <div class="grid2">
      <div class="frame" style="padding:14px">
        <div class="section-title">ON THE BENCH</div>
        <div id="smith-blade"></div>
        ${q.at_top
          ? `<p class="small"><span class="tag gold">RUNG ${view.tier} OF 9</span>
             ${q.text || ''}</p>`
          : q.next ? `
        <div class="section-title">RUNG ${q.next_tier} — ${q.next.name}</div>
        <div id="smith-next"></div>
        <div class="cost-list">${(q.cost || []).map(row => `
          <div class="cost-row${row.met ? ' met' : ''}">
            <i style="background:${row.colour}"></i>
            <span class="cn">${row.name}</span>
            <span class="cv">${row.have}<span class="muted">/${row.need}</span></span>
            <span class="cw">${row.met ? '✔ enough'
              : `${row.short} short · ${row.regions.join(' · ')}`}</span>
          </div>`).join('')}
          <div class="cost-row${q.gold_short ? '' : ' met'}">
            <i style="background:var(--gold)"></i>
            <span class="cn">Her labour</span>
            <span class="cv">${view.gold}<span class="muted">/${q.gold}</span></span>
            <span class="cw">${q.gold_short ? `${q.gold_short} short` : '✔ paid'}</span>
          </div>
        </div>
        ${Object.keys(q.substitution || {}).length ? `
          <p class="small" style="color:var(--orange)">She can beat
          ${Object.entries(q.substitution).map(([id, n]) =>
            `${n} ${(view.bag.find(b => b.metal === id) || {}).name || id}`).join(', ')}
          down into what is missing. You lose some of it in the beating.
          That is the trade, and it is always a bad one.</p>` : ''}
        <div class="actions">
          <button class="btn ${ready && view.at_the_bench ? 'primary' : ''}"
            id="smith-forge" ${ready && view.at_the_bench ? '' : 'disabled'}>
            ${!view.at_the_bench
              ? `SHE IS IN ${String(view.bench_region_name || 'THE VILLAGE').toUpperCase()}`
              : ready ? 'FORGE IT' : `STILL SHORT — ${blocked.join(' and ')}`}</button>
        </div>
        ${view.at_the_bench ? '' : `<p class="small muted">You can read the bench
          from anywhere — that is how you know what you are short of. The metal
          is worked in ${view.bench_region_name || 'the village'}, and nowhere
          else.</p>`}` : ''}
        <div class="section-title">THE BAG</div>
        <div id="smith-bag"></div>
      </div>
      <div class="frame" style="padding:14px">
        <div class="section-title">SHE SAYS</div>
        ${(view.lines || []).map(l => `<p class="small">${l}</p>`).join('')}
        ${counselRows(view.counsel)}
      </div>
    </div>
    <div class="frame" style="padding:14px;margin-top:12px">
      ${techniqueLadder(view.technique)}
    </div>
    <div class="grid2" style="margin-top:12px">
      <div class="frame" style="padding:14px">${routePanel(view.route)}</div>
      <div class="frame" style="padding:14px">${swapPanel(view.swap)}</div>
    </div>
    <div class="actions">
      ${view.item ? (view.equipped
        ? '<button class="btn" id="smith-rack">HANG IT ON THE WALL</button>'
        : '<button class="btn good" id="smith-unrack">TAKE IT BACK</button>') : ''}
      <button class="btn" id="smith-ore">WHERE EVERY METAL DROPS</button>
      <button class="btn" id="m-close">LEAVE THE BENCH</button>
    </div>`, { wide: true });

  const blade = m.querySelector('#smith-blade');
  if (blade && view.item) blade.appendChild(bladeCard(view.item));
  const next = m.querySelector('#smith-next');
  if (next && view.next_item) {
    next.appendChild(bladeCard(view.next_item,
      { size: 72, note: 'What it becomes. Nothing is lost — the metal goes in.' }));
  }
  const bag = m.querySelector('#smith-bag');
  if (bag) bag.innerHTML = metalBag(view.bag);

  m.querySelector('#m-close').onclick = closeModal;
  m.querySelector('#smith-ore').onclick = () => showOreMap(view);
  const forgeBtn = m.querySelector('#smith-forge');
  if (forgeBtn && ready && view.at_the_bench) {
    forgeBtn.onclick = () => doForge(view.blade, forgeBtn);
  }
  const rack = m.querySelector('#smith-rack');
  if (rack) {
    rack.onclick = async () => {
      const r = await api.forgeRack(view.blade);
      if (r.error) { toast('SHE DECLINES', r.message || r.error, 'red'); return; }
      audio.sfx('select');
      await refresh();
      drawSmith(r.smith);
    };
  }
  const unrack = m.querySelector('#smith-unrack');
  if (unrack) {
    unrack.onclick = async () => {
      const r = await api.forgeUnrack();
      if (r.error) { toast('SHE DECLINES', r.message || r.error, 'red'); return; }
      audio.sfx('unlock');
      await refresh();
      drawSmith(r.smith);
    };
  }
}

/* Every metal, where it drops, how hard that region hits and roughly how many
 * fights a bar is. Eleven metals over sixteen regions, so a player who has
 * never been to the Graph Wastes can still find out that Wastes-iron is the
 * thing standing between them and rung seven — which is the difference between
 * a long walk and a wall. */
async function showOreMap(back) {
  let r;
  try {
    r = await api.forgeMetals();
  } catch (e) { toast('CANNOT READ THE LEDGER', e.message, 'red'); return; }
  const held = Object.create(null);
  for (const row of r.bag || []) held[row.metal] = row.held;
  const m = modal(`<h2>THE ELEVEN METALS</h2>
    <p class="small muted">Every region but the village gives up exactly one
    kind, and it gives up no other. That is the whole reason the map is an
    economy: you go where the metal is, and you carry it back here.</p>
    ${(r.metals || []).map(metal => `<div class="list-item">
      <span class="t" style="color:${metal.colour}">
        ${metal.name.toUpperCase()} <span class="muted">· rung ${metal.rung}
        · ${held[metal.metal] || 0} held</span></span>
      <span class="d">${metal.line}<br>
        <span class="muted">${metal.blurb}</span><br>
        <span class="muted">${metal.tell}</span></span></div>`).join('')}
    <div class="actions">
      <button class="btn primary" id="ore-back">BACK TO THE BENCH</button>
      <button class="btn" id="m-close">OUT</button>
    </div>`, { wide: true });
  m.querySelector('#m-close').onclick = closeModal;
  m.querySelector('#ore-back').onclick = () => drawSmith(back);
}

/* The upgrade. forge.upgrade() checks the quote before it touches the bag, so a
 * refusal cannot have spent anything — and the screen is redrawn from the same
 * state either way, so the player can see that for themselves rather than being
 * told it. */
async function doForge(bladeId, btn) {
  btn.disabled = true;
  btn.textContent = 'SHE IS WORKING…';
  let r;
  try {
    r = await api.forgeUpgrade(bladeId);
  } catch (e) {
    btn.disabled = false;
    toast('THE BENCH IS SHUT', e.message, 'red');
    return;
  }
  if (r.error) {
    toast('SHE DECLINES', r.message
      || (r.error === 'gold' ? `${r.gold_short} gold short.`
          : r.error === 'metal' ? 'Not enough metal.'
          : r.error === 'at_top' ? 'There is no rung ten.'
          : String(r.error)), 'red');
    drawSmith(r.smith || r);
    return;
  }
  audio.sfx('levelup');
  await refresh();
  showForged(r);
}

/* What a rung landing looks like. Three things changed at once and Vess names
 * all three, because the player is about to look at the sprite. */
function showForged(r) {
  const m = modal(`
    <h2 style="color:var(--gold-hi)">${r.rung.name.toUpperCase()} — RUNG ${r.tier}</h2>
    <div class="grid2">
      <div class="frame" style="padding:14px">
        <div class="forge-anvil" id="forged-art"></div>
      </div>
      <div class="frame" style="padding:14px">
        ${(r.lines || []).map(l => `<p class="small">${l}</p>`).join('')}
        <div class="section-title">WHAT IT DOES NOW</div>
        ${(r.changes.power.new || []).map(t =>
          `<p class="small" style="color:var(--green)">+ ${t}</p>`).join('')}
        ${(r.changes.power.grown || []).map(t =>
          `<p class="small" style="color:var(--blue)">↑ ${t}</p>`).join('')}
        <div class="section-title">${r.changes.technique.name} ·
          ${r.changes.technique.rank[1]}</div>
        <p class="small">${r.changes.technique.text}</p>
        <p class="small muted">Paid: ${Object.entries(r.spent).map(([id, n]) =>
          `${n} ${id.replace(/_/g, ' ')}`).join(', ')} · ${r.gold_spent} gold.
          ${r.gold} gold left.</p>
      </div>
    </div>
    <div class="actions">
      <button class="btn primary" id="f-back">BACK TO THE BENCH</button>
      <button class="btn" id="m-close">OUT INTO THE WORLD</button>
    </div>`, { wide: true });
  const art = m.querySelector('#forged-art');
  if (art && r.item) art.appendChild(itemIcon(r.item, 192));
  m.querySelector('#m-close').onclick = closeModal;
  m.querySelector('#f-back').onclick = () => showSmith();
  toast('FORGED', `${r.rung.name} — rung ${r.tier}.`, 'gold');
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
  /* NOT the battle stage, and deliberately not moved with it. This is a modal
   * of its own — lootart.drawLootDrop composes into 192x128 with the item at
   * 96,104 — and it has never shared a pixel with fx.js's raster. Growing it to
   * 256x224 would only put more empty room around a 16x16 icon. */
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

/* What fell out of the monster that is not loot. A metal drops only in the
 * regions it belongs to, which is the whole reason the map is an economy rather
 * than a menu — so the line says what it is for as well as what it is. */
function metalHtml(metal) {
  if (!metal) return '';
  ensureForgeStyle();
  const f = (G.state && G.state.forge) || {};
  const q = f.quote || {};
  const wanted = (q.cost || []).find(row => row.metal === metal.metal);
  return `<h3>METAL</h3>
    <div class="item-card" style="border-color:${metal.colour};cursor:default">
      <div class="grow">
        <div class="in" style="color:${metal.colour}">
          ${metal.units} × ${metal.name}
          <span class="muted">· ${metal.held} in the bag</span></div>
        <div class="ie">${wanted
          ? (wanted.met
             ? `Enough for rung ${q.next_tier}. Vess is waiting.`
             : `Rung ${q.next_tier} wants ${wanted.need} — ${wanted.short} short.`)
          : 'Not what the next rung asks for. It keeps; nothing in the bag spoils.'}</div>
        <div class="if">${metal.tell || metal.blurb || ''}</div>
      </div></div>`;
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
        question ${(run.index || 0) + 1} of ${run.total || 0}.</p>` : ''}
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

/* uikit's HOST, for the four modules that arrived with the world layer. Same
 * bargain partyui makes: they draw into this file's chrome rather than growing
 * their own, so one backdrop click closes every modal in the game and one
 * destroyChild() tears down whatever is mounted. */
function configureWorldScreens() {
  uikit.configure({
    panel,
    modal,
    closeModal,
    toast,
    say,
    sfx: (kind) => audio.sfx(kind),
    state: () => G.state,
    refresh: async () => { await refresh(); return G.state; },
    back: () => returnToWorld(),
    go: (id) => go(id),
    /* A screen that opened an encounter hands it straight back: main.js owns
     * the battle screen, and a module that drew one would be the second one. */
    onEncounter: (payload) => enterBattle(payload),
  });
}

/* Every world-layer screen mounts the same way. The module's paint() calls
 * HOST.panel synchronously, which is what destroys whatever was mounted before
 * it; registering the new child straight afterwards is what makes the NEXT
 * navigation tear this one down. */
function mountWorldScreen(mod, paint, ...args) {
  const pending = paint(...args);
  G.child = { destroy: () => { try { mod.leave(); } catch (e) { /* done */ } } };
  return Promise.resolve(pending).catch((e) => {
    toast('THAT PANEL WILL NOT OPEN', e.message, 'red');
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

/* ---------------- the keyring ---------------- */

/* FOURTEEN BOSSES, FOURTEEN KEYS, FOURTEEN ROADS, ONE DOOR.
 *
 * The keys are not items. There is no state["keys"] in the save and nothing
 * here can drop, sell or lose one: `world.keys_held(cleared_bosses)` derives
 * the whole ring from the kill list, so beating the boss IS the possession.
 * This screen is a reading of that, which is why it has no buttons except the
 * one that opens the door.
 *
 * THE LINE AT THE BOTTOM IS THE POINT OF THE SCREEN. A player looking at
 * "3 / 14" is one small assumption away from believing the exam is eleven boss
 * fights away. It is not, it never will be, and the sentence saying so comes
 * off the server (`finalexam.practical_gate`) rather than being retyped here,
 * so there is exactly one place it can be got wrong. */
async function paintKeyring() {
  panel('THE KEYRING', '<p class="small muted">Counting the wards…</p>');
  let view;
  try {
    view = await api.keys();
  } catch (e) { toast('THAT PANEL WILL NOT OPEN', e.message, 'red'); return; }
  const portal = view.portal || {};
  const practical = view.practical || {};
  const held = view.held ? view.held.length : 0;
  const need = view.required | 0;

  const rows = (view.keys || []).map(k => `
    <div class="list-item ${k.held ? '' : 'locked'}"
         style="${k.held ? `border-left:3px solid ${k.colour}` : ''}">
      <span class="t" style="${k.held ? `color:${k.colour}` : ''}">
        ${k.held ? '⚿ ' : '· '}${k.name.toUpperCase()}</span>
      <span class="d">${k.held ? k.line
        : `Held by ${k.boss_name}, in ${k.region_name}.`}<br>
        <span class="muted small">opens ${k.opens_name}</span></span>
    </div>`).join('');

  panel('THE KEYRING', `
    <p class="small">Every boss in the realm is holding one. Beating it is the
    possession — there is nothing to carry, nothing to lose, and nothing to
    sell. Each key opens exactly one road, and the road is named on it.</p>

    <div class="frame" style="padding:16px;margin:12px 0;border-left:4px solid ${
      portal.open ? 'var(--gold-hi)' : 'var(--violet)'}">
      <div class="section-title" style="margin-top:0">${
        portal.name || 'THE STANDING PORTAL'}</div>
      <p class="small">${portal.where || ''}</p>
      <p class="small"><span class="tag ${portal.open ? 'gold' : ''}">${held} / ${need}
        WARDS LIT</span>${portal.open ? '<span class="tag green">OPEN</span>' : ''}</p>
      <span class="bar"><i style="width:${need ? (held / need) * 100 : 0}%;
        background:${portal.open ? 'var(--gold-hi)' : 'var(--violet)'}"></i></span>
      <p class="small muted" style="margin-top:8px">${portal.line || ''}</p>
      ${portal.open ? '<button class="btn primary" id="keys-enter">STEP THROUGH ✦</button>'
        : ''}
    </div>

    <div class="frame" style="padding:14px;margin:12px 0;
         border-left:4px solid var(--green)">
      <div class="section-title" style="margin-top:0">
        THE PRACTICAL IS NOT BEHIND THIS DOOR</div>
      <p class="small">${practical.line || ''}</p>
      <p class="small muted">${practical.where || ''}</p>
      <button class="btn" id="keys-exam">SIT IT NOW ✦</button>
    </div>

    ${rows}`);

  const enter = $('#keys-enter');
  if (enter) {
    enter.onclick = async () => {
      const res = await api.enterPortal();
      if (!res.ok) return toast('IT DOES NOT OPEN', res.message || res.error, 'red');
      audio.sfx('unlock');
      toast((res.trial || {}).name || 'THE LAST ROOM', res.message || '', 'gold');
      paintKeyring();
      openLastRoom(res);
    };
  }

  const exam = $('#keys-exam');
  // The measurement, from the screen that counts the keys, with the keys
  // uncounted. This button is here specifically so the answer to "do I need
  // these first" is a thing the player can press rather than read.
  if (exam) exam.onclick = () => go('exam');
}

/* THE LAST ROOM, once the door is open — and the one place in this client that
 * starts the staged practical.
 *
 * `api.startFinalTrial()` composes the SAME exam `api.startExam()` composes:
 * same six questions' worth of composer, same seal, same clock, same rules.
 * The only difference is that the server binds the composed exam's id to the
 * story, so that when the debrief comes back `ending.resolve()` recognises it.
 * That is the entire mechanism, and it is why this call may not be made from
 * the exam screen or the interview menu: a staged sitting reachable from the
 * menu is the ending firing for practice, which is the bug this whole feature
 * exists to fix.
 *
 * And the other direction, which matters more: this room is NOT the way to the
 * practical. `SIT IT NOW` on the keyring screen is, it is three lines above
 * this one, and it needs none of the fourteen keys. */
function openLastRoom(room) {
  const trial = room.trial || {};
  const two = room.two_exams || {};
  const climax = two.climax || {};
  const examiner = room.examiner || {};
  const m = modal(`<h2>${uikit.esc(trial.name || 'THE LAST ROOM')}</h2>
    <p class="small muted">${uikit.esc(trial.where || '')}</p>
    <p>${uikit.esc(room.message || '')}</p>
    ${examiner.name ? `<p class="small"><span class="tag gold">${
      uikit.esc(examiner.name)}</span> ${uikit.esc(examiner.epithet || '')}</p>` : ''}
    <div class="frame" style="padding:14px;margin:12px 0;
         border-left:4px solid var(--gold-hi)">
      <div class="section-title" style="margin-top:0">${
        uikit.esc(climax.name || 'THE FINAL PRACTICAL')}</div>
      <p class="small">${uikit.esc(climax.what || '')}</p>
      <p class="small muted">${uikit.esc(climax.note || '')}</p>
    </div>
    <div class="actions">
      <button class="btn danger" id="lr-sit">BEGIN. THE CLOCK STARTS NOW.</button>
      <button class="btn" id="lr-wait">NOT YET</button>
    </div>`, { wide: true });
  m.querySelector('#lr-wait').onclick = closeModal;
  m.querySelector('#lr-sit').onclick = async () => {
    closeModal();
    let r;
    try {
      r = await api.startFinalTrial(G.state.player.profile);
    } catch (e) { toast('CANNOT START', e.message, 'red'); return; }
    if (r.error) { toast('CANNOT START', r.message || r.error, 'red'); return; }
    /* `staging.staged === false` here would mean the wards went dark between
     * the door and the desk. It is NOT an error and it does not stop anything:
     * the exam has started and it is sat as a measurement. Said once, quietly. */
    if (r.staging && r.staging.staged === false) {
      toast('SAT AS A MEASUREMENT', r.staging.why || '', '');
    }
    try {
      enterBattle(await api.interviewCurrent());
    } catch (e) { toast('CANNOT START', e.message, 'red'); }
  };
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
  { id: 'repos', label: 'MINI-REPO BATTLES',
    blurb: 'Somebody else\u2019s codebase, its own tests, and a clock.' },
  { id: 'exam', label: 'THE PRACTICAL TEST',
    blurb: 'The fourteen-rung ladder, and the exam at the top of it.' },
  { id: 'interview', label: 'INTERVIEW MODE',
    blurb: 'A measured run. Nothing is taught while it is running.' },
  { id: 'seed', label: 'THIS WORLD',
    blurb: 'The shareable world code, and the ground under it.' },
  { id: 'settings', label: 'MENU',
    blurb: 'Audio, accessibility, the sandbox, and your history.' },
  { id: 'town', label: 'THE TOWN SQUARE',
    blurb: 'The Mender, the smith, the shelf, and the assayer with her trials.' },
  { id: 'hunt', label: 'THE HUNT',
    blurb: 'What roams this region, what it examines, and how long it would take.' },
  { id: 'sage', label: 'THE ONE WHO SITS HERE',
    blurb: 'Sixteen hidden teachers, found by having done the work.' },
  { id: 'arts', label: 'THE SECRET ARTS',
    blurb: 'Lines of Python nobody sells you. Sixteen for your discipline.' },
  { id: 'regalia', label: 'REGALIA',
    blurb: 'Objects that buy a companion more help, and never deeper help.' },
  { id: 'sanctuaries', label: 'THE HIDDEN HEALERS',
    blurb: 'Seventeen of them, found by being hurt in the right place.' },
  { id: 'keys', label: 'THE KEYRING',
    blurb: 'Fourteen keys, the roads they open, and the door that counts them.' },
  { id: 'rollcall', label: 'THE ROLL CALL',
    blurb: 'Who each boss took, who walked out, and who is still held.' },
  { id: 'finale', label: 'THE LAST SCENE',
    blurb: 'Staged after the practical is scored, and never before.' },
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

function paintTransferCard() {
  const host = $('#transfer-card');
  if (!host) return;
  api.transfer().then((t) => {
    if (!t || !$('#transfer-card')) return;          // panel closed while we read
    if (t.error) { host.innerHTML = ''; return; }
    // The band matters more than the number. A percentage built from four
    // attempts is not a percentage, so when it is not measurable yet we print
    // the sentence instead and say what would make it measurable.
    const head = t.measured
      ? `<div class="section-title">TRANSFER READINESS
           <span style="color:var(--gold)">${t.score}%</span>
           <span class="small muted">${t.band.text} at ${t.band.confidence} · n=${t.sample}</span>
         </div>`
      : `<div class="section-title">TRANSFER READINESS
           <span class="small muted">not yet measurable</span></div>`;
    const skills = (t.by_skill || []).slice(0, 6).map(r =>
      `<div class="row" style="gap:10px">
         <span class="nm" style="width:150px">${r.skill}</span>
         <span class="n" style="width:52px;text-align:right">${
           r.score === null || r.score === undefined ? '—' : r.score + '%'}</span>
         <span class="small muted">n=${r.sample}</span>
       </div>`).join('');
    host.innerHTML = head
      + `<p class="small" style="margin:8px 0">${t.note}</p>`
      + (t.verdict ? `<p class="small" style="color:var(--violet)">${t.verdict}</p>` : '')
      + (skills ? `<div style="margin-top:10px">${skills}</div>` : '')
      + `<p class="small muted" style="margin-top:10px">
           ${t.remaining} unfamiliar hold-out problem(s) left of ${t.holdout_total}.
           Nothing in Adventure Mode can move this number, which is the point of it.
         </p>`;
  }).catch(() => { host.innerHTML = ''; });
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
    repos: `${((s.mini_repos || {}).cleared || []).length}/${
      ((s.mini_repos || {}).repos || []).length} handed back green`,
    exam: `${(s.cleared_bosses || []).length}/14 rungs climbed`,
    interview: `profile ${s.player.profile}`,
    seed: s.seed || '',
    settings: `${s.playtime || ''} played`,
    town: `${s.player.gold} gold in the purse`,
    hunt: 'seventeen apexes, one to a region',
    sage: 'sixteen sanctums, ninety-six arts',
    arts: 'earned, never bought',
    regalia: 'twenty-four objects',
    sanctuaries: 'free, and they find you',
    keys: 'fourteen bosses, fourteen roads, one door',
    rollcall: 'twenty-five names',
    finale: 'sixteen beats and a freeze frame',
  };
  panel('THE LEDGER', `
    <p class="small muted">Everything this game keeps about you, and every door
    that is not one of the five on the bar.</p>
    <div id="transfer-card" class="frame" style="margin:14px 0;padding:16px">
      <div class="section-title">TRANSFER READINESS</div>
      <p class="small muted">reading the hold-out…</p>
    </div>
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
  ledger: () => { paintLedger(); paintTransferCard(); },
  status: paintStatus,
  grimoire: paintGrimoire,
  interview: paintInterview,
  settings: paintSettings,
  saves: paintSaves,
  exam: paintExam,
  seed: paintSeed,
  repos: paintRepos,
  // -- the world layer ---------------------------------------------------
  town: () => mountWorldScreen(townui, townui.paintTown),
  hunt: () => mountWorldScreen(huntui, huntui.paintHunt, currentRegion().id),
  sage: () => mountWorldScreen(legendui, legendui.paintSage, currentRegion().id),
  arts: () => mountWorldScreen(legendui, legendui.paintArts),
  regalia: () => mountWorldScreen(legendui, legendui.paintRegalia),
  sanctuaries: () => mountWorldScreen(legendui, legendui.paintSanctuaries),
  keys: paintKeyring,
  rollcall: () => mountWorldScreen(legendui, legendui.paintRollCall),
  finale: () => mountWorldScreen(finaleui, finaleui.paintFinaleCard),
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
  // The town is the loop. It is on the bar rather than in the index because a
  // player comes back to it between every second fight, and a door you use
  // that often should not be two clicks deep.
  { id: 'town', label: 'TOWN' },
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
  // A key aimed at the chrome rather than at a field. focusEditor() waits these
  // out before it takes the caret, so the tail of a SPACE-tap through a mentor
  // speech never lands in the player's code.
  if (e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'INPUT') {
    G.lastChromeKey = Date.now();
  }
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

/* The ring and the lit caption are one signal with the caret, so they are
 * driven by focus rather than by a click: tabbing in counts, and so does the
 * automatic focus an encounter does when it opens. */
(() => {
  const host = $('#editor-host');
  const pane = $('#editor-pane');
  if (!host || !pane) return;
  host.addEventListener('focusin', () => pane.classList.add('typing'));
  host.addEventListener('focusout', () => pane.classList.remove('typing'));
  // The caption names the box below it, so clicking the caption should put the
  // caret in the box. A label that says "write here" and does nothing when
  // pressed is a label a player stops believing.
  const caption = $('#editor-caption');
  /* GATED THE SAME WAY THE AUTOMATIC HANDOFF IS GATED. The caption is visible
   * and clickable while a dialogue is up — at 1600x1000 it sits at y=690 and
   * the dialogue box at y=868 — so an unconditional focus() here put the caret
   * in the textarea mid-taunt, and the global key handler stands down for a
   * focused TEXTAREA: the dialogue could no longer be advanced with SPACE, and
   * both spaces were typed into the player's code. editorIsLive() already knows
   * that an open modal and an open dialogue own the screen. */
  if (caption) {
    /* A deliberate "put the caret there": nothing is talking over the screen
     * (editorIsLive says so), so there is no tail of chrome keys to guard
     * against and no reason to disturb what was selected. */
    caption.addEventListener('click', () => {
      if (editorIsLive()) focusEditor({ keepSelection: true, guard: false });
    });
  }
})();

window.addEventListener('resize', () => {
  if (G.title) G.title.resize();
  if (G.overworld) G.overworld.resize();
  // The whole-number scale the stage can afford is a function of the viewport,
  // so it is re-decided here rather than once at the start of the fight.
  if (G.screen === 'battle') fitBattleStage();
  // The wash is positioned in pixels against the stage, so it moves when the
  // stage does.
  if (G.alarmNode) paintAlarm();
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
  // The wheel, once. It is the rulebook — element names, status durations, what
  // cures what, which hazard a region wears, the potion catalogue — and it does
  // not change while the server is up. Soft, and the HUD degrades to ids
  // instead of names if it never lands: a codex that failed to fetch is not a
  // reason to refuse to draw a fight.
  api.wheel().then((w) => { if (w && !w.error) G.wheel = w; })
    .catch(() => { /* the HUD reads ids instead of names */ });

  // partyui.js paints through the shell's own chrome — one modal node, one
  // toast rail, one panel body. Handed over once, before any door can open.
  configureParty();
  configureWorldScreens();

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
  // The overworld reads the companion out of the state we already hold, the
  // same way partyui.js reads it — no second fetch, and no knowledge of pets
  // in this file, so the pets rewrite lands without touching the shell.
  //
  // The apex rides on the same object. huntui.stateFor MUTATES it rather than
  // spreading it into a new one, because this function is called every frame by
  // two different consumers and a fresh object per frame in that path is the
  // one thing overworld.js's budget is written to avoid.
  G.overworld.stateSource = () => huntui.stateFor(G.state);
  G.overworld.onEnter = onNodeEnter;
  /* The canvas draws the telegraph wordlessly, which is deliberate; this is the
   * words, on the region card, where a number belongs. */
  G.overworld.onApexStage = (stage, info) => {
    huntui.onStage(stage, info);
    // A creature that has just gone quiet is worth one line, because the
    // player is owed the end of a thing that started with twenty seconds of
    // warning. DORMANT on arrival is not news, so it is latched.
    if ((stage === 'DORMANT' || stage === 'SPENT') && G._apexWasUp) {
      G._apexWasUp = false;
      toast('IT LOSES THE TRAIL', 'Whatever that was, it is not following you '
        + 'any more.', '');
    } else if (stage === 'TRACKING' || stage === 'CLOSING') {
      G._apexWasUp = true;
    }
  };
  G.overworld.onApexContact = (info) => huntui.onContact(info);
  // A fight that was open when the page was closed. The server still holds the
  // fight block, so the banner has to come back with it or the player is in a
  // fight the interface has quietly forgotten about.
  huntui.restore();
  // Click the animal, the animal answers. Every species has its own voice and
  // a legendary sounds like what it grew into.
  G.overworld.onCompanionClick = (c) => {
    if (!c) return;
    audio.resume();
    const spoke = audio.petSound(c.animal, { tier: c.tier, dead: c.dead });
    if (spoke && c.line) toast(String(c.name || c.animal).toUpperCase(), c.line, 'violet');
  };
  /* The field has run off the end of the strip it holds and is asking for a
   * fresher one. refresh() rebinds the overworld to the new record and
   * republishes it — see the block at `G.state = next` — so this is only the
   * trigger; the id guard is belt and braces against a refresh that arrives
   * after the player has already walked through a door. Overworld._pollSky()
   * asks once per exhausted strip and not once every two seconds. */
  G.overworld.onSkyStale = async () => {
    await refresh();
    const here = currentRegion();
    if (here && G.overworld.region && here.id === G.overworld.region.id) {
      G.overworld.region = here;
    }
  };
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

  // #repo/<id> drops straight into a Mini-Repo, and #repos onto the board.
  // Same purpose as #problem/<id>: linking somebody to the thing you are
  // talking about, and reaching a screen from a tool that cannot click.
  const repoLink = /^#repo\/([a-z0-9_-]+)$/.exec(location.hash || '');
  if (repoLink || (location.hash || '') === '#repos') {
    document.body.classList.remove('titling');
    if (!G.state.build) await api.chooseBuild('ANALYST').catch(() => {});
    await refresh();
    if (repoLink) await startRepo(repoLink[1]);
    else go('repos');
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
  // The title screen gets its own track. Autoplay is usually blocked before the
  // first gesture, so audio.resume() retries this on the first click or key.
  audio.play('title');
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
  /* `audio.play('town')` used to be here, and it was cancelling the title's own
   * track five lines after the comment above promised it. audio.play() is one
   * music channel with a crossfade — a second call REPLACES the first, it does
   * not layer — so the dedicated title recording
   * (nickpanek-80s-style-surf-thrash-instrumental) was fetched and aborted on
   * every single boot, and what a player actually heard on the title screen was
   * the overworld track, which is what `town` aliases to. Measured in a browser
   * before and after: boot requested three music files and aborted two of them
   * with net::ERR_ABORTED; it now requests one and aborts none. The region's
   * track is started by leaveTitle(), which is where it belongs. */
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
