/* Watching it come: the apex hunter, on the map.
 *
 * gauntlet/hunters.py owns the hunt. It authors seventeen apexes, decides when
 * one stirs, runs `hunt_step` and says, in its own words, that the `Hunt`
 * dataclass "is the whole of the state web/js/overworld.js mirrors". So this
 * file MIRRORS. It does not decide whether you are being hunted, it does not
 * decide when the chase ends, and it does not get a vote on the eight escape
 * guarantees. It draws what the engine says is true, between the updates the
 * engine sends, and it enforces three rules of its own that are about pixels
 * rather than about rules:
 *
 *   A  the creature goes through the same y-sort as the trees, and may never
 *      cover the player, a marker, or an exit
 *   B  the state is legible from the screen without reading a number
 *   C  the way out is drawn last and brightest, over everything the dread adds
 *
 * -------------------------------------------------------------------------
 * DEAD RECKONING, AND WHY
 *
 * The authority ticks on the server. The client's own move handler is debounced
 * at 900ms, so an authoritative position arrives roughly once a second and a
 * creature that only moved when one landed would twitch across the map at 1 Hz.
 * So the engine's (x, y) is a CORRECTION, not a position: between updates the
 * apex advances along the same route it would have taken, at the speed its
 * state says it moves, and the next update eases it back onto the truth.
 * `syncedAgo` says how stale the picture is and `corrected` says how far the
 * last correction moved it, so a harness can put numbers on both instead of
 * taking "close enough" on trust.
 *
 * If a hunt row arrives with no coordinates at all — which is what the state
 * looks like today, because the server wiring has not happened — the same
 * motion model drives locally from a deterministic spawn. That is a FALLBACK
 * and it is labelled as one in `debug()`: `source: 'engine' | 'local'`.
 *
 * -------------------------------------------------------------------------
 * THE ESCAPE. hunters.py designed it first and states it as arithmetic:
 *
 *     G1  74 px/s < 112 px/s. Always. In every state, at every readiness.
 *         Hold a direction and you gain 38 pixels a second.
 *
 * Everything this file does is downstream of that, and it re-clamps it rather
 * than trusting it: no state in STATE_SPEED may exceed APEX_MAX_SPEED, and a
 * payload that says otherwise is clamped on arrival. Two files independently
 * refusing to let the monster outrun you is not redundancy, it is the only
 * form of guarantee that survives somebody else's tuning pass.
 *
 * The rest of the guarantees are the engine's and this file does not simulate
 * them. What it does add is the one the engine cannot: a creature forty-eight
 * pixels tall, drawn on a screen three hundred wide, MUST NOT BE ALLOWED TO
 * COVER THE DOOR. See `drawTelegraph` and overworld.js's `_drawApexOverlay`.
 *
 * No Math.random in any path here; every angle and every fallback spawn comes
 * out of a hash of the region and the creature.
 */
import * as bosses from './bosses.js';

export const TILE = 16;

/* ------------------------------------------------- copied from hunters.py
 *
 * Copies, and deliberately not a fetch: this table decides how a frame is
 * drawn and a frame cannot wait for a round trip. The engine remains the
 * authority — `adoptPayload` takes hunters.client_payload() and overwrites
 * every one of these at runtime — but the clamp below is applied to whatever
 * arrives, so an engine that one day ships a 200 px/s enrage state gets a
 * 74 px/s enrage state on this client and a line in the harness output. */
export const PLAYER_WALK_SPEED = 112.0;
export const APEX_MAX_SPEED = 74.0;
export const SPEED_MARGIN = PLAYER_WALK_SPEED - APEX_MAX_SPEED;   // 38

export const HUNT_STATES = ['DORMANT', 'STIRRING', 'ROAMING', 'TRACKING',
                            'CLOSING', 'ENGAGED', 'FADING', 'SPENT'];

export const STATE_SPEED = {
  DORMANT: 0, STIRRING: 0, ROAMING: 38, TRACKING: 52,
  CLOSING: 74, ENGAGED: 0, FADING: 22, SPENT: 0,
};

/* hunters.py's own telegraph table, minus the channels this file is not the
 * owner of. `audio` is a sentence about sound design and belongs to audio.js;
 * `line` is prose and belongs to whoever owns the region card. What is here is
 * the two channels that are pixels: how much the frame darkens, and what the
 * map is allowed to show.
 *
 *   none     nothing. You have not been found.
 *   heading  a direction, and no position. It is out there, that way.
 *   stale    where it WAS. The scent is old and the marker says so by lagging.
 *   live     where it is, now.
 */
export const TELEGRAPH = {
  STIRRING: { vignette: 0.00, map: 'none',    countdown: false, rate: 0.0 },
  ROAMING:  { vignette: 0.06, map: 'heading', countdown: false, rate: 0.7 },
  TRACKING: { vignette: 0.12, map: 'stale',   countdown: false, rate: 1.5 },
  CLOSING:  { vignette: 0.22, map: 'live',    countdown: true,  rate: 2.8 },
  ENGAGED:  { vignette: 0.00, map: 'live',    countdown: false, rate: 0.0 },
  FADING:   { vignette: 0.10, map: 'stale',   countdown: false, rate: 0.5 },
};

/* The hard ceiling on the darkening, above the 0.22 the table asks for. It is
 * a separate number from the table on purpose: the table is tuning and this is
 * a promise. At 0.26 over the world you can still read an exit glow, a chest, a
 * marker and the control hints through it — which is the whole of requirement
 * C, and the reason the gold chevron is painted after this and never under it. */
export const VIGNETTE_CAP = 0.26;

/* States in which there is a body on the map at all. DORMANT and SPENT are not
 * "invisible", they are "not there", and the difference matters: nothing is
 * drawn, nothing is sorted, nothing is paid for. */
export const EMBODIED = { ROAMING: 1, TRACKING: 1, CLOSING: 1, ENGAGED: 1, FADING: 1 };

/* Client-side only, and a DRAW rule rather than a mechanic. The engine's own
 * EXIT_SAFE_PX (128) is a SPAWN exclusion — it never appears within eight tiles
 * of a boundary — and applying eight tiles to the pursuit as well would hollow
 * the chase out, because half the screen would be a no-go. This is much
 * smaller and it buys exactly one thing: the apex's forty-eight pixel body
 * never stands on the door glyph, so the way out is never a thing you have to
 * look around a monster to find. Mechanically it changes nothing — the apex has
 * no collision, cannot block a step, and a fight it starts can always be fled.
 */
export const EXIT_KEEP_PX = 2.5 * TILE;

export const FADE_SECONDS = 6.0;        // hunters.py FADE_SECONDS
export const STALE_LAG_SECONDS = 2.2;   // how far behind the 'stale' marker sits
export const CORRECTION_SPEED = 150;    // px/s the drawn body eases onto truth
export const SNAP_PX = 4 * TILE;        // a correction bigger than this is a jump
export const REFLOW_SECONDS = 0.25;     // how often the dead-reckoning route refloods
export const CONTACT_PX = 20;           // hunters.py CONTACT_PX

/* Fallback spawn placement, used only when no engine coordinates ever arrive.
 * The numbers are the engine's, in tiles. */
/* DELIBERATELY TIGHTER THAN THE ENGINE'S OWN BAND, which is 26..40 tiles
 * (hunters.SPAWN_MIN_PX 416, SPAWN_MAX_PX 640). The engine measures a scalar
 * distance and never has to find a tile to put it on; this has to, and two of
 * the seventeen maps are small enough that no open, reachable tile is 26 tiles
 * from a player standing anywhere near the middle. Widening these to match was
 * tried and measured: `_place` degraded to "the furthest tile on the map",
 * which in those two regions is an unreachable pocket, and the creature never
 * arrived at all. A slightly nearer fallback spawn is a worse hunt; a fallback
 * spawn nothing can walk out of is no hunt. See `_place`. */
export const SPAWN_MIN_TILES = 22;
export const SPAWN_MAX_TILES = 34;
export const LOCAL_ARRIVAL_DELAY = 2.0;

export const WAYOUT_LANE = 7;    // px from the rim. The way out is OUTBOARD.
export const THREAT_LANE = 20;   // px from the rim. The threat is inboard of it.
export const MARK_SIZE = 6;

const TAU = Math.PI * 2;

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function gcd(a, b) { while (b) { const t = a % b; a = b; b = t; } return a; }
function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }

/* The colours of elements.py, for the one case where an apex row arrives with
 * no colour of its own. Every apex in hunters.py carries one, so this is a
 * fallback for a half-built payload rather than a table anybody consults. */
export const ELEMENT_COLOUR = {
  FIRE: '#e06a3c', COLD: '#7ec8ff', POISON: '#8fd07a',
  BRUTE: '#bf8f4f', LIGHTNING: '#f2dc6a', VOID: '#6a4f8f',
  NEUTRAL: '#9b96b8',
};

/* hunters.client_payload(), adopted. Every number this file draws with can be
 * replaced by the engine's own at runtime, which is what stops the copies above
 * from silently drifting away from the module that owns them. The speed clamp
 * is applied to whatever arrives; `adoptPayload` returns what it refused so a
 * harness can print it rather than a player discovering it. */
export function adoptPayload(payload) {
  const refused = [];
  if (!payload || typeof payload !== 'object') return { adopted: false, refused };
  if (payload.speed && typeof payload.speed === 'object') {
    for (const k of Object.keys(payload.speed)) {
      const v = Number(payload.speed[k]);
      if (!Number.isFinite(v) || v < 0) continue;
      if (v > APEX_MAX_SPEED) {
        refused.push({ state: k, asked: v, clamped: APEX_MAX_SPEED });
        STATE_SPEED[k] = APEX_MAX_SPEED;
      } else STATE_SPEED[k] = v;
    }
  }
  if (payload.telegraph && typeof payload.telegraph === 'object') {
    for (const k of Object.keys(payload.telegraph)) {
      const row = payload.telegraph[k];
      if (!row || !TELEGRAPH[k]) continue;
      const v = Number(row.vignette);
      if (Number.isFinite(v)) TELEGRAPH[k].vignette = Math.min(VIGNETTE_CAP, Math.max(0, v));
      if (typeof row.map === 'string') TELEGRAPH[k].map = row.map;
      if (typeof row.countdown === 'boolean') TELEGRAPH[k].countdown = row.countdown;
    }
  }
  return { adopted: true, refused };
}

/* ------------------------------------------------------------------- state
 *
 * THE SHAPE THIS CODES AGAINST, taken from gauntlet/hunters.py rather than
 * invented. Nothing in server.py exposes it yet; these are the two dataclasses
 * that module already serialises, and the field names are its own.
 *
 *   state.hunt = Hunt.to_dict()      // hunters.py, "the whole of the state
 *                                    // web/js/overworld.js mirrors"
 *     { region, state, apex, elapsed, dwell, pressure, x, y, distance,
 *       best_distance, beyond, scent, cooldown, spawns, kills, flights }
 *
 *   state.apexes = [Apex.to_dict()]  // hunters.client_payload().apexes
 *     { id, name, region, region_name, depth, element, elements, art,
 *       silhouette, presence, lesson, tell, sprite, sprite_fallback, colour,
 *       exam, metal, required_rung, exam_difficulty, trophy }
 *
 *   state.apex_payload = client_payload()   // optional, adopted if present
 *
 * WHAT IS ASSUMED, precisely, because the wiring does not exist:
 *
 *   1  The hunt row for the CURRENT region reaches the client. Read from
 *      `state.hunt`, `state.apex_hunt`, or the matching entry of `state.hunts`
 *      / `state.apex_hunts` — three plausible spellings accepted rather than
 *      one guessed at, and all of them optional.
 *   2  `x` and `y` are PIXELS in the same map space as player.px/py, which is
 *      what SPAWN_MIN_PX = 22 * TILE and CONTACT_PX = 20 imply. A row whose
 *      coordinates are plainly tiles instead — both inside the map's tile
 *      bounds and too small to be pixels — is scaled up, and `coordUnits` in
 *      debug() says which reading was taken.
 *   3  The apex table may or may not be present. Without it the creature still
 *      draws, in neutral grey, under the name the hunt row carries. A hunt with
 *      no art is still a hunt; a hunt with no state is not a hunt.
 *
 * Everything degrades to "nothing is hunting", silently: a missing field, a
 * malformed row, a row for another region, a stateSource that throws mid
 * rewrite. In that case the overworld renders exactly as it does today.
 */
function pickHunt(state, regionId) {
  if (!state || typeof state !== 'object') return null;
  const one = state.hunt || state.apex_hunt || state.apexHunt;
  if (one && typeof one === 'object' && !Array.isArray(one)) return one;
  const many = state.hunts || state.apex_hunts || (Array.isArray(one) ? one : null);
  if (Array.isArray(many)) {
    for (let i = 0; i < many.length; i++) {
      const r = many[i];
      if (r && typeof r === 'object' && String(r.region || '') === String(regionId)) return r;
    }
  }
  return null;
}

function pickApex(state, huntRow, regionId) {
  if (!state || typeof state !== 'object') return null;
  const direct = state.apex || state.apex_row;
  if (direct && typeof direct === 'object' && !Array.isArray(direct)) return direct;
  const table = state.apexes
    || (state.apex_payload && state.apex_payload.apexes)
    || (Array.isArray(direct) ? direct : null);
  if (!Array.isArray(table)) return null;
  const wantId = huntRow && huntRow.apex ? String(huntRow.apex) : '';
  for (let i = 0; i < table.length; i++) {
    const r = table[i];
    if (!r || typeof r !== 'object') continue;
    if (wantId && String(r.id) === wantId) return r;
  }
  for (let i = 0; i < table.length; i++) {
    const r = table[i];
    if (r && typeof r === 'object' && String(r.region || '') === String(regionId)) return r;
  }
  return null;
}

/* Which of bosses.js's archetypes this creature has a face as. The authored
 * key first — hunters.py ships a `sprite` nobody has drawn yet, and the day
 * somebody does, this line starts using it with no edit here — then the
 * declared fallback, then the id. resolveBoss never throws and never returns
 * nothing, so the last resort is its business rather than ours. */
export function artKeyFor(apexRow) {
  if (!apexRow) return 'titan';
  const tried = [apexRow.sprite, apexRow.sprite_fallback, apexRow.spriteFallback,
                 apexRow.id];
  for (const k of tried) {
    if (!k) continue;
    try {
      const r = bosses.resolveBoss(String(k));
      // resolveBoss answers SOMETHING for anything; the authored key counts as
      // real only when it resolves to itself or to a declared archetype.
      if (r && (String(k) === r || k === apexRow.sprite_fallback
                || k === apexRow.spriteFallback)) return r;
    } catch (e) { /* mid-rewrite export */ }
  }
  try { return bosses.resolveBoss(String(apexRow.sprite_fallback || apexRow.id || '')); }
  catch (e) { return 'titan'; }
}

/* Normalised, or null. Refusal is the default. */
export function resolveHunt(state, regionId) {
  const row = pickHunt(state, regionId);
  if (!row || typeof row !== 'object') return null;
  const rr = row.region || row.region_id || row.regionId;
  if (rr && regionId && String(rr) !== String(regionId)) return null;

  let st = String(row.state || row.hunt_state || 'DORMANT').toUpperCase();
  if (HUNT_STATES.indexOf(st) < 0) st = 'DORMANT';

  const apexRow = pickApex(state, row, regionId);
  const element = String((apexRow && (apexRow.element || apexRow.affinity)) || 'NEUTRAL')
    .toUpperCase();

  let x = Number(row.x), y = Number(row.y);
  let units = 'none';
  if (Number.isFinite(x) && Number.isFinite(y)) {
    units = 'px';
    // Assumption 2, stated in the header and detectable here: a row whose
    // coordinates are small enough to be tile indices is read as tiles. The
    // engine's own numbers are pixels — SPAWN_MIN_PX is 416 — so this only
    // fires for a payload that has already disagreed with its own module.
    if (Math.abs(x) < 64 && Math.abs(y) < 48 && (x % 1 === 0) && (y % 1 === 0)) {
      x *= TILE; y *= TILE; units = 'tiles->px';
    }
  } else { x = null; y = null; }

  const dist = Number(row.distance);

  return {
    state: st,
    apexId: String(row.apex || (apexRow && apexRow.id) || ''),
    name: String((apexRow && apexRow.name) || row.name || 'Something').toUpperCase(),
    colour: (apexRow && apexRow.colour) || ELEMENT_COLOUR[element] || ELEMENT_COLOUR.NEUTRAL,
    element,
    artKey: artKeyFor(apexRow),
    authoredSprite: (apexRow && apexRow.sprite) || '',
    lesson: (apexRow && apexRow.lesson) || '',
    tell: (apexRow && apexRow.tell) || '',
    regionId: String(regionId || ''),
    x, y, coordUnits: units,
    distance: Number.isFinite(dist) ? dist : null,
    scent: Number.isFinite(Number(row.scent)) ? clamp01(Number(row.scent)) : null,
    elapsed: Number.isFinite(Number(row.elapsed)) ? Number(row.elapsed) : 0,
    spawns: Number(row.spawns) || 0,
    hasArt: !!apexRow,
  };
}

/* The identity of a hunt. A state change or a moved creature must NOT rebuild
 * it — that is the whole point of mirroring — so only the things that make it a
 * different animal in a different place are in here. */
export function stampOf(v) {
  return v ? `${v.apexId}|${v.artKey}|${v.colour}|${v.regionId}` : '';
}

/* ---------------------------------------------------------------- pursuit
 *
 * `world` is injected rather than imported, so this is drivable without an
 * Overworld: { regionId, mapW, mapH, player:{px,py}, solid(tx,ty), markers }.
 */
export class Pursuit {
  constructor(view, world) {
    this.view = view;
    this.world = world;
    this.state = 'DORMANT';
    this.px = 0; this.py = 0;          // where it is DRAWN
    this.tx = 0; this.ty = 0;          // where the motion model says it is
    this.placed = false;
    this.source = 'local';
    this.syncedAgo = 0;
    this.corrected = 0;                // px the last correction moved it
    this.corrections = 0;
    this.snaps = 0;
    this.alpha = 0;
    this.facing = 'down';
    this.tiles = Infinity;
    this.staleX = 0; this.staleY = 0; this._staleAt = 0;
    this._authX = null; this._authY = null;
    this.localAge = 0;
    this._dist = null; this._queue = null;
    this._flowX = -1; this._flowY = -1; this._reflow = 0;
    this._aim = null;
    this._keepOut = null;
    this._bind();
  }

  /* Exit tiles get a small keep-out for the DRAW rule in EXIT_KEEP_PX. Resolved
   * to integer tile keys once, because the marker list never changes inside a
   * region and a per-frame scan of it would be the same answer at a cost. */
  _bind() {
    const w = this.world;
    const keep = new Set();
    const r = Math.ceil(EXIT_KEEP_PX / TILE);
    const ms = w.markers || [];
    for (let i = 0; i < ms.length; i++) {
      const m = ms[i];
      if (m.kind !== 'exit') continue;
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if ((dx * dx + dy * dy) * TILE * TILE > EXIT_KEEP_PX * EXIT_KEEP_PX) continue;
          const tx = m.x + dx, ty = m.y + dy;
          if (tx < 0 || ty < 0 || tx >= w.mapW || ty >= w.mapH) continue;
          keep.add(ty * w.mapW + tx);
        }
      }
    }
    this._keepOut = keep;
  }

  get embodied() { return !!EMBODIED[this.state] && this.placed; }
  get speed() { return Math.min(APEX_MAX_SPEED, STATE_SPEED[this.state] || 0); }

  /* A fresh view from the state. This is the authority arriving. */
  sync(view) {
    const was = this.state;
    this.view = view;
    this.state = view.state;
    if (!EMBODIED[this.state]) {
      if (this.state === 'DORMANT' || this.state === 'SPENT') this.placed = false;
      return was !== this.state;
    }
    if (view.x !== null && view.y !== null) {
      this.source = 'engine';
      if (!this.placed) {
        this.px = view.x; this.py = view.y;
        this.tx = view.x; this.ty = view.y;
        this.placed = true;
        this.syncedAgo = 0;
        this.staleX = view.x; this.staleY = view.y;
        this._authX = view.x; this._authY = view.y;
      } else if (view.x !== this._authX || view.y !== this._authY) {
        /* Only a CHANGED position is a correction.
         *
         * This is not an optimisation, it is the difference between a creature
         * and a decal. The client polls; the server row is the same object
         * until the next tick lands, so `sync` is handed an identical (x, y)
         * for fifty consecutive frames. Applying it every time pins the model
         * to the last authoritative pixel, dead reckoning never advances, and
         * the apex stands perfectly still for a second and then teleports.
         * Measured before this line existed: it walked zero pixels in ten
         * seconds at a state whose speed is 52 px/s, and the stale marker never
         * lagged because there was nothing for it to lag behind. */
        this._authX = view.x; this._authY = view.y;
        this.syncedAgo = 0;
        const d = Math.hypot(view.x - this.tx, view.y - this.ty);
        this.corrected = d; this.corrections++;
        this.tx = view.x; this.ty = view.y;
        if (d > SNAP_PX) { this.px = view.x; this.py = view.y; this.snaps++; }
      }
    } else if (!this.placed) {
      this.source = 'local';
      // the fallback: a deterministic tile inside the engine's own spawn band
      if (this.localAge >= LOCAL_ARRIVAL_DELAY && this._place()) {
        this.placed = true;
        this.staleX = this.px; this.staleY = this.py;
      }
    }
    return was !== this.state;
  }

  /* One frame. Dead-reckons the motion model, eases the drawn body onto it,
   * and ages the stale marker. Returns 'contact' on the frame it arrives,
   * which the caller may ignore — the ENGINE decides whether a fight starts;
   * this is the client noticing, so a sound can play on the right frame. */
  update(dt, time) {
    this.localAge += dt;
    this.syncedAgo += dt;

    if (!EMBODIED[this.state]) {
      this.alpha = Math.max(0, this.alpha - dt / 0.5);
      this.tiles = Infinity;
      return '';
    }
    if (!this.placed) {
      if (this.source === 'local' && this.localAge >= LOCAL_ARRIVAL_DELAY
          && this._place()) {
        this.placed = true;
        this.staleX = this.px; this.staleY = this.py;
      } else return '';
    }

    const target = this.state === 'FADING' ? 0.55 : 1;
    this.alpha = this.alpha < target
      ? Math.min(target, this.alpha + dt / 0.6)
      : Math.max(target, this.alpha - dt / FADE_SECONDS);

    // 1. advance the model
    this._reckon(dt);
    // 2. ease the drawn body onto it
    const dx = this.tx - this.px, dy = this.ty - this.py;
    const d = Math.hypot(dx, dy);
    if (d > 0.05) {
      const step = Math.min(d, Math.max(CORRECTION_SPEED, this.speed * 1.4) * dt);
      this.px += (dx / d) * step; this.py += (dy / d) * step;
      if (Math.abs(dx) > Math.abs(dy)) this.facing = dx < 0 ? 'left' : 'right';
      else if (dy !== 0) this.facing = dy < 0 ? 'up' : 'down';
    }

    // 3. the stale marker lags on purpose: TRACKING says "it knows where you
    //    WERE", and a marker that told the truth would be saying the opposite
    if (time - this._staleAt >= STALE_LAG_SECONDS) {
      this._staleAt = time; this.staleX = this.px; this.staleY = this.py;
    }

    const p = this.world.player;
    const gap = Math.hypot(this.px - p.px, this.py - p.py);
    this.tiles = gap / TILE;
    return gap <= CONTACT_PX ? 'contact' : '';
  }

  /* --------------------------------------------------------- the route
   *
   * A breadth-first flood from the player; the model walks downhill in it.
   *
   * The two cheaper things were both tried before this and both are why this
   * is here. A walker that steers straight at the player wedges on the first
   * concave rock and vibrates there forever — two of seventeen regions. A
   * walker with a committed wall-follow wedges less often and FURTHER AWAY,
   * which is worse, because eleven tiles out nobody ever sees why it stopped
   * coming — three of seventeen. The flood reaches the player in seventeen of
   * seventeen, which is the only score worth having for a creature whose entire
   * premise is that it arrives.
   *
   * It costs one pass over 1,632 cells, four times a second, into two
   * Int32Arrays allocated once when the hunt begins, and only while something
   * is actually hunting. That is roughly 26,000 integer operations a second
   * against a draw loop rasterising tens of thousands of pixels a frame. It is
   * not the expensive thing on this screen.
   *
   * The flood spreads over everything that is not rock, INCLUDING the exit
   * keep-out, so the route to a player standing on the door is still a real
   * route; the apex walks it and stops at the edge of the keep-out because
   * `_step` will not enter. It ends up looking at you across two and a half
   * tiles it will not cross, which is the picture the rule is for. Excluding
   * the keep-out from the flood instead would have deleted the route and the
   * creature would wander, which reads as a bug rather than as a rule.
   */
  _flow() {
    const w = this.world, p = w.player;
    const W = w.mapW, H = w.mapH, cells = W * H;
    if (!this._dist) { this._dist = new Int32Array(cells); this._queue = new Int32Array(cells); }
    const dist = this._dist, q = this._queue;
    dist.fill(-1);
    const sx = Math.floor((p.px + TILE / 2) / TILE);
    const sy = Math.floor((p.py + TILE / 2) / TILE);
    if (sx < 0 || sy < 0 || sx >= W || sy >= H) return false;
    let head = 0, tail = 0;
    const s0 = sy * W + sx;
    dist[s0] = 0; q[tail++] = s0;
    while (head < tail) {
      const c = q[head++];
      const d = dist[c] + 1;
      const cx = c % W, cy = (c / W) | 0;
      // fixed neighbour order, so the flood and therefore the route is the same
      // on two runs of the same walk
      if (cy > 0)     { const n = c - W; if (dist[n] < 0 && !w.solid(cx, cy - 1)) { dist[n] = d; q[tail++] = n; } }
      if (cy < H - 1) { const n = c + W; if (dist[n] < 0 && !w.solid(cx, cy + 1)) { dist[n] = d; q[tail++] = n; } }
      if (cx > 0)     { const n = c - 1; if (dist[n] < 0 && !w.solid(cx - 1, cy)) { dist[n] = d; q[tail++] = n; } }
      if (cx < W - 1) { const n = c + 1; if (dist[n] < 0 && !w.solid(cx + 1, cy)) { dist[n] = d; q[tail++] = n; } }
    }
    this._flowX = sx; this._flowY = sy;
    return true;
  }

  _open(tx, ty) {
    const w = this.world;
    if (tx < 1 || ty < 1 || tx >= w.mapW - 1 || ty >= w.mapH - 1) return false;
    if (w.solid(tx, ty)) return false;
    return !this._keepOut.has(ty * w.mapW + tx);
  }

  _step(mx, my) {
    const nx = this.tx + mx, ny = this.ty + my;
    const tx = Math.floor((nx + TILE / 2) / TILE), ty = Math.floor((ny + TILE / 2) / TILE);
    if (!this._open(tx, ty)) return false;
    this.tx = nx; this.ty = ny;
    return true;
  }

  _probe(vx, vy, px) {
    const nx = this.tx + vx * px, ny = this.ty + vy * px;
    return this._open(Math.floor((nx + TILE / 2) / TILE), Math.floor((ny + TILE / 2) / TILE));
  }

  _ahead(vx, vy, px) {
    const steps = Math.max(1, Math.round(px / (TILE / 2)));
    for (let i = 1; i <= steps; i++) if (!this._probe(vx, vy, (px * i) / steps)) return false;
    return true;
  }

  _downhill(out) {
    const w = this.world, W = w.mapW, H = w.mapH, dist = this._dist;
    if (!dist) return false;
    const cx = Math.floor((this.tx + TILE / 2) / TILE);
    const cy = Math.floor((this.ty + TILE / 2) / TILE);
    if (cx < 0 || cy < 0 || cx >= W || cy >= H) return false;
    const here = dist[cy * W + cx];
    if (here < 0) return false;
    let best = here, bx = -1, by = -1;
    for (let k = 0; k < 4; k++) {
      const tx = cx + (k === 2 ? -1 : k === 3 ? 1 : 0);
      const ty = cy + (k === 0 ? -1 : k === 1 ? 1 : 0);
      if (tx < 0 || ty < 0 || tx >= W || ty >= H) continue;
      const d = dist[ty * W + tx];
      if (d < 0 || d >= best) continue;
      if (!this._open(tx, ty)) continue;
      best = d; bx = tx; by = ty;
    }
    if (bx < 0) return false;
    out.x = bx; out.y = by;
    return true;
  }

  /* ROAMING has not found you, so it does not walk at you: it walks its
   * circuit. Modelled as a slow drift toward a fixed point hashed off the
   * region — no pursuit, no roll, and visibly not coming. */
  _reckon(dt) {
    const sp = this.speed;
    if (sp <= 0) return;
    const w = this.world, p = w.player;
    const step = sp * dt;

    let gx = p.px, gy = p.py;
    if (this.state === 'ROAMING' || this.state === 'FADING') {
      const h = hash(this.view.regionId + '|' + this.view.apexId);
      gx = (4 + (h % (w.mapW - 8))) * TILE;
      gy = (3 + ((h >>> 9) % (w.mapH - 6))) * TILE;
      if (this.state === 'FADING') { gx = w.mapW * TILE - gx; gy = w.mapH * TILE - gy; }
    }

    const dx = gx - this.tx, dy = gy - this.ty;
    const dist = Math.hypot(dx, dy);
    if (dist < 0.001) return;
    const ux = dx / dist, uy = dy / dist;

    this._reflow -= dt;
    const psx = Math.floor((p.px + TILE / 2) / TILE);
    const psy = Math.floor((p.py + TILE / 2) / TILE);
    if (this._reflow <= 0 || psx !== this._flowX || psy !== this._flowY) {
      this._reflow = REFLOW_SECONDS;
      this._flow();
    }

    if (dist < TILE * 2 || this._ahead(ux, uy, Math.min(dist, TILE * 1.5))) {
      if (this._step(ux * step, uy * step)) return;
    }
    const aim = this._aim || (this._aim = { x: 0, y: 0 });
    if (this._downhill(aim)) {
      const ax = aim.x * TILE - this.tx, ay = aim.y * TILE - this.ty;
      const n = Math.hypot(ax, ay) || 1;
      if (this._step((ax / n) * step, (ay / n) * step)) return;
    }
    const firstX = Math.abs(ux) >= Math.abs(uy);
    if (firstX && this._step(ux * step, 0)) return;
    if (!firstX && this._step(0, uy * step)) return;
    if (firstX && this._step(0, uy * step)) return;
    if (!firstX) this._step(ux * step, 0);
  }

  /* Fallback placement only. A fixed-stride walk over the map from a hashed
   * start, taking the first tile inside the engine's own spawn band that is
   * open and not an interactable. Deterministic, and no roll near a draw path.
   *
   * Both shifts are UNSIGNED and the modulo is folded positive, and both are
   * scars: `hash` returns a uint32, `seed >> 8` is a SIGNED shift, and any hash
   * with the top bit set produced a negative stride that walked off the bottom
   * of the map into tile indices `_open` dutifully rejected. The scan failed,
   * nothing spawned, and in five of seventeen regions the apex never appeared
   * at all — silently, because a monster that has not spawned looks exactly
   * like a monster that has not spawned YET. */
  _place() {
    const w = this.world, p = w.player;
    const cells = w.mapW * w.mapH;
    const lo = SPAWN_MIN_TILES * TILE, hi = SPAWN_MAX_TILES * TILE;
    const seed = hash(`${this.view.regionId}|${this.view.apexId}|${this.view.spawns}`);
    const start = seed % cells;
    let stride = 1 + ((seed >>> 8) % cells);
    while (gcd(stride, cells) !== 1) stride++;
    let inBand = -1;      // the first tile inside the engine's own spawn band
    let furthest = -1, furthestD = -1;   // and the best this map can actually do
    for (let i = 0; i < cells; i++) {
      const c = ((start + i * stride) % cells + cells) % cells;
      const tx = c % w.mapW, ty = (c / w.mapW) | 0;
      if (!this._open(tx, ty)) continue;
      if (this._onMarker(tx, ty)) continue;
      const d = Math.hypot(tx * TILE - p.px, ty * TILE - p.py);
      if (d >= lo && d <= hi) { inBand = c; break; }
      // A 48x34 map is 34 tiles wide and a player standing in the middle of it
      // cannot be 22 tiles from anywhere. So the band is a preference and the
      // fallback is "as far away as this place allows", because degrading to
      // a closer spawn is a worse hunt and degrading to NO spawn is no hunt.
      if (d > furthestD) { furthestD = d; furthest = c; }
    }
    const cell = inBand >= 0 ? inBand : furthest;
    if (cell < 0) return false;
    this.tx = (cell % w.mapW) * TILE;
    this.ty = ((cell / w.mapW) | 0) * TILE;
    this.px = this.tx; this.py = this.ty;
    return true;
  }

  _onMarker(tx, ty) {
    const ms = this.world.markers || [];
    for (let i = 0; i < ms.length; i++) {
      const m = ms[i];
      if (m.kind === 'building') {
        if (tx >= m.x && tx <= m.x + 1 && ty >= m.y && ty <= m.y + 1) return true;
      } else if (m.x === tx && m.y === ty) return true;
    }
    return false;
  }

  /* Where it is relative to you, as a unit vector, written into a caller-owned
   * scratch so the draw path allocates nothing. `useStale` asks for the scent
   * rather than the creature, which is what the TRACKING telegraph shows. */
  bearing(out, useStale) {
    const p = this.world.player;
    const x = useStale ? this.staleX : this.px;
    const y = useStale ? this.staleY : this.py;
    const dx = x - p.px, dy = y - p.py;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    out.x = dx / d; out.y = dy / d; out.dist = d;
    return out;
  }

  debug() {
    return {
      state: this.state, source: this.source, coordUnits: this.view.coordUnits,
      apexId: this.view.apexId, artKey: this.view.artKey,
      authoredSpriteKey: this.view.authoredSprite,
      element: this.view.element, colour: this.view.colour,
      speed: this.speed, speedCap: APEX_MAX_SPEED,
      px: +this.px.toFixed(2), py: +this.py.toFixed(2),
      tx: +this.tx.toFixed(2), ty: +this.ty.toFixed(2),
      placed: this.placed, embodied: this.embodied,
      alpha: +this.alpha.toFixed(3), facing: this.facing,
      tiles: Number.isFinite(this.tiles) ? +this.tiles.toFixed(2) : null,
      syncedAgo: +this.syncedAgo.toFixed(2),
      corrections: this.corrections,
      lastCorrectionPx: +this.corrected.toFixed(2),
      snaps: this.snaps,
    };
  }
}

/* ------------------------------------------------------------------- art
 *
 * bosses.js, at map scale. hunters.py gives every apex a `sprite` nobody has
 * drawn yet and a `sprite_fallback` that is a real archetype, which is the only
 * reason a gameplay pass can ship a monster before an art pass has drawn it.
 * artKeyFor() takes the authored key the moment it starts resolving.
 *
 * drawBoss at scale 1 returns the 48x48 MAP FORM, with its own shadow, its own
 * bob and its own ground relationship — the same call and the same size the
 * overworld already uses for a region's boss marker, which is the correct
 * reading: an apex is a boss that came to find you.
 */
export const APEX_SIZE = 48;

const AURA_MOTES = 8;

export function drawApexBody(ctx, h, time, reducedMotion) {
  const a = h.alpha;
  if (a <= 0.004 || !h.embodied) return;
  const t = reducedMotion ? 0 : time;
  const cx = h.px + TILE / 2;
  const cy = h.py + TILE;
  const prev = ctx.globalAlpha;

  /* The aura, under the body: eight motes on a slow orbit in the apex's own
   * colour, breathing on the same clock as the screen-edge wash so the creature
   * and the frame pulse together. Squares rather than circles, because
   * everything else on this screen is a square, and trig on a passed-in clock
   * rather than a roll, because this is a draw path. */
  const breathe = 0.5 + Math.sin(t * 1.6) * 0.5;
  const rx = 19 + breathe * 3, ry = 8 + breathe * 2;
  ctx.fillStyle = h.view.colour;
  for (let i = 0; i < AURA_MOTES; i++) {
    const ang = (i / AURA_MOTES) * TAU + t * 0.55;
    const s = Math.sin(ang);
    ctx.globalAlpha = prev * a * (0.18 + 0.26 * (0.5 + s * 0.5));
    ctx.fillRect(Math.round(cx + Math.cos(ang) * rx) - 1,
                 Math.round(cy - 16 + s * ry) - 1, 2, 2);
  }

  ctx.globalAlpha = prev * a;
  try {
    bosses.drawBoss(ctx, h.view.artKey, cx, cy, {
      time: t * 1000, scale: 1, colour: h.view.colour,
      element: h.view.element, reducedMotion: !!reducedMotion,
    });
  } catch (e) { /* an archetype mid-rewrite: no body, and no dead screen */ }
  ctx.globalAlpha = prev;
}

/* --------------------------------------------------------- the telegraph
 * Screen space, after the world transform is gone: these are the pixels of the
 * frame the player is looking at.
 */

/* A solid pixel triangle. A path would be one call instead of six and also the
 * only antialiased thing on a screen of hard pixels. */
function chevron(ctx, x, y, dir, size) {
  for (let i = 0; i < size; i++) {
    const half = size - i;
    if (dir === 'right') ctx.fillRect(x + i, y - half, 1, half * 2 + 1);
    else if (dir === 'left') ctx.fillRect(x - i, y - half, 1, half * 2 + 1);
    else if (dir === 'down') ctx.fillRect(x - half, y + i, half * 2 + 1, 1);
    else ctx.fillRect(x - half, y - i, half * 2 + 1, 1);
  }
}

/* A mark on the screen edge in the direction of something, in a numbered lane.
 * Writes where it landed into a caller-owned scratch — this runs three times a
 * frame for the length of a hunt, and a harness that wants to prove the gold
 * chevron survived everything painted over it needs to know which pixel. */
export function drawEdgeMark(ctx, viewW, viewH, dirX, dirY, colour, alpha, lane, size, out) {
  const cx = viewW / 2, cy = viewH / 2;
  const halfW = Math.max(1, cx - lane - size), halfH = Math.max(1, cy - lane - size);
  const tx = dirX !== 0 ? halfW / Math.abs(dirX) : Infinity;
  const ty = dirY !== 0 ? halfH / Math.abs(dirY) : Infinity;
  const t = Math.min(tx, ty);
  const ex = cx + dirX * t, ey = cy + dirY * t;
  const edge = tx <= ty ? (dirX < 0 ? 'left' : 'right') : (dirY < 0 ? 'up' : 'down');
  const prev = ctx.globalAlpha;
  ctx.globalAlpha = prev * alpha;
  ctx.fillStyle = colour;
  chevron(ctx, Math.round(ex), Math.round(ey), edge, size);
  ctx.globalAlpha = prev;
  if (out) { out.x = Math.round(ex); out.y = Math.round(ey); out.edge = edge; }
  return edge;
}

/* The frame darkens on the side it is coming from, in its colour, and breathes
 * faster the closer it gets. Non-overlapping strips, so the alpha the player
 * sees is exactly the alpha computed here: a stack of overlapping translucent
 * rectangles would compound into something far darker than the cap, and the cap
 * is the promise that the way out stays readable.
 *
 * Returns the peak alpha actually painted, so a harness can hold this file to
 * VIGNETTE_CAP rather than take the comment's word for it. */
export function drawTelegraph(ctx, h, viewW, viewH, time, reducedMotion) {
  const cfg = TELEGRAPH[h.state];
  if (!cfg || cfg.vignette <= 0 || h.alpha <= 0.004) return 0;
  const bear = drawTelegraph._b || (drawTelegraph._b = { x: 0, y: 0, dist: 0 });
  h.bearing(bear, cfg.map === 'stale');
  const pulse = reducedMotion ? 0.5 : (0.5 + Math.sin(time * cfg.rate * TAU * 0.5) * 0.5);
  const peak = Math.min(VIGNETTE_CAP, cfg.vignette * (0.70 + 0.30 * pulse) * h.alpha);
  const horiz = Math.abs(bear.x) >= Math.abs(bear.y);
  const reach = 0.18 + 0.22 * Math.min(1, cfg.vignette / 0.22);
  const bands = 7;
  const span = Math.round((horiz ? viewW : viewH) * reach);
  const step = Math.max(1, Math.round(span / bands));
  const prev = ctx.globalAlpha;
  ctx.fillStyle = h.view.colour;
  for (let b = 0; b < bands; b++) {
    const k = 1 - b / bands;
    ctx.globalAlpha = peak * k * k;
    const off = b * step;
    if (horiz) ctx.fillRect(bear.x < 0 ? off : viewW - off - step, 0, step, viewH);
    else ctx.fillRect(0, bear.y < 0 ? off : viewH - off - step, viewW, step);
  }
  ctx.globalAlpha = prev;
  return peak;
}

/* The mark over the companion's head when it has noticed. Two pixels and a
 * bob: the least that reads as an animal going rigid. */
export function drawCompanionAlert(ctx, x, y, colour, time, reducedMotion) {
  const bob = reducedMotion ? 0 : (Math.sin(time * 7) > 0 ? 0 : 1);
  const prev = ctx.globalAlpha;
  ctx.globalAlpha = prev * 0.9;
  ctx.fillStyle = colour;
  ctx.fillRect(Math.round(x), Math.round(y - 3 + bob), 2, 5);
  ctx.fillRect(Math.round(x), Math.round(y + 3 + bob), 2, 2);
  ctx.globalAlpha = prev;
}
