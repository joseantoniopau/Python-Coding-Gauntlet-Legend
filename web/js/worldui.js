/* The open world, the dungeons, and the strip that says what to do next.
 *
 * Eleven server modules have been reachable over HTTP for a while and invisible
 * in the browser for exactly as long. This file renders three of them:
 *
 *   THE TODO STRIP   /api/todo is guaranteed non-empty — that guarantee is the
 *                    codebase's no-dead-end rule, expressed as an endpoint. So
 *                    the strip is rendered unconditionally and every row is a
 *                    button, because a list of suggestions you cannot press is
 *                    a list of reproaches.
 *   THE WORLD MAP    s.world.nodes and s.world.edges are a real directed graph
 *                    with gates on the edges. Drawn as a graph, on a canvas, in
 *                    the game's own palette: regions carry their state, roads
 *                    carry theirs, and a closed road is drawn rather than
 *                    omitted so the player can read the wall and aim at it.
 *   THE DESCENT      a dungeon run, built ONLY out of `options`. The server
 *                    asserts that list is never empty and that at least one
 *                    entry is available; hand-rolling the buttons would throw
 *                    that away and re-open the trapped-in-a-room bug.
 *
 * Nothing in here decides anything. Every gate, reason, requirement and refusal
 * shown is a string the server wrote — `refusal`, `requirement`, `why`,
 * `reason`, `message`. Where this file has an opinion it is about layout.
 *
 * MOUNTING. main.js owns the screens; this module owns what goes inside them.
 *
 *   import { createWorldUI } from './worldui.js';
 *   G.worldui = createWorldUI({
 *     toast, say, audio,                       // main's own chrome, reused
 *     onRefresh:   () => refresh().then(() => G.state),
 *     onEncounter: (payload) => enterBattle(payload),
 *     onRegion:    (id) => loadRegion(id),
 *     onAction:    (action) => { ... },        // todo rows this file cannot run
 *     onBack:      () => returnToWorld(),
 *   });
 *   G.worldui.mountTodo($('#world-side-todo'), G.state);   // the strip, anywhere
 *   G.worldui.mountOverworld($('#panel-body'), G.state);   // the map screen
 *   G.worldui.mountDescent($('#panel-body'), G.state);     // when s.dungeon is set
 *
 * Travel fires world events and this file announces those itself. A GRADED
 * SUBMISSION fires them too, and that payload lands in main.js — so after a
 * result, pass them on:  G.worldui.announce(result.world && result.world.events)
 * and they get the same herald rather than vanishing.
 *
 * Every hook is optional and every one has a fallback that does not strand the
 * player — the last resort is clicking main.js's own WORLD nav button, which is
 * in the document whether or not this file was given a way home.
 */
import { api } from './api.js';
import { RAMPS, BIOME_RAMP, THEME, OUTLINE, mix, shade } from './palette.js';

const $ = (sel, root = document) => root.querySelector(sel);

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};

/* Everything drawn here is server prose and half of it is player-facing text
 * with punctuation in it. It goes in through innerHTML, so it goes through
 * this first. */
function esc(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

const FONT = '10px "Press Start 2P", monospace';
const FONT_S = '8px "Press Start 2P", monospace';

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < String(str).length; i++) {
    h ^= String(str).charCodeAt(i); h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/* ---------------------------------------------------------------- refusals */

/** A sealed refusal is HTTP 409 with a body the exam wrote. api.js hands the
 *  body back rather than throwing, so the ONLY correct thing to do with it is
 *  print `message` and stop guessing. */
export function isSealed(res) {
  return Boolean(res && res.error === 'sealed' && res.message);
}

/** The title over a sealed refusal: the capability the exam took, named. The
 *  sentence under it is the exam's and is never rewritten. */
export function sealedTitle(res) {
  const cap = (res && res.capability) || '';
  return cap ? `SEALED · ${cap.replace(/_/g, ' ')}` : 'SEALED';
}

/** The one sentence to show the player for any "no" the world layer can give.
 *  Returns null when the payload is not a refusal at all — callers test that
 *  rather than sniffing a 200 body for success. */
export function refusalText(res) {
  if (!res) return 'The server answered with nothing at all.';
  if (isSealed(res)) return res.message;
  if (res.route && res.route.reason) return res.route.reason;
  if (res.reason && res.ok === false) return res.reason;
  if (typeof res.error === 'string' && res.error) {
    return res.error === 'sealed' ? 'Sealed for the duration of the exam.' : res.error;
  }
  if (res.moved === false && res.reason) return res.reason;
  return null;
}

/* ------------------------------------------------------------ route styling */

/* Four road states, four readings. `soft` is the interesting one: the road is
 * open and what is down it will hurt — an open world you are forbidden to enter
 * is a corridor with extra steps, so the client draws the warning, not a wall. */
export function routeStyle(state) {
  switch (state) {
    case 'open':   return { colour: THEME.gold, dash: [], width: 3, label: 'OPEN' };
    case 'soft':   return { colour: THEME.ember, dash: [7, 5], width: 3, label: 'OPEN, AND ABOVE YOU' };
    case 'wall':   return { colour: THEME.blood, dash: [3, 4], width: 2, label: 'GATED' };
    case 'hidden': return { colour: THEME.inkFaint, dash: [1, 6], width: 2, label: 'NOT ON YOUR MAP' };
    default:       return { colour: THEME.inkFaint, dash: [2, 4], width: 2, label: String(state || '') };
  }
}

const STATE_TINT = {
  ruined: THEME.inkFaint, stirring: THEME.ember,
  restored: THEME.venom, transformed: THEME.goldHigh,
};

const STATE_TAG = {
  ruined: '', stirring: 'orange', restored: 'green', transformed: 'gold',
};

const SKY = {
  dawn:     ['#2a1638', '#7a3a2e', '#e8762a'],
  overcast: ['#14141c', '#22242e', '#383c4a'],
  clearing: ['#101826', '#1e3450', '#4a6a88'],
  clear:    ['#0a1a2c', '#1a4c68', '#4fb7d6'],
  radiant:  ['#2a1c08', '#a8811f', '#fff0b4'],
};

/* ------------------------------------------------------------------ layout */

/** Place the regions. The payload carries no coordinates — the world is a graph,
 *  not a picture — so the columns are BFS rank from the safest region outward
 *  and the rows are danger order inside a rank. That makes the map agree with
 *  the curriculum without anybody hand-placing seventeen nodes, and it survives
 *  a seeded world adding or moving one. */
export function layoutRegions(nodes, edges, width, height) {
  const byId = new Map(nodes.map(n => [n.id, n]));
  const adj = new Map(nodes.map(n => [n.id, []]));
  for (const edge of edges) {
    if (!adj.has(edge.from) || !adj.has(edge.to)) continue;
    adj.get(edge.from).push(edge.to);
    adj.get(edge.to).push(edge.from);   // ranking ignores direction; walking does not
  }
  const root = nodes.reduce(
    (best, n) => (best === null || (n.danger || 0) < (best.danger || 0) ? n : best), null);
  const rank = new Map();
  if (root) {
    rank.set(root.id, 0);
    const queue = [root.id];
    while (queue.length) {
      const here = queue.shift();
      for (const next of adj.get(here) || []) {
        if (rank.has(next)) continue;
        rank.set(next, rank.get(here) + 1);
        queue.push(next);
      }
    }
  }
  // A region no road touches still has to be on the map; it goes in the last
  // column, where its lack of edges is the visible fact about it.
  let maxRank = 0;
  for (const value of rank.values()) maxRank = Math.max(maxRank, value);
  for (const n of nodes) if (!rank.has(n.id)) rank.set(n.id, maxRank + 1);
  maxRank = Math.max(...rank.values(), 0);

  const columns = [];
  for (const n of nodes) {
    const r = rank.get(n.id);
    (columns[r] = columns[r] || []).push(n);
  }
  const padX = 64;
  const padTop = 42;
  const padBottom = 34;
  const spanX = Math.max(1, width - padX * 2);
  const spanY = Math.max(1, height - padTop - padBottom);
  const placed = new Map();
  columns.forEach((column, r) => {
    column.sort((a, b) => (a.danger || 0) - (b.danger || 0)
      || String(a.id).localeCompare(String(b.id)));
    const x = padX + (maxRank === 0 ? spanX / 2 : (r / maxRank) * spanX);
    column.forEach((n, i) => {
      const y = padTop + ((i + 0.5) / column.length) * spanY;
      // A pixel of hand-drawn wobble, deterministic per region so the map is
      // the same map every time it is opened.
      const jx = (hash(n.id) % 9) - 4;
      const jy = (hash(n.id + ':y') % 11) - 5;
      placed.set(n.id, { id: n.id, node: n, x: Math.round(x + jx), y: Math.round(y + jy) });
    });
  });
  return { placed, byId, rank, columns: maxRank + 1 };
}

/* ---------------------------------------------------------------- map paint */

const NODE_W = 62;
const NODE_H = 42;

function fitCanvas(canvas, width, height) {
  const dpr = clamp(window.devicePixelRatio || 1, 1, 2);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.imageSmoothingEnabled = false;    // the whole game is on one pixel grid
  return ctx;
}

function plate(ctx, x, y, w, h, cut = 7) {
  ctx.beginPath();
  ctx.moveTo(x + cut, y);
  ctx.lineTo(x + w - cut, y);
  ctx.lineTo(x + w, y + cut);
  ctx.lineTo(x + w, y + h - cut);
  ctx.lineTo(x + w - cut, y + h);
  ctx.lineTo(x + cut, y + h);
  ctx.lineTo(x, y + h - cut);
  ctx.lineTo(x, y + cut);
  ctx.closePath();
}

function quad(a, c, b, t) {
  const u = 1 - t;
  return {
    x: u * u * a.x + 2 * u * t * c.x + t * t * b.x,
    y: u * u * a.y + 2 * u * t * c.y + t * t * b.y,
  };
}

/** Two lines of at most eleven characters, which is what fits under a plate at
 *  8px in the pixel face. Longer names lose their tail rather than their box. */
function nameLines(name) {
  const words = String(name || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const word of words) {
    if (!line) line = word;
    else if ((line + ' ' + word).length <= 11) line += ' ' + word;
    else { lines.push(line); line = word; }
  }
  if (line) lines.push(line);
  if (lines.length > 2) { lines.length = 2; lines[1] = lines[1].slice(0, 10) + '…'; }
  return lines.map(l => (l.length > 11 ? l.slice(0, 10) + '…' : l));
}

/* The overworld graph on a canvas. It owns hit-testing and nothing else: every
 * click is handed straight back out, because deciding what a click MEANS needs
 * the server payloads and those live on WorldUI. */
class MapCanvas {
  constructor(canvas, handlers = {}) {
    this.canvas = canvas;
    this.handlers = handlers;
    this.world = null;
    this.layout = null;
    this.hover = null;          // {kind:'node'|'edge', id}
    this.selected = null;       // region id
    this.phase = 0;
    this.width = 0;
    this.height = 0;

    this._onMove = (e) => this.pointer(e, false);
    this._onDown = (e) => this.pointer(e, true);
    this._onLeave = () => { this.hover = null; this.canvas.style.cursor = 'default'; this.draw(); };
    canvas.addEventListener('mousemove', this._onMove);
    canvas.addEventListener('click', this._onDown);
    canvas.addEventListener('mouseleave', this._onLeave);
  }

  release() {
    this.canvas.removeEventListener('mousemove', this._onMove);
    this.canvas.removeEventListener('click', this._onDown);
    this.canvas.removeEventListener('mouseleave', this._onLeave);
  }

  setWorld(world) {
    this.world = world || { nodes: [], edges: [] };
    this.resize();
  }

  resize() {
    if (!this.world || !this.canvas.isConnected) return;
    const box = this.canvas.parentElement;
    this.width = Math.max(320, Math.floor((box ? box.clientWidth : 720) - 26));
    const rows = Math.max(3, Math.ceil(this.world.nodes.length / 4));
    this.height = clamp(160 + rows * 76, 340, 620);
    this.ctx = fitCanvas(this.canvas, this.width, this.height);
    this.layout = layoutRegions(this.world.nodes, this.world.edges, this.width, this.height);
    this.draw();
  }

  /** Canvas coordinates from a mouse event, in CSS pixels — the context is
   *  already scaled for the device ratio, so the two agree. */
  at(event) {
    const rect = this.canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  pick(point) {
    if (!this.layout) return null;
    for (const spot of this.layout.placed.values()) {
      if (Math.abs(point.x - spot.x) <= NODE_W / 2 + 3
          && Math.abs(point.y - spot.y) <= NODE_H / 2 + 3) {
        return { kind: 'node', id: spot.id };
      }
    }
    let best = null;
    for (const edge of this.world.edges) {
      const geo = this.geometry(edge);
      if (!geo) continue;
      for (let t = 0.08; t <= 0.92; t += 0.04) {
        const p = quad(geo.a, geo.c, geo.b, t);
        const d = Math.hypot(p.x - point.x, p.y - point.y);
        if (d < 9 && (!best || d < best.d)) best = { kind: 'edge', id: edge.id, d };
      }
    }
    return best;
  }

  geometry(edge) {
    const a = this.layout && this.layout.placed.get(edge.from);
    const b = this.layout && this.layout.placed.get(edge.to);
    if (!a || !b) return null;
    // Parallel roads between the same pair would sit on top of each other, so
    // each bows by a deterministic amount off the perpendicular.
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.max(1, Math.hypot(dx, dy));
    const bias = ((hash(edge.id) % 2) ? 1 : -1) * (8 + (hash(edge.id) % 18));
    const c = {
      x: (a.x + b.x) / 2 + (-dy / len) * bias,
      y: (a.y + b.y) / 2 + (dx / len) * bias,
    };
    return { a, b, c };
  }

  pointer(event, clicked) {
    if (!this.layout) return;
    const hit = this.pick(this.at(event));
    if (clicked) {
      if (!hit) return;
      if (hit.kind === 'node' && this.handlers.onNode) this.handlers.onNode(hit.id);
      if (hit.kind === 'edge' && this.handlers.onEdge) this.handlers.onEdge(hit.id);
      return;
    }
    const before = this.hover ? this.hover.kind + this.hover.id : '';
    const now = hit ? hit.kind + hit.id : '';
    this.canvas.style.cursor = hit ? 'pointer' : 'default';
    if (before === now) return;
    this.hover = hit;
    if (this.handlers.onHover) this.handlers.onHover(hit);
    this.draw();
  }

  draw() {
    const ctx = this.ctx;
    if (!ctx || !this.layout) return;
    const w = this.width;
    const h = this.height;
    const pulse = 0.5 + 0.5 * Math.sin(this.phase);

    ctx.fillStyle = THEME.void;
    ctx.fillRect(0, 0, w, h);

    // The sky is the loudest signal the world has that it noticed the player,
    // and progression.advance() moves it. It belongs at the top of the map.
    const sky = SKY[(this.world && this.world.sky) || 'dawn'] || SKY.dawn;
    const grad = ctx.createLinearGradient(0, 0, 0, 26);
    grad.addColorStop(0, sky[0]);
    grad.addColorStop(0.6, sky[1]);
    grad.addColorStop(1, sky[2]);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, 26);
    ctx.globalAlpha = 0.25;
    ctx.fillStyle = THEME.void;
    for (let x = 0; x < w; x += 4) ctx.fillRect(x, 18 + (hash(x) % 6), 2, 8);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = OUTLINE;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, 27); ctx.lineTo(w, 27); ctx.stroke();
    ctx.font = FONT_S;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = THEME.ink;
    ctx.fillText(String((this.world && this.world.sky) || 'dawn').toUpperCase(), 8, 13);

    for (const edge of this.world.edges) this.drawEdge(ctx, edge, pulse);
    for (const spot of this.layout.placed.values()) this.drawNode(ctx, spot, pulse);
  }

  drawEdge(ctx, edge, pulse) {
    const geo = this.geometry(edge);
    if (!geo) return;
    const style = routeStyle(edge.state);
    const lit = this.hover && this.hover.kind === 'edge' && this.hover.id === edge.id;
    ctx.save();
    ctx.lineCap = 'butt';
    ctx.setLineDash(style.dash);
    ctx.lineWidth = style.width + (lit ? 2 : 0);
    ctx.strokeStyle = lit ? shade(style.colour, 40) : style.colour;
    ctx.globalAlpha = edge.state === 'hidden' ? 0.45 + 0.25 * pulse : lit ? 1 : 0.85;
    ctx.beginPath();
    ctx.moveTo(geo.a.x, geo.a.y);
    ctx.quadraticCurveTo(geo.c.x, geo.c.y, geo.b.x, geo.b.y);
    ctx.stroke();
    ctx.setLineDash([]);

    const mid = quad(geo.a, geo.c, geo.b, 0.5);
    if (edge.state === 'wall') {
      // A gate is drawn ON the road. A road that simply stopped being drawn is
      // a dead end, and this codebase does not have those.
      ctx.globalAlpha = 1;
      ctx.strokeStyle = THEME.blood;
      ctx.lineWidth = 3;
      const ang = Math.atan2(geo.b.y - geo.a.y, geo.b.x - geo.a.x) + Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(mid.x + Math.cos(ang) * 7, mid.y + Math.sin(ang) * 7);
      ctx.lineTo(mid.x - Math.cos(ang) * 7, mid.y - Math.sin(ang) * 7);
      ctx.stroke();
    } else if (edge.state === 'hidden') {
      ctx.globalAlpha = 1;
      ctx.font = FONT;
      ctx.textAlign = 'center';
      ctx.fillStyle = THEME.arcaneHigh;
      ctx.fillText('?', mid.x, mid.y);
    }
    if (edge.one_way) {
      const tip = quad(geo.a, geo.c, geo.b, 0.84);
      const tail = quad(geo.a, geo.c, geo.b, 0.74);
      const ang = Math.atan2(tip.y - tail.y, tip.x - tail.x);
      ctx.globalAlpha = 1;
      ctx.fillStyle = style.colour;
      ctx.beginPath();
      ctx.moveTo(tip.x, tip.y);
      ctx.lineTo(tip.x - Math.cos(ang - 0.5) * 10, tip.y - Math.sin(ang - 0.5) * 10);
      ctx.lineTo(tip.x - Math.cos(ang + 0.5) * 10, tip.y - Math.sin(ang + 0.5) * 10);
      ctx.closePath();
      ctx.fill();
    }
    if (lit) {
      ctx.globalAlpha = 1;
      ctx.font = FONT_S;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      const label = String(edge.name || '').toUpperCase();
      const wide = ctx.measureText(label).width;
      ctx.fillStyle = THEME.panel;
      ctx.fillRect(mid.x - wide / 2 - 4, mid.y - 20, wide + 8, 14);
      ctx.strokeStyle = style.colour;
      ctx.lineWidth = 1;
      ctx.strokeRect(mid.x - wide / 2 - 4, mid.y - 20, wide + 8, 14);
      ctx.fillStyle = THEME.ink;
      ctx.fillText(label, mid.x, mid.y - 8);
      ctx.textBaseline = 'middle';
    }
    ctx.restore();
  }

  drawNode(ctx, spot, pulse) {
    const node = spot.node;
    const ramp = RAMPS[BIOME_RAMP[node.biome] || 'stone'] || RAMPS.stone;
    const shift = (node.visuals && node.visuals.palette_shift) || 0;
    const body = shift >= 0 ? mix(ramp[2], '#ffffff', shift * 0.55)
                            : mix(ramp[2], '#000000', -shift * 0.85);
    const x = spot.x - NODE_W / 2;
    const y = spot.y - NODE_H / 2;
    const here = Boolean(node.here);
    const lit = this.hover && this.hover.kind === 'node' && this.hover.id === node.id;
    const chosen = this.selected === node.id;
    const far = node.reachable === false;

    ctx.save();
    if (far) ctx.globalAlpha = 0.5;

    ctx.fillStyle = OUTLINE;
    plate(ctx, x + 2, y + 3, NODE_W, NODE_H);
    ctx.fill();

    plate(ctx, x, y, NODE_W, NODE_H);
    const face = ctx.createLinearGradient(0, y, 0, y + NODE_H);
    face.addColorStop(0, mix(body, ramp[3], 0.5));
    face.addColorStop(1, mix(body, ramp[0], 0.55));
    ctx.fillStyle = face;
    ctx.fill();

    ctx.lineWidth = here || chosen ? 3 : 2;
    ctx.strokeStyle = here ? THEME.goldHigh
      : chosen ? THEME.arcaneHigh
      : lit ? THEME.gold : OUTLINE;
    ctx.stroke();

    // One pixel row of state colour along the bottom edge: the region answering.
    ctx.fillStyle = STATE_TINT[node.state] || THEME.inkFaint;
    ctx.fillRect(x + 6, y + NODE_H - 5, NODE_W - 12, 3);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = FONT;
    ctx.fillStyle = OUTLINE;
    ctx.fillText(node.numeral || '·', spot.x + 1, y + 15);
    ctx.fillStyle = here ? THEME.goldHigh : THEME.bone;
    ctx.fillText(node.numeral || '·', spot.x, y + 14);

    ctx.font = FONT_S;
    const lines = nameLines(node.name);
    lines.forEach((line, i) => {
      const ly = y + NODE_H + 9 + i * 10;
      ctx.fillStyle = OUTLINE;
      ctx.fillText(line.toUpperCase(), spot.x + 1, ly + 1);
      ctx.fillStyle = far ? THEME.inkFaint : chosen ? THEME.arcaneHigh : THEME.inkDim;
      ctx.fillText(line.toUpperCase(), spot.x, ly);
    });

    if (far) {
      // Unreachable is a fact with a reason behind it, and the reason is on the
      // roads. The dashes say "ask the edges", the inspector answers.
      ctx.globalAlpha = 0.9;
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = THEME.blood;
      ctx.lineWidth = 1;
      plate(ctx, x - 3, y - 3, NODE_W + 6, NODE_H + 6);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (here) {
      ctx.globalAlpha = 0.35 + 0.45 * pulse;
      ctx.strokeStyle = THEME.goldHigh;
      ctx.lineWidth = 2;
      plate(ctx, x - 5 - pulse * 2, y - 5 - pulse * 2,
            NODE_W + 10 + pulse * 4, NODE_H + 10 + pulse * 4);
      ctx.stroke();
    }
    ctx.restore();
  }
}

/* ------------------------------------------------------------ descent paint */

const ROOM_RAMP = {
  ENTRANCE: 'bone', ENCOUNTER: 'blood', PUZZLE: 'arcane', TREASURE: 'gold',
  VAULT: 'bronze', STORY: 'cloth', SHRINE: 'cyan', JUNCTION: 'stone',
  BOSS: 'void',
};

const ROOM_GLYPH = {
  ENTRANCE: '↑', ENCOUNTER: '✦', PUZZLE: '◆', TREASURE: '$', VAULT: '⌂',
  STORY: '¶', SHRINE: '†', JUNCTION: '·', BOSS: '☠',
};

/* The descent, as far as it has been walked.
 *
 * The server sends only the rooms already VISITED, plus the doors out of the
 * room you are standing in — the rest of the building is not knowledge the
 * player has. So the map draws what is known at its real coordinates and hangs
 * the unwalked doors off the current room as stubs, which is the honest shape
 * of "there is a way through there and I have not taken it".
 */
class DungeonCanvas {
  constructor(canvas, handlers = {}) {
    this.canvas = canvas;
    this.handlers = handlers;
    this.view = null;
    this.spots = new Map();     // room id -> {x,y,room,ghost,option}
    this.phase = 0;
    this._onDown = (e) => {
      const hit = this.pick(e);
      if (hit && this.handlers.onRoom) this.handlers.onRoom(hit);
    };
    this._onMove = (e) => { this.canvas.style.cursor = this.pick(e) ? 'pointer' : 'default'; };
    canvas.addEventListener('click', this._onDown);
    canvas.addEventListener('mousemove', this._onMove);
  }

  release() {
    this.canvas.removeEventListener('click', this._onDown);
    this.canvas.removeEventListener('mousemove', this._onMove);
  }

  setView(view) {
    this.view = view;
    this.resize();
  }

  resize() {
    if (!this.view || !this.canvas.isConnected) return;
    const box = this.canvas.parentElement;
    this.width = Math.max(320, Math.floor((box ? box.clientWidth : 620) - 26));
    this.height = 380;
    this.ctx = fitCanvas(this.canvas, this.width, this.height);
    this.place();
    this.draw();
  }

  place() {
    const view = this.view || {};
    const rooms = view.rooms || [];
    const run = view.run || {};
    this.spots = new Map();
    if (!rooms.length) return;

    const xs = rooms.map(r => r.x);
    const ys = rooms.map(r => r.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const pad = 54;
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const usableW = this.width - pad * 2;
    const usableH = this.height - pad * 2;
    const scale = Math.min(usableW / spanX, usableH / spanY, 96);
    const offX = (this.width - spanX * scale) / 2;
    const offY = (this.height - spanY * scale) / 2;

    for (const room of rooms) {
      this.spots.set(room.id, {
        id: room.id, room,
        x: Math.round(offX + (room.x - minX) * scale),
        y: Math.round(offY + (room.y - minY) * scale),
        cleared: (run.cleared || []).includes(room.id),
      });
    }
    // Doors out of here that have not been walked. Ringed around the current
    // room because their real position is not yet knowledge the player has.
    const here = this.spots.get(run.at);
    const unwalked = (view.options || []).filter(
      o => o.action === 'move' && !this.spots.has(o.room));
    unwalked.forEach((option, i) => {
      const angle = (-Math.PI / 2) + (i - (unwalked.length - 1) / 2) * 0.85;
      const base = here || { x: this.width / 2, y: this.height / 2 };
      this.spots.set(option.room, {
        id: option.room, ghost: true, option,
        x: Math.round(clamp(base.x + Math.cos(angle) * 108, 40, this.width - 40)),
        y: Math.round(clamp(base.y + Math.sin(angle) * 92, 40, this.height - 40)),
        room: { id: option.room, name: option.name, kind: option.kind, depth: option.depth },
      });
    });
  }

  pick(event) {
    const rect = this.canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    for (const spot of this.spots.values()) {
      if (Math.abs(px - spot.x) <= 22 && Math.abs(py - spot.y) <= 18) return spot;
    }
    return null;
  }

  draw() {
    const ctx = this.ctx;
    if (!ctx || !this.view) return;
    const run = this.view.run || {};
    const pulse = 0.5 + 0.5 * Math.sin(this.phase);
    ctx.fillStyle = '#07060c';
    ctx.fillRect(0, 0, this.width, this.height);

    // A faint grid, so a room's position reads as a position and not a float.
    ctx.strokeStyle = shade(THEME.panel, 6);
    ctx.lineWidth = 1;
    for (let x = 0; x < this.width; x += 24) {
      ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, this.height); ctx.stroke();
    }
    for (let y = 0; y < this.height; y += 24) {
      ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(this.width, y + 0.5); ctx.stroke();
    }

    const link = (a, b, colour, width, dash) => {
      if (!a || !b) return;
      ctx.save();
      ctx.setLineDash(dash || []);
      ctx.strokeStyle = colour;
      ctx.lineWidth = width;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      ctx.restore();
    };

    // The walked trail is the only adjacency the client actually knows.
    const trail = run.trail || [];
    for (let i = 1; i < trail.length; i++) {
      link(this.spots.get(trail[i - 1]), this.spots.get(trail[i]), THEME.edgeHigh, 3);
    }
    const exit = this.view.exit_path || [];
    for (let i = 1; i < exit.length; i++) {
      link(this.spots.get(exit[i - 1]), this.spots.get(exit[i]), THEME.gold, 2, [5, 4]);
    }
    const here = this.spots.get(run.at);
    for (const spot of this.spots.values()) {
      if (!spot.ghost) continue;
      link(here, spot, spot.option && spot.option.available ? THEME.venom : THEME.blood,
           2, [3, 4]);
    }

    for (const spot of this.spots.values()) this.drawRoom(ctx, spot, run, pulse);

    ctx.font = FONT_S;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = THEME.inkFaint;
    ctx.fillText('GOLD DASH = THE WAY OUT FROM HERE', 8, this.height - 8);
  }

  drawRoom(ctx, spot, run, pulse) {
    const room = spot.room || {};
    const ramp = RAMPS[ROOM_RAMP[room.kind] || 'stone'] || RAMPS.stone;
    const w = 40;
    const h = 30;
    const x = spot.x - w / 2;
    const y = spot.y - h / 2;
    const current = room.id === run.at;
    const cleared = spot.cleared;
    const blocked = spot.ghost && spot.option && !spot.option.available;

    ctx.save();
    if (spot.ghost) ctx.globalAlpha = blocked ? 0.42 : 0.72;
    ctx.fillStyle = OUTLINE;
    plate(ctx, x + 2, y + 2, w, h, 5);
    ctx.fill();
    plate(ctx, x, y, w, h, 5);
    ctx.fillStyle = cleared ? mix(ramp[1], '#000000', 0.35) : ramp[2];
    ctx.fill();
    ctx.lineWidth = current ? 3 : 2;
    ctx.strokeStyle = current ? THEME.goldHigh
      : room.kind === 'BOSS' ? THEME.blood
      : blocked ? THEME.blood : OUTLINE;
    ctx.stroke();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = FONT;
    ctx.fillStyle = cleared ? THEME.inkFaint : THEME.ink;
    ctx.fillText(ROOM_GLYPH[room.kind] || '·', spot.x, spot.y - 1);
    if (cleared) {
      ctx.fillStyle = THEME.venom;
      ctx.font = FONT_S;
      ctx.fillText('✔', x + w - 7, y + 7);
    }
    // A room with no name on it is a dot. The name is what makes the map a
    // memory of the descent rather than a diagram of it.
    ctx.font = FONT_S;
    const short = String(room.name || '').length > 10
      ? String(room.name).slice(0, 9) + '…' : String(room.name || '');
    ctx.fillStyle = cleared ? THEME.inkFaint : THEME.inkDim;
    ctx.fillText(short.toUpperCase(), spot.x, y + h + 8);
    if (spot.ghost) {
      ctx.fillStyle = blocked ? THEME.blood : THEME.venom;
      ctx.fillText(blocked ? 'SHUT' : 'OPEN', spot.x, y + h + 18);
    } else {
      ctx.fillStyle = THEME.inkFaint;
      ctx.fillText(`D${room.depth}`, spot.x, y + h + 18);
    }
    if (current) {
      ctx.globalAlpha = 0.3 + 0.5 * pulse;
      ctx.strokeStyle = THEME.goldHigh;
      ctx.lineWidth = 2;
      plate(ctx, x - 5, y - 5, w + 10, h + 10, 6);
      ctx.stroke();
    }
    ctx.restore();
  }
}

/* Kind -> how the strip labels it. The server's `kind` vocabulary is fixed in
 * progression.things_to_do; anything new falls through to a sane default. */
const TODO_KIND = {
  retest:  { tag: 'red',    label: 'RETEST DUE', verb: 'CLEAR' },
  chapter: { tag: 'gold',   label: 'CHAPTER',    verb: 'GO' },
  boss:    { tag: 'red',    label: 'BOSS',       verb: 'FIGHT' },
  dungeon: { tag: 'violet', label: 'DUNGEON',    verb: 'DESCEND' },
  event:   { tag: 'blue',   label: 'THE WORLD',  verb: 'LOOK' },
  travel:  { tag: 'green',  label: 'ROAD',       verb: 'TRAVEL' },
  secret:  { tag: 'violet', label: 'SECRET',     verb: 'SEARCH' },
  build:   { tag: 'orange', label: 'UNSPENT',    verb: 'SPEND' },
  train:   { tag: '',       label: 'TRAINING',   verb: 'TRAIN' },
  shrine:  { tag: 'blue',   label: 'SHRINE',     verb: 'ANSWER' },
  repair:  { tag: 'orange', label: 'REPAIR',     verb: 'MEND' },
  explore: { tag: 'green',  label: 'EXPLORE',    verb: 'WALK' },
};

/* What to tell the player when main.js gave us no onAction for a row. Naming
 * the key beats "nothing happened when I pressed it". */
const DELEGATE_HINT = {
  retest: 'press N on the world screen; a due pattern comes back in disguise.',
  encounter: 'press N on the world screen for the next encounter.',
  boss: 'walk to the boss marker in that region.',
  shrine: 'walk to a shrine marker, or press the MEMORY SHRINE button.',
  allocate: 'open GEAR and spend the points.',
  explore: 'press F on the world screen to search the ground.',
};

/* ============================================================== the screens */

export class WorldUI {
  constructor(hooks = {}) {
    this.hooks = hooks;
    this.s = null;              // the dashboard payload, as main.js last read it
    this.host = null;
    this.screen = '';           // 'overworld' | 'descent'
    this.selected = null;       // region under inspection on the map
    this.descent = null;        // the api.dungeon() payload while a run is open
    this.dungeonRegion = null;  // which region's list opened this descent
    this.map = null;
    this.dmap = null;
    this.busy = false;          // one world POST at a time; two is a double walk
    this.queue = [];            // world events waiting their turn on screen
    this.herald = null;         // the announcement node, while one is up
    this.heraldKey = null;      // its Escape handler, while one is up
    this.heraldTimers = [];     // its reveal beats, so a dismissal can kill them
    this.todoHosts = [];        // every node the strip is mounted into
    this.dungeonCards = {};     // api.dungeons() flavour, by dungeon id
    this.fetched = null;        // the region whose second opinion we already took
    this.roads = null;          // {region, list} from /api/routes, for that region
    this.timers = new Set();
    this.raf = 0;
    this.last = 0;
    this.onResize = () => {
      if (this.map) this.map.resize();
      if (this.dmap) this.dmap.resize();
    };
    window.addEventListener('resize', this.onResize);
  }

  /* ------------------------------------------------------------ lifecycle */

  /** Every path that takes a screen away goes through here. A previous pass in
   *  this codebase fixed four timer leaks; the rule since is that anything that
   *  ticks is registered the moment it is created. */
  clearTimers() {
    for (const id of this.timers) { clearTimeout(id); clearInterval(id); }
    this.timers.clear();
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
  }

  later(fn, ms) {
    const id = setTimeout(() => { this.timers.delete(id); fn(); }, ms);
    this.timers.add(id);
    return id;
  }

  destroy() {
    this.dismissHerald();
    this.clearTimers();
    this.releaseCanvases();
    window.removeEventListener('resize', this.onResize);
    this.host = null;
    this.screen = '';
  }

  releaseCanvases() {
    if (this.map) { this.map.release(); this.map = null; }
    if (this.dmap) { this.dmap.release(); this.dmap = null; }
  }

  /* One loop drives both canvases. It exists for the two-second breath on the
   * region you are standing in and on the room you are standing in — nothing
   * else on either canvas animates, so it is cheap and it is cancellable. */
  paintLoop() {
    if (this.raf) return;
    const tick = (now) => {
      this.raf = 0;
      const liveMap = this.map && this.map.canvas.isConnected;
      const liveDescent = this.dmap && this.dmap.canvas.isConnected;
      // #panel-body outlives whatever was inside it, so the host being attached
      // proves nothing. The canvases are the screen; when both are gone, so is
      // the reason to keep a frame callback alive.
      if (!liveMap && !liveDescent) return;
      if (now - this.last > 42) {
        this.last = now;
        const phase = now / 520;
        if (liveMap) { this.map.phase = phase; this.map.draw(); }
        if (liveDescent) { this.dmap.phase = phase; this.dmap.draw(); }
      }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  /* --------------------------------------------------------------- chrome */

  toast(title, body, kind = '') {
    if (this.hooks.toast) { this.hooks.toast(title, body, kind); return; }
    // main.js owns #toasts; borrowing it is better than inventing a second
    // notification surface, and the timers below are registered like any other.
    const rail = $('#toasts');
    if (!rail) return;
    const node = el('div', `toast ${kind}`, `<span class="tt">${esc(title)}</span>${esc(body)}`);
    rail.appendChild(node);
    this.later(() => { node.style.transition = 'opacity .4s'; node.style.opacity = '0'; }, 4200);
    this.later(() => node.remove(), 4800);
  }

  sfx(name) {
    const audio = this.hooks.audio;
    if (audio && audio.sfx) { try { audio.sfx(name); } catch (e) { /* silence is fine */ } }
  }

  /** A door, for the two places on this screen that are doors: the mouth of a
   *  dungeon, and the way back out of one. `heavy` is what makes a dungeon
   *  sound like a dungeon rather than like a shop. */
  door(closing, opts) {
    const audio = this.hooks.audio;
    if (audio && audio.door) { try { audio.door(!!closing, opts || {}); } catch (e) { /* silence is fine */ } }
  }

  /** WALKING IS A SOUND. Travelling a road and moving between dungeon rooms are
   *  both the player covering ground, and both were silent — a chime played and
   *  then the screen was somewhere else. `n` steps, staggered past footstep()'s
   *  own 55ms throttle, on the material the place is made of. */
  steps(terrain = 'stone', n = 3, opts = {}) {
    const audio = this.hooks.audio;
    if (!audio || !audio.footstep) return 0;
    for (let i = 0; i < n; i++) {
      const at = i * 155;
      const fire = () => {
        try { audio.footstep(terrain, { gain: 0.9, ...opts }); } catch (e) { /* silence is fine */ }
      };
      if (!i) fire(); else this.later(fire, at);
    }
    return n;
  }

  /** The last resort way home: main.js's own WORLD button, which is in the
   *  document whether or not this file was handed an onBack. */
  back() {
    if (this.hooks.onBack) { this.hooks.onBack(); return; }
    const nav = $('[data-nav="world"]');
    if (nav) nav.click();
  }

  /** Show a "no" the way the rules require: a sealed refusal prints the exam's
   *  own sentence and nothing of ours. Returns true when it WAS a refusal, so
   *  callers read it as `if (this.refused(res)) return;`. */
  refused(res, title = 'THE WORLD SAYS NO') {
    const text = refusalText(res);
    if (!text) return false;
    if (isSealed(res)) {
      // The message is the exam's, verbatim. `herald` is the exam's own title
      // for the refusal when it sends one; otherwise the capability it took is
      // the title, because SEALED alone does not say which door shut.
      this.sfx('error');
      this.toast(res.herald || sealedTitle(res), text, 'red');
      return true;
    }
    this.sfx('error');
    this.toast(title, text, 'red');
    return true;
  }

  /* ----------------------------------------------------------------- data */

  /** Re-read the dashboard. main.js owns the canonical copy, so it gets first
   *  refusal; api.state() is the fallback for a host that did not wire a hook. */
  async reload() {
    // A fresh dashboard makes every per-region second opinion stale too.
    this.fetched = null;
    try {
      if (this.hooks.onRefresh) {
        const next = await this.hooks.onRefresh();
        if (next && next.world) { this.s = next; return this.s; }
      }
      const fresh = await api.state();
      if (fresh && fresh.world) this.s = fresh;
    } catch (err) {
      this.toast('THE MAP DID NOT REDRAW', err.message, 'red');
    }
    return this.s;
  }

  /** Just the map. /api/state rebuilds eleven modules to answer; /api/world-map
   *  answers the one question a road that just opened actually changed. */
  async refreshMap() {
    const res = await api.worldMap();
    if (this.refused(res, 'THE MAP IS SEALED')) return false;
    if (!res || !Array.isArray(res.nodes)) return false;
    if (!this.s) this.s = { world: res, todo: [] };
    else this.s.world = res;
    return true;
  }

  world() {
    return (this.s && this.s.world) || { nodes: [], edges: [], here: '', events: {} };
  }

  regionNode(id) {
    return this.world().nodes.find(n => n.id === id) || null;
  }

  /** Shortest walk from where the player stands to a region, as route ids.
   *  Returns null when no passable chain exists — the caller then has to say
   *  what is in the way rather than greying a button out in silence. */
  pathTo(regionId) {
    const world = this.world();
    const here = world.here;
    if (!here || here === regionId) return [];
    const out = new Map();
    const link = (from, to, id) => {
      if (!out.has(from)) out.set(from, []);
      out.get(from).push({ id, to });
    };
    for (const edge of world.edges) {
      if (!edge.passable) continue;
      link(edge.from, edge.to, edge.id);
      if (!edge.one_way) link(edge.to, edge.from, edge.id);
    }
    const seen = new Set([here]);
    const queue = [[here, []]];
    while (queue.length) {
      const [at, trail] = queue.shift();
      for (const edge of out.get(at) || []) {
        if (seen.has(edge.to)) continue;
        if (edge.to === regionId) return trail.concat([edge.id]);
        seen.add(edge.to);
        queue.push([edge.to, trail.concat([edge.id])]);
      }
    }
    return null;
  }

  /** Why a region cannot be walked to: the gates on the roads that touch it,
   *  in the server's own words. */
  blockedBy(regionId) {
    return this.world().edges
      .filter(e => (e.to === regionId || e.from === regionId) && !e.passable)
      .map(e => ({ id: e.id, name: e.name, state: e.state,
                   requirement: e.requirement, percent: e.percent }));
  }

  /* --------------------------------------------------------------- travel */

  /** Walk one road. Every refusal the server can give is an answer here, not an
   *  exception, so the only thing to do with one is print it. */
  async travel(routeId) {
    if (this.busy) return false;
    const owner = this.host;
    this.busy = true;
    try {
      const res = await api.travel(routeId);
      this.hooks.onTravelResponse?.(res);
      if (owner !== this.host || !owner?.isConnected) return false;
      if (this.refused(res, 'THE ROAD IS CLOSED')) return false;
      this.sfx('unlock');
      // Four paces of road under you. The `unlock` above is the gate; this is
      // the walk, and without it travelling between regions was a menu click.
      this.steps('stone', 4);
      const world = res.world || {};
      if (world.events && world.events.length) this.queue.push(...world.events);
      if (this.hooks.onRegion && res.region) this.hooks.onRegion(res.region, res);
      return true;
    } catch (err) {
      this.toast('THE ROAD IS CLOSED', err.message, 'red');
      return false;
    } finally {
      this.busy = false;
    }
  }

  /** Walk a whole chain of roads. It stops at the first refusal and says which
   *  road refused, because being dropped halfway with no explanation is the
   *  exact failure this screen exists to remove. */
  async walkTo(regionId) {
    const world = this.world();
    if (regionId === world.here) { this.selected = regionId; this.render(); return; }
    const path = this.pathTo(regionId);
    const node = this.regionNode(regionId);
    const name = node ? node.name : regionId;
    if (path === null) {
      const gates = this.blockedBy(regionId);
      this.toast('NO ROAD YET', gates.length
        ? `${name} — ${gates[0].requirement} (${gates[0].percent}%).`
        : `Nothing on your map runs to ${name} yet.`, 'red');
      this.selected = regionId;
      this.render();
      return;
    }
    for (const routeId of path) {
      const ok = await this.travel(routeId);
      if (!ok) break;
    }
    await this.reload();
    this.selected = this.world().here;
    this.render();
    this.drainQueue();
  }

  /* ------------------------------------------------------------ todo strip */

  /* The most valuable six rows on the screen for a player who does not know
   * what to do next. The server guarantees the list is never empty and that
   * every row carries a `why` and an `action`, so this renders unconditionally
   * and clicks straight through — a suggestion you cannot act on is a reproach. */
  mountTodo(host, state) {
    if (state) this.s = state;
    if (!host) return;
    // The strip is worth having in two places at once — beside the map and down
    // the side of the world screen — so every mount is remembered and every
    // repaint reaches all of them.
    if (!this.todoHosts.includes(host)) this.todoHosts.push(host);
    this.paintTodo();
  }

  paintTodo() {
    this.todoHosts = this.todoHosts.filter(h => h && h.isConnected);
    for (const host of this.todoHosts) this.paintTodoInto(host);
  }

  paintTodoInto(host) {
    const rows = (this.s && this.s.todo) || [];
    host.innerHTML = '';
    host.appendChild(el('div', 'section-title', 'WHAT TO DO NEXT'));
    if (!rows.length) {
      // The endpoint promises this cannot happen. If it ever does, the player
      // still gets a way forward rather than an empty box.
      const fallback = el('div', 'list-item',
        `<span class="t">TRAIN AT THE CAMP</span>
         <span class="d">The board came back empty, which it is not supposed to.
         The Camp always has work at your level.</span>`);
      fallback.onclick = () => this.delegate({ kind: 'encounter' }, { title: 'Train at the Camp' });
      host.appendChild(fallback);
      return;
    }
    rows.forEach((entry, i) => host.appendChild(this.todoRow(entry, i)));
    host.appendChild(el('p', 'small muted',
      'Ordered by what your evidence says would help most — not by what is '
      + 'shiniest, and not by what you have not touched lately.'));
  }

  todoRow(entry, index) {
    const meta = TODO_KIND[entry.kind] || { tag: '', label: String(entry.kind || '').toUpperCase(), verb: 'GO' };
    const hops = entry.hops === 0 ? 'right here'
      : entry.hops === 1 ? 'one road away'
      : entry.hops === undefined || entry.hops === null ? ''
      : `${entry.hops} roads away`;
    const where = [entry.region_name, hops].filter(Boolean).join(' · ');
    const row = el('div', 'list-item');
    if (index === 0) {
      row.style.borderColor = 'var(--gold)';
      row.style.background = 'var(--panel-3)';
    }
    row.innerHTML = `
      <div style="display:flex;gap:10px;align-items:flex-start">
        <span class="pixel" style="flex:0 0 30px;color:var(--ink-faint);font-size:11px;
          padding-top:2px">${String(index + 1).padStart(2, '0')}</span>
        <span class="grow">
          <span class="t">${esc(meta.label)}${where ? ` · ${esc(where)}` : ''}</span>
          <span class="d"><b style="color:var(--ink)">${esc(entry.title)}</b><br>
            ${esc(entry.why || '')}</span>
        </span>
        <span class="tag ${meta.tag}" style="flex:0 0 auto">${esc(meta.verb)} ▸</span>
      </div>`;
    row.onclick = () => this.doTodo(entry);
    return row;
  }

  async doTodo(entry) {
    const action = entry.action || {};
    this.sfx('select');
    if (action.kind === 'travel') return this.walkTo(action.region || entry.region);
    if (action.kind === 'dungeon') return this.enterDungeon(action.dungeon, entry.region);
    if (action.kind === 'objective') return this.showEvent(action.event);
    if (action.kind === 'explore') {
      // Walk there first; searching the ground of a region you are not standing
      // in is the kind of thing that silently does nothing.
      await this.walkTo(action.region || entry.region);
      return this.delegate(action, entry);
    }
    return this.delegate(action, entry);
  }

  /** Rows this file does not own — an encounter, a boss, a shrine, spending
   *  points. main.js runs those. Without a hook the player is put back on the
   *  world screen and told plainly which key does it, rather than left pressing
   *  a row that does nothing. */
  delegate(action, entry) {
    if (this.hooks.onAction) { this.hooks.onAction(action, entry || {}); return; }
    this.back();
    this.toast('OUT ON THE MAP',
      `${(entry && entry.title) || 'That'} — ${DELEGATE_HINT[action.kind]
        || 'it is done from the world screen.'}`);
  }

  async refreshTodo() {
    const res = await api.todo();
    if (this.refused(res, 'THE BOARD IS SEALED')) return;
    if (res && Array.isArray(res.todo) && this.s) {
      this.s.todo = res.todo;
      this.paintTodo();
    }
  }

  /* -------------------------------------------------------------- overworld */

  async mountOverworld(host, state) {
    if (state) this.s = state;
    if (!host) return;
    this.host = host;
    this.screen = 'overworld';
    // A caller with no dashboard to hand over still gets a map; the map has its
    // own endpoint and the strip has its own endpoint.
    if (!this.s || !this.s.world) { await this.refreshMap(); await this.refreshTodo(); }
    if (!this.selected || !this.regionNode(this.selected)) this.selected = this.world().here;
    this.render();
    this.drainQueue();
  }

  render() {
    if (!this.host || !this.host.isConnected) return;
    if (this.screen === 'descent') this.renderDescent();
    else this.renderOverworld();
  }

  renderOverworld() {
    const world = this.world();
    this.releaseCanvases();
    this.host.innerHTML = `
      <h2 class="pixel" style="color:var(--gold);font-size:15px;margin:0 0 14px">
        THE OVERWORLD</h2>
      <div class="frame" style="padding:14px;margin-bottom:12px" id="wui-todo"></div>
      <div style="display:grid;grid-template-columns:minmax(0,2.1fr) minmax(270px,1fr);
                  gap:12px;align-items:start">
        <div class="frame" style="padding:12px">
          <canvas id="wui-map" style="display:block;image-rendering:pixelated"></canvas>
          <div id="wui-legend" class="small" style="margin-top:10px;display:flex;
               gap:14px;flex-wrap:wrap;color:var(--ink-dim)"></div>
        </div>
        <div class="frame" style="padding:14px" id="wui-inspect"></div>
      </div>
      <div class="frame" style="padding:14px;margin-top:12px" id="wui-events"></div>
      <div class="actions" style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
        <button class="btn" id="wui-back">◀ BACK TO THE WORLD</button>
        <button class="btn" id="wui-recentre">CENTRE ON ME</button>
        <button class="btn" id="wui-reload">REDRAW</button>
      </div>`;

    this.mountTodo($('#wui-todo', this.host), null);
    this.paintLegend();

    this.map = new MapCanvas($('#wui-map', this.host), {
      onNode: (id) => { this.sfx('tick'); this.select(id); },
      onEdge: (id) => this.tapEdge(id),
      onHover: () => { /* the canvas repaints itself; nothing else cares */ },
    });
    this.map.selected = this.selected;
    this.map.setWorld(world);

    this.renderInspector();
    this.freshenRegion(this.selected);
    this.renderEvents();

    $('#wui-back', this.host).onclick = () => { this.sfx('select'); this.back(); };
    $('#wui-recentre', this.host).onclick = () => { this.sfx('tick'); this.select(world.here); };
    $('#wui-reload', this.host).onclick = async () => {
      await this.reload();
      await this.refreshMap();
      this.render();
    };
    this.paintLoop();
  }

  paintLegend() {
    const host = $('#wui-legend', this.host);
    if (!host) return;
    const swatch = (colour, dash, text) =>
      `<span style="display:inline-flex;align-items:center;gap:6px">
         <span style="width:22px;height:0;border-top:3px ${dash} ${colour}"></span>
         ${esc(text)}</span>`;
    host.innerHTML = [
      swatch(THEME.gold, 'solid', 'open road'),
      swatch(THEME.ember, 'dashed', 'open, and above your level'),
      swatch(THEME.blood, 'dashed', 'gated — the reason is on it'),
      swatch(THEME.inkFaint, 'dotted', 'not on your map yet'),
      `<span style="color:${THEME.goldHigh}">▣ you are here</span>`,
      `<span>region state:
        <span class="tag">ruined</span>
        <span class="tag orange">stirring</span>
        <span class="tag green">restored</span>
        <span class="tag gold">transformed</span></span>`,
    ].join('');
  }

  select(regionId) {
    this.selected = regionId;
    if (this.map) { this.map.selected = regionId; this.map.draw(); }
    this.renderInspector();
    this.freshenRegion(regionId);
  }

  /** The dashboard's node for a region is already a full region_view, so this
   *  is not a fix — it is a second opinion taken once per selection, which is
   *  how a boss cleared five minutes ago stops showing as standing. */
  async freshenRegion(regionId) {
    if (this.fetched === regionId) return;
    this.fetched = regionId;
    let region; let dungeonList; let roads;
    try {
      [region, dungeonList, roads] = await Promise.all([
        api.region(regionId), api.dungeons(regionId), api.routes(regionId),
      ]);
    } catch (err) {
      // The inspector is already drawn from the dashboard's own copy of this
      // region, so the screen survives this. Clearing `fetched` is what lets
      // selecting the region again try for the fresher answer.
      this.fetched = null;
      this.toast('THE SECOND OPINION DID NOT ARRIVE', err.message, 'red');
      return;
    }
    if (this.selected !== regionId || !this.host || !this.host.isConnected) return;
    // /api/routes knows about hidden roads this player has already FOUND, which
    // the world map deliberately does not draw until the Cartographer's sheet.
    if (roads && Array.isArray(roads.routes)) {
      this.roads = { region: regionId, list: roads.routes };
    }
    if (region && !region.error) {
      const nodes = this.world().nodes;
      const index = nodes.findIndex(n => n.id === regionId);
      if (index >= 0) nodes[index] = { ...nodes[index], ...region };
    }
    if (dungeonList && Array.isArray(dungeonList.dungeons)) {
      this.dungeonCards = this.dungeonCards || {};
      for (const card of dungeonList.dungeons) this.dungeonCards[card.id] = card;
    }
    this.renderInspector();
  }

  renderInspector() {
    if (!this.host || !this.host.isConnected) return;
    const host = $('#wui-inspect', this.host);
    if (!host) return;
    const world = this.world();
    const node = this.regionNode(this.selected) || this.regionNode(world.here);
    if (!node) {
      host.innerHTML = '<p class="small muted">The map came back with no regions '
        + 'on it. Press REDRAW.</p>';
      return;
    }
    const here = node.id === world.here;
    const touching = world.edges.filter(e => e.from === node.id || e.to === node.id);
    const cards = this.dungeonCards || {};

    host.innerHTML = `
      <div class="section-title">${esc(node.numeral ? node.numeral + ' · ' : '')}${esc(String(node.name || '').toUpperCase())}</div>
      <p class="small" style="margin:0 0 8px">
        <span class="tag ${STATE_TAG[node.state] || ''}">${esc(node.state)}</span>
        <span class="tag">danger ${esc(node.danger)}</span>
        <span class="tag ${here ? 'gold' : node.reachable ? 'blue' : 'red'}">${
          here ? 'you are here'
            : node.reachable ? `${node.hops} road${node.hops === 1 ? '' : 's'} away`
            : 'no road yet'}</span>
      </p>
      <p class="small">${esc(node.blurb)}</p>
      <p class="small muted">${esc(node.state_prose || '')}</p>
      ${node.next_state ? `<div class="section-title">TOWARD ${esc(node.next_state.toUpperCase())}</div>
        <p class="small">${esc(node.toward_next || '')}</p>` : `
        <p class="small" style="color:var(--gold)">${esc(node.toward_next || '')}</p>`}
      <div class="section-title">ROADS</div>
      <div id="wui-roads"></div>
      ${(node.bosses || []).length ? `<div class="section-title">BOSSES</div>
        ${node.bosses.map(b => `<div class="gate ${b.cleared ? 'pass' : 'fail'}">
          <span class="mark">${b.cleared ? '✔' : '·'}</span>
          <span>${esc(b.name)}${b.cleared ? '' : ' — still standing'}</span></div>`).join('')}` : ''}
      ${this.keysBlock(node)}
      ${this.portalBlock(node)}
      ${(node.dungeons || []).length ? `<div class="section-title">DUNGEONS</div>
        <div id="wui-dungeons"></div>` : ''}
      ${node.pet ? `<div class="section-title">SOMETHING IS HIDING HERE</div>
        <p class="small">${esc(node.pet.hint || node.pet.blurb || '')}</p>` : ''}`;

    const roadHost = $('#wui-roads', host);
    const known = (this.roads && this.roads.region === node.id ? this.roads.list : [])
      .filter(r => !touching.some(t => t.id === r.id));
    const roads = touching.concat(known);
    if (!roads.length) {
      roadHost.appendChild(el('p', 'small muted',
        'No road on your map touches this place. That is a thing to fix, not a wall.'));
    }
    for (const edge of roads) roadHost.appendChild(this.roadRow(edge, node, world));

    const dungeonHost = $('#wui-dungeons', host);
    if (dungeonHost) {
      for (const dungeon of node.dungeons) {
        dungeonHost.appendChild(this.dungeonRow(dungeon, cards[dungeon.id] || {}, node));
      }
    }
  }

  /* WHAT THIS GROUND OWES, OR HAS ALREADY PAID.
   *
   * A key is drawn on the region it comes from rather than hidden in a menu,
   * because the whole point of the key system is that geography is the reward:
   * you go there, you beat the thing that lives there, and a road opens. Naming
   * the road on the map is what turns "a trophy" into "a reason to go".
   *
   * `node.keys` is progression.region_view's own list and is derived from the
   * kill list — there is no keyring in the save to disagree with it. */
  keysBlock(node) {
    const keys = node.keys || [];
    if (!keys.length) return '';
    return `<div class="section-title">KEYS HELD HERE</div>
      ${keys.map(k => `<div class="gate ${k.held ? 'pass' : 'fail'}"
           style="${k.held ? `border-left:3px solid ${esc(k.colour)}` : ''}">
        <span class="mark">${k.held ? '✦' : '·'}</span>
        <span>${esc(k.name)}${k.held
          ? ` — opens ${esc(k.opens || '')}`
          : ' — still on whatever is holding it'}</span></div>`).join('')}`;
  }

  /* THE STANDING PORTAL, drawn on the one region it stands in.
   *
   * Fourteen wards for fourteen bosses, and the sentence underneath is not
   * decoration: this is the screen a player is most likely to misread as "the
   * exam is behind all of this". It is not, it never will be, and the panel
   * says so with the count sitting right next to it. */
  portalBlock(node) {
    const portal = node.portal;
    if (!portal) return '';
    const held = portal.held | 0;
    const need = portal.required | 0;
    const open = !!portal.open;
    return `<div class="section-title" style="color:${
      esc(open ? portal.accent || 'var(--gold-hi)' : 'var(--violet)')}">
        ${esc(String(portal.name || 'THE STANDING PORTAL'))}</div>
      <p class="small">${esc(portal.where || '')}</p>
      <p class="small">
        <span class="tag ${open ? 'gold' : ''}">${held} / ${need} WARDS LIT</span>
        ${open ? '<span class="tag green">OPEN</span>' : ''}</p>
      <span class="bar" style="margin-top:4px"><i style="width:${
        clamp(need ? (held / need) * 100 : 0, 0, 100)}%;background:${
        esc(open ? 'var(--gold-hi)' : 'var(--violet)')}"></i></span>
      <p class="small muted" style="margin-top:6px">${esc(portal.line || '')}</p>
      <p class="small muted">It stands in front of the story's last room and in
        front of nothing else. The practical is a measurement and is on the menu
        right now, with none of these keys.</p>`;
  }

  roadRow(edge, node, world) {
    const style = routeStyle(edge.state);
    const other = edge.from === node.id ? edge.to_name || edge.to : edge.from;
    const otherNode = this.regionNode(edge.from === node.id ? edge.to : edge.from);
    // Walkable right now means: passable, touching the region you are standing
    // in, and not pointing the wrong way up a one-way road.
    const walkable = edge.passable && (edge.from === world.here
      || (edge.to === world.here && !edge.one_way));
    const row = el('div', `list-item ${edge.passable ? '' : 'locked'}`);
    row.innerHTML = `
      <span class="t" style="color:${style.colour}">${esc(edge.name)} · ${esc(style.label)}</span>
      <span class="d">${esc(edge.kind)} to ${esc(otherNode ? otherNode.name : other)}${
        edge.one_way ? ' — one way only' : ''}<br>
        ${esc(edge.prose || '')}
        ${!edge.passable ? `<br><b style="color:var(--red)">${esc(edge.requirement || 'closed')}</b>
          <span class="bar" style="margin-top:5px"><i style="width:${clamp(edge.percent || 0, 0, 100)}%;
            background:var(--orange)"></i></span>` : ''}
        ${edge.warning ? `<br><span style="color:var(--orange)">${esc(edge.warning)}</span>` : ''}
      </span>`;
    if (walkable) {
      row.title = `Walk ${edge.name}`;
      row.onclick = () => this.tapEdge(edge.id);
    } else if (edge.state === 'hidden') {
      row.classList.remove('locked');
      row.title = 'Survey the mark';
      row.onclick = () => this.surveyRoute(edge);
    } else {
      row.onclick = () => this.tapEdge(edge.id);
    }
    return row;
  }

  dungeonRow(dungeon, card, node) {
    const open = dungeon.open !== false;
    const row = el('div', `list-item ${open ? '' : 'locked'}`);
    row.innerHTML = `
      <span class="t">${esc(dungeon.name)} · ${esc(dungeon.floors)} FLOORS${
        dungeon.cleared ? ' · CLEARED' : ''}</span>
      <span class="d">${esc(dungeon.blurb || card.blurb || '')}
        ${card.rule ? `<br><span class="muted">rule: ${esc(String(card.rule).replace(/_/g, ' '))}${
          card.lesson ? ` — ${esc(card.lesson)}` : ''}</span>` : ''}
        ${open ? '' : `<br><b style="color:var(--red)">${esc(dungeon.requirement || 'sealed')}</b>`}</span>`;
    if (open) row.onclick = () => this.enterDungeon(dungeon.id, node.id);
    else row.onclick = () => this.toast(String(dungeon.name).toUpperCase(),
      dungeon.requirement || 'The door is not open yet.', 'red');
    return row;
  }

  /** Clicking a road. An open one is walked; a closed one says why, in the
   *  server's words, and stays on the map where it can be aimed at. */
  async tapEdge(routeId) {
    const world = this.world();
    // A road found by exploration is on /api/routes before it is on the map, so
    // both lists are searched or the row would be a button that does nothing.
    const edge = world.edges.find(e => e.id === routeId)
      || ((this.roads && this.roads.list) || []).find(e => e.id === routeId);
    if (!edge) return;
    const touchesHere = edge.from === world.here || edge.to === world.here;
    const target = edge.to === world.here ? edge.from : edge.to;
    if (!edge.passable) {
      if (edge.state === 'hidden') return this.surveyRoute(edge);
      this.toast(String(edge.name).toUpperCase(),
        `${edge.requirement}${edge.percent ? ` — ${edge.percent}% of the way there.` : '.'}`,
        'red');
      this.select(target);
      return;
    }
    if (!touchesHere) {
      // Passable, but not from here: walk the chain rather than refusing on a
      // technicality the player cannot see from the map.
      return this.walkTo(target);
    }
    if (edge.to === world.here && edge.one_way) {
      this.toast(String(edge.name).toUpperCase(), 'That road only runs the other way.', 'red');
      return;
    }
    const ok = await this.travel(routeId);
    if (!ok) return;
    await this.reload();
    this.selected = this.world().here;
    this.render();
    this.toast('ON THE ROAD', `${edge.name} — ${this.regionNode(target)
      ? this.regionNode(target).name : target}.`, 'gold');
    this.drainQueue();
  }

  /** A hidden road drawn as a question mark is the one unlock exploration alone
   *  can buy. Pressing it asks the server; the server decides. */
  async surveyRoute(edge) {
    const res = await api.discoverRoute(edge.id);
    if (isSealed(res)) { this.refused(res); return; }
    if (res && res.ok === false) {
      this.toast(String(edge.name || 'THE MARK').toUpperCase(),
        res.reason || 'The mark means nothing yet.');
      return;
    }
    if (res && res.ok) {
      this.sfx('unlock');
      this.toast('ON YOUR MAP', res.announce || `${res.name} is on your map.`, 'gold');
      // Only the map changed, so only the map is re-read.
      await this.refreshMap();
      this.fetched = null;
      this.render();
      return;
    }
    this.refused(res, 'NOTHING THERE');
  }

  /* ----------------------------------------------------------- world events */

  async renderEvents() {
    if (!this.host || !this.host.isConnected) return;
    const host = $('#wui-events', this.host);
    if (!host) return;
    this.paintEvents(host, this.world().events || {});
    const fresh = await api.events();
    if (!host.isConnected || !fresh || fresh.error) return;
    this.paintEvents(host, fresh);
  }

  paintEvents(host, events) {
    const fired = events.fired || [];
    const upcoming = events.upcoming || [];
    host.innerHTML = `
      <div class="section-title">THE WORLD'S NEXT MOVE — ${fired.length}/${
        events.total || fired.length + upcoming.length} SO FAR</div>
      ${upcoming.length ? upcoming.map(e => `
        <div class="list-item" style="cursor:default">
          <span class="t">${esc(e.title)}${e.region ? ` · ${esc(String(e.region).replace(/_/g, ' '))}` : ''}</span>
          <span class="d">${esc(e.requirement)}
            <span class="bar" style="margin-top:6px"><i style="width:${
              clamp(e.percent || 0, 0, 100)}%;background:var(--violet)"></i></span>
            <span class="muted">${esc(e.percent)}% there</span></span>
        </div>`).join('')
        : '<p class="small muted">Nothing is pending. Everything the world had to '
          + 'say about your evidence, it has said.</p>'}
      ${fired.length ? `<div class="section-title">ALREADY HAPPENED</div>
        <p class="small muted">${fired.slice(-4).map(e => esc(e.title)).join(' · ')}</p>` : ''}`;
  }

  /** Find one upcoming event and say what it is waiting for. The todo strip
   *  offers this as a row, and a row has to lead somewhere. */
  async showEvent(eventId) {
    const events = this.world().events || {};
    const row = [...(events.upcoming || []), ...(events.fired || [])]
      .find(e => e.id === eventId);
    if (!row) { this.toast('THE WORLD', 'That beat is not on the board any more.'); return; }
    if (row.requirement) {
      this.toast(String(row.title || 'THE WORLD').toUpperCase(),
        `${row.requirement} — ${row.percent}% of the way there.`, 'gold');
    } else {
      this.announce([{ ...row, prose: row.prose || '', changes: [], routes_opened: [] }]);
    }
    if (row.region) this.select(row.region);
  }

  /* ---------------------------------------------------------- the descent */

  async enterDungeon(dungeonId, regionId) {
    if (this.busy) return;
    this.busy = true;
    try {
      const res = await api.enterDungeon(dungeonId);
      if (this.refused(res, 'THE DOOR DOES NOT OPEN')) return;
      if (!res || !res.dungeon) {
        this.toast('THE DOOR DOES NOT OPEN', 'The descent came back empty.', 'red');
        return;
      }
      this.sfx('unlock');
      // The mouth of the dungeon. Heavy, because it is.
      this.door(false, { heavy: true });
      this.descent = res;
      this.dungeonRegion = regionId || this.world().here;
      this.screen = 'descent';
      this.render();
    } finally {
      this.busy = false;
    }
  }

  /** Open the run view for a descent that is already in progress — s.dungeon is
   *  non-null whenever there is one, and it survives leaving the screen. */
  async mountDescent(host, state) {
    if (state) this.s = state;
    if (host) this.host = host;
    if (!this.host) return;
    const res = await api.dungeon();
    if (this.refused(res, 'THE DESCENT IS SEALED')) { this.screen = 'overworld'; this.render(); return; }
    if (!res || !res.dungeon) {
      this.toast('NO DESCENT OPEN', 'You are not in a dungeon. Pick one off a region.');
      this.screen = 'overworld';
      this.render();
      return;
    }
    this.descent = res;
    this.screen = 'descent';
    this.render();
  }

  renderDescent() {
    const view = this.descent || {};
    const dungeon = view.dungeon || {};
    const run = view.run || {};
    const progress = view.progress || {};
    const seal = progress.seal || { required: 0, met: true };
    const options = view.options || [];
    this.releaseCanvases();

    const room = (view.rooms || []).find(r => r.id === run.at) || {};
    const boss = run.boss || {};

    this.host.innerHTML = `
      <h2 class="pixel" style="color:var(--gold);font-size:15px;margin:0 0 4px">
        ${esc(String(dungeon.name || 'THE DESCENT').toUpperCase())}</h2>
      <p class="small muted" style="margin:0 0 12px">
        ${esc(String(dungeon.rule || '').replace(/_/g, ' ').toUpperCase())} —
        ${esc(dungeon.rule_note || '')}</p>
      <div class="frame" style="padding:14px;margin-bottom:12px">
        <div class="grid2">
          <div>
            <div class="skill-row"><span class="sn">DEPTH</span>
              <span class="bar"><i style="width:${clamp(
                100 * (progress.depth || 0) / Math.max(1, dungeon.max_depth || 1), 0, 100)}%"></i></span>
              <span class="sv">${esc(progress.depth || 0)}/${esc(dungeon.max_depth || 0)}</span></div>
            <div class="skill-row"><span class="sn">ROOMS SEEN</span>
              <span class="bar"><i style="width:${clamp(
                100 * (progress.visited || 0) / Math.max(1, progress.rooms || 1), 0, 100)}%"></i></span>
              <span class="sv">${esc(progress.visited || 0)}/${esc(progress.rooms || 0)}</span></div>
            <div class="skill-row"><span class="sn">FIGHTS WON</span>
              <span class="bar"><i style="width:${clamp(
                100 * (progress.cleared_fights || 0) / Math.max(1, progress.clearable || 1), 0, 100)}%;
                background:var(--red)"></i></span>
              <span class="sv">${esc(progress.cleared_fights || 0)}/${esc(progress.clearable || 0)}</span></div>
          </div>
          <div>
            <p class="small" style="margin:0 0 6px">
              <span class="tag ${seal.met ? 'green' : 'red'}">${seal.met
                ? 'the chamber is open' : `sealed · ${esc(progress.cleared_fights || 0)}/${esc(seal.required)}`}</span>
              <span class="tag gold">${esc(progress.gold || 0)} gold</span>
              <span class="tag violet">${esc(progress.xp || 0)} xp</span>
              ${progress.shortcut_open ? '<span class="tag blue">shortcut open</span>' : ''}
            </p>
            <p class="small">KEYS: ${(progress.keys || []).length
              ? (progress.keys || []).map(k => `<span class="tag gold">${esc(String(k).replace(/_/g, ' '))}</span>`).join(' ')
              : '<span class="muted">none yet</span>'}</p>
            <p class="small">THE CHAMBER: <b style="color:var(--red)">${esc(
              progress.boss || boss.name || 'something at the bottom')}</b>${
              boss.stance ? ` — ${esc(boss.stance)}` : ''}</p>
            ${boss.taunt ? `<p class="small muted">"${esc(boss.taunt)}"</p>` : ''}
          </div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr);
                  gap:12px;align-items:start">
        <div class="frame" style="padding:12px">
          <canvas id="wui-descent" style="display:block;image-rendering:pixelated"></canvas>
        </div>
        <div class="frame" style="padding:14px">
          <div class="section-title">${esc((room.name || 'HERE').toUpperCase())}</div>
          <p class="small">${esc(room.blurb || '')}</p>
          ${room.story ? `<p class="small" style="color:var(--violet)">${esc(room.story)}</p>` : ''}
          <div class="section-title">WHAT YOU CAN DO</div>
          <div class="stack" id="wui-options"></div>
          <p class="small muted" style="margin-top:10px">
            Walking out is allowed from anywhere, always. A locked door is locked
            on the way in and never on the way out.</p>
        </div>
      </div>
      <div class="actions" style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
        <button class="btn" id="wui-tomap">◀ THE MAP</button>
        <button class="btn" id="wui-refresh">REDRAW</button>
        <button class="btn danger" id="wui-abandon">ABANDON THE DESCENT</button>
      </div>`;

    this.dmap = new DungeonCanvas($('#wui-descent', this.host), {
      onRoom: (spot) => {
        const option = options.find(o => o.action === 'move' && o.room === spot.id);
        if (!option) { this.toast(String(spot.room.name || 'THAT ROOM').toUpperCase(),
          'No door runs from here to there.'); return; }
        if (!option.available) { this.toast('SHUT', option.reason || 'not that way', 'red'); return; }
        this.moveRoom(option.room);
      },
    });
    this.dmap.setView(view);

    // ONE button per entry in `options`, and nothing else. The server asserts
    // that list is never empty and always holds something available; building
    // the buttons any other way throws that guarantee away.
    const host = $('#wui-options', this.host);
    for (const option of options) host.appendChild(this.optionButton(option));

    $('#wui-tomap', this.host).onclick = () => {
      this.sfx('select');
      this.screen = 'overworld';
      this.render();
    };
    $('#wui-refresh', this.host).onclick = () => this.mountDescent(null, null);
    $('#wui-abandon', this.host).onclick = () => this.leaveDungeon();
    this.paintLoop();
  }

  optionButton(option) {
    let label = '';
    let note = '';
    let cls = 'btn';
    if (option.action === 'move') {
      label = `GO · ${String(option.name || 'ROOM').toUpperCase()}`;
      note = `${String(option.kind || '').toLowerCase()} · depth ${option.depth}`;
    } else if (option.action === 'engage') {
      label = `FIGHT WHAT IS HERE · ${String(option.difficulty || '').toUpperCase()}`;
      note = (option.relent || []).length > 1
        ? `it relents through ${option.relent.join(' → ').toLowerCase()} if you miss`
        : 'one room, one problem';
      cls = 'btn danger';
    } else if (option.action === 'retreat') {
      label = `WALK OUT · ${Math.max(0, (option.path || []).length - 1)} ROOMS`;
      note = option.reason || '';
    } else if (option.action === 'leave') {
      label = 'LEAVE THE DUNGEON';
      note = option.reason || '';
      cls = 'btn good';
    } else {
      label = String(option.action || '').toUpperCase();
      note = option.reason || '';
    }
    const btn = el('button', cls,
      `<span style="display:block">${esc(label)}</span>
       <span class="small muted" style="display:block;margin-top:5px;text-transform:none;
         font-family:inherit">${esc(option.available ? note : (option.reason || 'not from here'))}</span>`);
    btn.style.textAlign = 'left';
    btn.disabled = !option.available;
    if (!option.available && option.reason) btn.title = option.reason;
    btn.onclick = () => {
      if (option.action === 'move') return this.moveRoom(option.room);
      if (option.action === 'engage') return this.engage();
      if (option.action === 'retreat') return this.retreat();
      if (option.action === 'leave') return this.leaveDungeon();
      return undefined;
    };
    return btn;
  }

  adopt(res) {
    if (res && res.state && res.state.dungeon) {
      this.descent = res.state;
      this.render();
      return true;
    }
    return false;
  }

  async moveRoom(roomId) {
    if (this.busy) return;
    this.busy = true;
    try {
      const res = await api.dungeonMove(roomId);
      if (res && res.moved === false) {
        // The door said no and handed back what IS open from here. Take the new
        // options first; the reason is the server's own sentence.
        this.toast('NOT THAT WAY', res.reason || 'the door does not give', 'red');
        this.sfx('error');
        this.adopt(res);
        return;
      }
      if (this.refused(res, 'NOT THAT WAY')) return;
      this.sfx('tick');
      // A room is a walk, not a jump cut. Stone, because a dungeon is.
      this.steps('stone', 3);
      this.adopt(res);
      const room = res.room || {};
      if (room.name) {
        this.toast(String(room.name).toUpperCase(),
          room.blurb || `depth ${res.depth}.`, room.kind === 'BOSS' ? 'red' : '');
      }
      if (room.story) this.narrate(room.name, [room.story]);
    } finally {
      this.busy = false;
    }
  }

  async engage() {
    if (this.busy) return;
    this.busy = true;
    try {
      const res = await api.dungeonEngage();
      if (this.refused(res, 'NOTHING HERE ASKS ANYTHING')) return;
      if (this.hooks.onEncounter) { this.hooks.onEncounter(res); return; }
      // No battle hook: say so rather than sitting there looking broken.
      this.toast('THE ROOM IS WAITING',
        'The encounter is open on the server — the battle screen has to take it '
        + 'from here.', 'red');
    } finally {
      this.busy = false;
    }
  }

  async retreat() {
    if (this.busy) return;
    this.busy = true;
    try {
      const res = await api.dungeonRetreat();
      if (this.refused(res, 'YOU CANNOT WALK OUT')) return;
      this.sfx('select');
      this.steps('stone', 4);
      this.adopt(res);
      this.toast('YOU WALK OUT', `${Math.max(0, (res.path || []).length - 1)} rooms back `
        + 'to the threshold. The descent stays where it is.');
    } finally {
      this.busy = false;
    }
  }

  async leaveDungeon() {
    if (this.busy) return;
    this.busy = true;
    try {
      const res = await api.leaveDungeon();
      if (this.refused(res, 'THE DUNGEON WILL NOT LET GO')) return;
      this.descent = null;
      this.screen = 'overworld';
      // Come back out onto the region the descent was under, not onto whatever
      // was last poked on the map.
      this.selected = this.dungeonRegion || this.world().here;
      this.dungeonRegion = null;
      await this.reload();
      this.render();
      // "The door closes behind you" is the sentence this screen has always
      // printed. Now it is also the sound.
      this.door(true, { heavy: true });
      this.toast('OUT', 'The door closes behind you. What you cleared stays cleared.');
    } finally {
      this.busy = false;
    }
  }

  narrate(who, lines) {
    if (this.hooks.say) { this.hooks.say(String(who || '').toUpperCase(), lines, 'oracle'); return; }
    this.toast(String(who || 'THE ROOM').toUpperCase(), lines.join(' '));
  }

  /* --------------------------------------------------------- world events */

  /** A world event is the map answering the player. It gets a herald and a card
   *  it has to be dismissed out of — a toast that fades in four seconds is the
   *  wrong shape for "a road has opened and the sky has changed". */
  announce(events) {
    if (!events || !events.length) return;
    this.queue.push(...events);
    this.drainQueue();
  }

  drainQueue() {
    if (this.herald || !this.queue.length) return;
    this.showHerald(this.queue.shift());
  }

  showHerald(event) {
    this.dismissHerald();
    const changes = (event.changes || []).map(c => c.detail).filter(Boolean);
    const roads = event.routes_opened || [];
    const wrap = el('div', '', '');
    wrap.style.cssText = 'position:fixed;inset:0;z-index:85;display:flex;'
      + 'align-items:center;justify-content:center;padding:24px;'
      + 'background:rgba(6,6,10,.9)';
    const card = el('div', 'frame', `
      <div class="pixel" style="color:var(--violet);font-size:10px;letter-spacing:1px">
        THE WORLD MOVES</div>
      <h2 class="pixel" style="color:var(--gold-hi);font-size:16px;margin:10px 0 14px">
        ${esc(event.title || '')}</h2>
      <p class="pixel" id="wui-herald" style="color:var(--gold);font-size:11px;
        line-height:1.9;min-height:24px">${esc(event.herald || '')}</p>
      <p class="small" id="wui-prose" style="opacity:0;transition:opacity .5s;
        line-height:1.8;color:var(--ink)">${esc(event.prose || '')}</p>
      <div id="wui-changes" style="opacity:0;transition:opacity .5s;margin-top:10px">
        ${roads.length ? `<p class="small" style="color:var(--green)">
          ROADS OPEN: ${roads.map(r => esc(r)).join(' · ')}</p>` : ''}
        ${changes.length ? changes.map(c =>
          `<p class="small muted">${esc(c)}</p>`).join('') : ''}
        ${event.region ? `<p class="small muted">in ${esc(
          String(event.region).replace(/_/g, ' '))}</p>` : ''}
      </div>
      <div class="actions" style="display:flex;gap:8px;margin-top:16px">
        <button class="btn primary" id="wui-herald-ok">${this.queue.length
          ? `CONTINUE (${this.queue.length} MORE)` : 'CONTINUE'}</button>
      </div>`);
    card.style.cssText += 'max-width:min(640px,94vw);padding:22px 24px';
    wrap.appendChild(card);
    (document.getElementById('app') || document.body).appendChild(wrap);
    this.herald = wrap;

    // Revealed in beats, so the herald lands before the consequences do. Both
    // timers are registered; dismissing at any point clears them.
    this.heraldLater(() => {
      const prose = $('#wui-prose', card);
      if (prose) prose.style.opacity = '1';
    }, 700);
    this.heraldLater(() => {
      const detail = $('#wui-changes', card);
      if (detail) detail.style.opacity = '1';
    }, 1400);

    const done = () => { this.dismissHerald(); this.drainQueue(); };
    $('#wui-herald-ok', card).onclick = done;
    wrap.addEventListener('click', (e) => { if (e.target === wrap) done(); });
    this.heraldKey = (e) => { if (e.key === 'Escape' || e.key === ' ') { e.preventDefault(); done(); } };
    window.addEventListener('keydown', this.heraldKey);
    this.sfx('unlock');
  }

  heraldLater(fn, ms) {
    const id = setTimeout(() => { this.timers.delete(id); fn(); }, ms);
    this.timers.add(id);
    this.heraldTimers.push(id);
    return id;
  }

  dismissHerald() {
    for (const id of this.heraldTimers) { clearTimeout(id); this.timers.delete(id); }
    this.heraldTimers = [];
    if (this.heraldKey) {
      window.removeEventListener('keydown', this.heraldKey);
      this.heraldKey = null;
    }
    if (this.herald) { this.herald.remove(); this.herald = null; }
  }
}

export function createWorldUI(hooks = {}) {
  return new WorldUI(hooks);
}

export const WORLD_UI_VERSION = '1.0.0';
