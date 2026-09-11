/* Python Coding Gauntlet Legend — the battle stage.
 *
 * fx.js owns the fight: the hit, the number, the spell, the close. This module
 * owns the room the fight happens in. It draws everything behind the combatants
 * and everything in front of them, and it owns the camera that moves both.
 *
 * Nothing here is traced, sampled or derived from any existing game, film or
 * franchise. Every silhouette is generated from a seeded height field or a
 * stepped rectangle run, the way the rest of this codebase generates art.
 *
 * Four rules carry the file:
 *
 *   1. NOTHING IS ALLOCATED IN THE DRAW LOOP. Every layer, overlay, glow, fog
 *      band, sigil and occluder is rasterised once in createScene(). A frame is
 *      drawImage, fillRect and globalAlpha, and nothing else. Particles are
 *      analytic — position is a pure function of time — so there is no update
 *      pass and no per-frame object churn either.
 *   2. PARALLAX LAYERS TILE. Painters write through fillWrap(), which wraps at
 *      the layer width, so a layer canvas twice the stage wide scrolls forever
 *      without a seam. That is why the backdrop can move slowly and still never
 *      repeat visibly on screen.
 *   3. THERE IS EXACTLY ONE LIGHT. Its position comes from the horizon, its
 *      colour from the region, and EVERYTHING agrees with it: the beam hanging
 *      in the air, the dust inside the beam, the pool on the deck, the lit face
 *      of every parallax layer, the rim on BOTH combatants — same hue, same
 *      side — and the cast shadows falling the other way. This is the single
 *      highest-leverage thing in the file. A stage where two figures are rimmed
 *      from opposite sides reads as a collage no matter how good the sprites
 *      are; a stage that agrees with itself about where the light is reads as
 *      expensive even when nothing in it is. scene.light is published and
 *      drawRimLight / drawFigureShadow default to it, so a caller has to go out
 *      of its way to break the agreement.
 *   4. FOUR DEPTHS, NOT THREE. Far, mid and near parallax behind the fight; the
 *      occluders framing it at the edges; and the apron — a strip of ground
 *      between the camera and the platform, drawn in FRONT of the combatants
 *      and moving faster than anything else. Depth is what the eye reads before
 *      it reads any single object.
 *   5. THE CAMERA IS OVER-SCANNED, AND IT HAS OPINIONS. baseZoom is 1.03 and
 *      full-frame art is built PAD pixels oversize, so drift, lean, shake and
 *      push-in can never expose an edge. It closes down during a fight, opens
 *      out during a lull, kicks and springs back on an impact, and clamps the
 *      sum of everything to seven pixels. Motion sickness is a failure.
 *
 * Wiring, in one line: the caller applies the camera, draws the stage, draws the
 * combatants, then draws the foreground. See the note at the foot of the file.
 */
import { shade, mix, rng, hash } from './sprites.js';
import { PALETTES } from './pixel.js';

/* ---------------- geometry ----------------
 * Identical to fx.STAGE. Duplicated rather than imported because fx.js is the
 * module that should import this one, and a cycle helps nobody. Pass your own
 * through createScene({stage}) if fx.STAGE ever moves. */
export const SCENE_STAGE = Object.freeze({
  w: 192,
  h: 128,
  ground: 100,   // horizon: where feet land
  heroX: 46,
  enemyX: 136,
});

/* Over-scan margin. Full-frame art is built this much larger on every side so
 * camera motion never reveals the edge of a canvas. */
const PAD = 16;

/* ---------------- the palette the brief asked for ----------------
 * Near-black grounds, gunmetal, blood and bone, electric violet and cyan, hot
 * orange. Region palettes are graded into this, never used raw: pixel.PALETTES
 * is built for a sunlit overworld and reads as a toy at battle scale. */
const METAL = Object.freeze({
  black:  '#06060a',
  ink:    '#0b0b12',
  gun:    '#1d1f27',
  steel:  '#3c414e',
  chrome: '#8e97a8',
  bone:   '#d6d0bd',
  blood:  '#a41724',
  gore:   '#5d0f18',
  rust:   '#6b2a18',
  fire:   '#ff7a1a',
  ember:  '#ffb347',
  violet: '#7b3cc4',
  cyan:   '#38cfe8',
  bile:   '#6fae3a',
});

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const lerp = (a, b, k) => a + (b - a) * k;
const easeOut = k => 1 - (1 - k) * (1 - k);
const easeInOut = k => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);

/* Deterministic value noise over a float. Used for flicker and shake, where a
 * seeded rng closure per frame would be an allocation for no reason. */
function noise(x) {
  const s = Math.sin(x * 12.9898) * 43758.5453;
  return s - Math.floor(s);
}

function rgba(hex, a) {
  const n = parseInt(String(hex).replace('#', '').slice(0, 6), 16) || 0;
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/* Grade a palette colour toward gunmetal and drop it. `k` is how much of the
 * region's own hue survives: 0.35 keeps a swamp green, 0.8 turns it to iron. */
function grade(hex, k = 0.6, drop = -26) {
  return shade(mix(hex, METAL.gun, k), drop);
}

/* ---------------- canvas allocation ----------------
 * Every surface in this module goes through here, and every call is counted, so
 * the harness can assert that the number does not move once a scene is built. */
let _allocated = 0;

function surface(w, h) {
  const cw = Math.max(1, Math.round(w));
  const ch = Math.max(1, Math.round(h));
  const canvas = document.createElement('canvas');
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  _allocated++;
  return { canvas, ctx, w: cw, h: ch };
}

/* Canvases allocated since load. createScene moves this; drawScene must not. */
export function sceneStats() { return { canvases: _allocated }; }
export function resetSceneStats() { _allocated = 0; }

/* ---------------- wrapped primitives ----------------
 * A layer is painted into a canvas `W` wide and scrolled modulo `W`. Anything
 * that runs off the right edge has to reappear on the left or the tiling shows
 * a seam every W pixels, which is the one artefact that gives away a generated
 * backdrop instantly. */
function fillWrap(ctx, W, x, y, w, h, colour) {
  if (w <= 0 || h <= 0) return;
  ctx.fillStyle = colour;
  let sx = ((Math.round(x) % W) + W) % W;
  ctx.fillRect(sx, Math.round(y), w, h);
  if (sx + w > W) ctx.fillRect(sx - W, Math.round(y), w, h);
}

function clearWrap(ctx, W, x, y, w, h) {
  if (w <= 0 || h <= 0) return;
  let sx = ((Math.round(x) % W) + W) % W;
  ctx.clearRect(sx, Math.round(y), w, h);
  if (sx + w > W) ctx.clearRect(sx - W, Math.round(y), w, h);
}

/* A 1px line as a run of rects. Bolts, chains and braces are all this. */
function segment(ctx, x0, y0, x1, y1, thick, colour) {
  const dx = x1 - x0, dy = y1 - y0;
  const steps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy))));
  ctx.fillStyle = colour;
  for (let i = 0; i <= steps; i++) {
    const k = i / steps;
    ctx.fillRect(Math.round(x0 + dx * k), Math.round(y0 + dy * k), thick, thick);
  }
}

/* Hard-edged filled ellipse, rasterised by hand. ctx.ellipse would do it, but
 * an anti-aliased edge on a 192x128 stage is a grey fringe two screen pixels
 * wide once it is scaled up, and it reads as blur rather than as art. */
function blockEllipse(ctx, cx, cy, rx, ry, colour, alpha = 1) {
  ctx.fillStyle = colour;
  const prev = ctx.globalAlpha;
  ctx.globalAlpha = prev * alpha;
  const r2 = Math.max(0.5, ry);
  for (let y = -ry; y <= ry; y++) {
    const t = 1 - (y * y) / (r2 * r2);
    if (t <= 0) continue;
    const half = Math.round(rx * Math.sqrt(t));
    ctx.fillRect(Math.round(cx - half), Math.round(cy + y), half * 2 + 1, 1);
  }
  ctx.globalAlpha = prev;
}

/* Radial falloff baked to a bitmap so the loop can blit it with 'lighter'. The
 * steps are deliberately few: a smooth glow looks like a modern bloom shader,
 * and this game is meant to look like it shipped on a cartridge. */
function radialGlow(r, colour, steps = 9, peak = 1) {
  const s = surface(r * 2, r * 2);
  for (let i = steps; i >= 1; i--) {
    const k = i / steps;
    s.ctx.globalAlpha = peak * Math.pow(1 - k, 2.1);
    blockEllipse(s.ctx, r, r, Math.round(r * k), Math.round(r * k), colour);
  }
  s.ctx.globalAlpha = 1;
  return s.canvas;
}

function ovalGlow(rx, ry, colour, steps = 8, peak = 0.8) {
  const s = surface(rx * 2 + 2, ry * 2 + 2);
  for (let i = steps; i >= 1; i--) {
    const k = i / steps;
    s.ctx.globalAlpha = peak * Math.pow(1 - k, 2);
    blockEllipse(s.ctx, rx + 1, ry + 1, Math.round(rx * k), Math.round(ry * k), colour);
  }
  s.ctx.globalAlpha = 1;
  return s.canvas;
}

/* ================================================================
 * LAYER PAINTERS
 * ================================================================
 * Each painter fills a transparent canvas `W` wide and `H` tall with one depth
 * layer's silhouette, bottom-aligned unless it says otherwise. They share a
 * colour pack:
 *
 *   c.body   the mass
 *   c.light  faces turned toward the key light (upper left)
 *   c.dark   faces turned away
 *   c.edge   the one-pixel top rim, usually the biome accent at low mix
 *   c.glow   windows, crystal cores, eyes in the dark
 *
 * A silhouette with a lit left face, a dark right face and a rim is readable at
 * any size. A flat silhouette is a sticker.
 */

/* Mountains, ridges, dunes. Built as a height field so peaks can overlap
 * without leaving a notch where two runs meet. */
function paintRidge(ctx, W, H, rand, c, o = {}) {
  const hs = new Int16Array(W);
  const sharp = o.sharp === undefined ? 1.7 : o.sharp;
  const minH = o.minH === undefined ? 0.28 : o.minH;
  let x = 0;
  while (x < W) {
    const pw = Math.round((o.wide ? 26 : 14) + rand() * (o.wide ? 46 : 30));
    const ph = Math.round(H * (minH + rand() * (1 - minH - 0.06)));
    for (let i = 0; i < pw; i++) {
      const t = Math.abs(i - pw / 2) / (pw / 2);
      const col = Math.round(ph * (1 - Math.pow(t, sharp)));
      const gx = ((x + i) % W + W) % W;
      if (col > hs[gx]) hs[gx] = col;
    }
    x += Math.round(pw * (0.42 + rand() * 0.34));
  }
  for (let gx = 0; gx < W; gx++) {
    const col = hs[gx];
    if (col <= 0) continue;
    const rising = col > hs[(gx - 1 + W) % W];
    ctx.fillStyle = c.body;
    ctx.fillRect(gx, H - col, 1, col);
    // Faceting: the lit face is the one climbing toward its peak.
    ctx.fillStyle = rising ? c.light : c.dark;
    ctx.fillRect(gx, H - col, 1, Math.min(col, Math.round(col * 0.34) + 2));
    ctx.fillStyle = c.edge;
    ctx.fillRect(gx, H - col, 1, 1);
    if (o.snow && col > H * 0.6) {
      const capped = Math.round((col - H * 0.6) * 0.7);
      ctx.fillStyle = c.cap || c.edge;
      for (let y = 0; y < capped; y++) {
        if (((gx * 7 + y * 13) % 11) > y) ctx.fillRect(gx, H - col + y, 1, 1);
      }
    }
  }
}

/* Rolling hills with an optional drystone wall along the near crest. */
function paintHills(ctx, W, H, rand, c, o = {}) {
  const a1 = 0.6 + rand() * 0.8, a2 = 1.7 + rand() * 1.4;
  const p1 = rand() * 6.283, p2 = rand() * 6.283;
  const amp = H * (o.amp || 0.22);
  const base = H * (o.base || 0.55);
  for (let x = 0; x < W; x++) {
    const u = (x / W) * 6.283;
    const col = Math.round(base + Math.sin(u * a1 + p1) * amp
                                + Math.sin(u * a2 + p2) * amp * 0.45);
    ctx.fillStyle = c.body;
    ctx.fillRect(x, H - col, 1, col);
    ctx.fillStyle = c.dark;
    ctx.fillRect(x, H - Math.round(col * 0.42), 1, Math.round(col * 0.42));
    ctx.fillStyle = c.edge;
    ctx.fillRect(x, H - col, 1, 1);
    ctx.fillStyle = c.light;
    ctx.fillRect(x, H - col + 1, 1, 1);
  }
  if (o.wall) {
    // Stones sized off a hash of x, so the wall does not pulse regularly.
    for (let x = 0; x < W; x += 5) {
      const u = (x / W) * 6.283;
      const col = Math.round(base + Math.sin(u * a1 + p1) * amp
                                  + Math.sin(u * a2 + p2) * amp * 0.45);
      const sw = 4 + ((x * 31) % 3);
      const sh = 3 + ((x * 17) % 3);
      fillWrap(ctx, W, x, H - col - sh, sw, sh, c.dark);
      fillWrap(ctx, W, x, H - col - sh, sw, 1, c.light);
    }
  }
}

/* Conifers and dead timber. `dead` swaps the canopy for bare branch runs, which
 * is most of what separates a forest from a swamp at silhouette scale. */
function paintTreeline(ctx, W, H, rand, c, o = {}) {
  const step = o.step || 7;
  for (let x = 0; x < W; x += Math.max(3, Math.round(step * (0.5 + rand())))) {
    const th = Math.round(H * (0.42 + rand() * 0.58));
    const tw = o.dead ? 2 : 2 + Math.round(rand() * 2);
    fillWrap(ctx, W, x, H - th, tw, th, c.dark);
    fillWrap(ctx, W, x, H - th, 1, th, c.body);
    if (o.dead) {
      const arms = 2 + Math.round(rand() * 3);
      for (let a = 0; a < arms; a++) {
        const ay = H - th + 2 + Math.round(rand() * (th * 0.6));
        const dir = rand() < 0.5 ? -1 : 1;
        const len = 3 + Math.round(rand() * 7);
        for (let i = 0; i < len; i++) {
          fillWrap(ctx, W, x + dir * i, ay - Math.round(i * 0.7), 1, 1, c.body);
        }
      }
    } else {
      // Stepped canopy: four tiers, each narrower and one tone lighter on its
      // left half. Four tiers is the fewest that still reads as a conifer.
      const tiers = 3 + Math.round(rand() * 2);
      for (let r = 0; r < tiers; r++) {
        const cw = Math.round((tiers - r) * 3 + 3 + rand() * 2);
        const cy = H - th - 2 + r * Math.round(th * 0.16);
        fillWrap(ctx, W, x + (tw >> 1) - (cw >> 1), cy, cw, Math.round(th * 0.2) + 2, c.body);
        fillWrap(ctx, W, x + (tw >> 1) - (cw >> 1), cy, Math.max(1, cw >> 1), 1, c.light);
        fillWrap(ctx, W, x + (tw >> 1) + (cw >> 1) - 2, cy + 1,
                 2, Math.round(th * 0.2), c.dark);
      }
      fillWrap(ctx, W, x + (tw >> 1) - 1, H - th - 4, 2, 4, c.body);
      fillWrap(ctx, W, x + (tw >> 1) - 1, H - th - 4, 1, 1, c.edge);
    }
  }
}

/* Towns, keeps, citadels, ruins. One generator, four moods, because a village
 * roofline and a castle roofline differ by pitch and battlement, not by kind. */
function paintSkyline(ctx, W, H, rand, c, o = {}) {
  const style = o.style || 'castle';
  let x = 0;
  while (x < W) {
    const bw = Math.round((style === 'village' ? 10 : 14) + rand() * (style === 'village' ? 12 : 18));
    const bh = Math.round(H * (0.34 + rand() * 0.64));
    fillWrap(ctx, W, x, H - bh, bw, bh, c.body);
    fillWrap(ctx, W, x, H - bh, 1, bh, c.light);                 // lit left jamb
    fillWrap(ctx, W, x + bw - 2, H - bh, 2, bh, c.dark);          // shaded right
    fillWrap(ctx, W, x, H - bh, bw, 1, c.edge);

    if (style === 'village') {
      // Ridge first, then widen on the way down. Building it the other way
      // round draws the roof upside down, which is a shape the eye refuses.
      const rh = Math.max(3, bw >> 1);
      for (let j = 0; j < rh; j++) {
        const rw = Math.max(2, Math.round(bw * (j + 1) / rh));
        fillWrap(ctx, W, x + ((bw - rw) >> 1), H - bh - rh + j, rw, 1,
                 j < 2 ? c.edge : (j < rh - 2 ? c.body : c.dark));
        fillWrap(ctx, W, x + ((bw - rw) >> 1), H - bh - rh + j, 1, 1, c.light);
      }
      if (rand() < 0.4) {                                         // chimney
        const cxp = x + 2 + Math.round(rand() * (bw - 6));
        fillWrap(ctx, W, cxp, H - bh - rh - 4, 3, 6, c.dark);
        fillWrap(ctx, W, cxp, H - bh - rh - 4, 3, 1, c.edge);
      }
    } else if (style === 'ruin') {
      // Bite chunks out of the crown, then out of one wall. A ruin is a shape
      // with something missing, not a shorter building.
      const bites = 1 + Math.round(rand() * 2);
      for (let b = 0; b < bites; b++) {
        const bx = x + Math.round(rand() * (bw - 4));
        clearWrap(ctx, W, bx, H - bh, 3 + Math.round(rand() * 4),
                  Math.round(rand() * bh * 0.45) + 2);
      }
      if (rand() < 0.5) clearWrap(ctx, W, x + bw - 3, H - bh, 3, Math.round(bh * 0.7));
    } else {
      for (let i = 0; i < bw; i += 4) {                           // battlements
        fillWrap(ctx, W, x + i, H - bh - 3, 2, 3, c.body);
        fillWrap(ctx, W, x + i, H - bh - 3, 2, 1, c.edge);
      }
      if (rand() < 0.45) {                                        // spire
        const sw = 5, sx = x + (bw >> 1) - 2, sh = Math.round(bh * 0.45) + 6;
        fillWrap(ctx, W, sx, H - bh - sh, sw, sh, c.body);
        fillWrap(ctx, W, sx, H - bh - sh, 1, sh, c.light);
        for (let i = 0; i <= sw >> 1; i++) {
          fillWrap(ctx, W, sx + i, H - bh - sh - 4 + i, sw - i * 2, 1, c.dark);
        }
        fillWrap(ctx, W, sx + 2, H - bh - sh - 7, 1, 3, c.edge);
      }
    }
    if (c.glow && style !== 'ruin') {
      const rows = Math.max(1, Math.round(bh / 9));
      for (let r = 0; r < rows; r++) {
        for (let w2 = 3; w2 < bw - 3; w2 += 5) {
          if (rand() < 0.42) {
            fillWrap(ctx, W, x + w2, H - bh + 5 + r * 8, 2, 3, c.glow);
          }
        }
      }
    }
    x += bw + 1 + Math.round(rand() * 5);
  }
}

/* Pillars, arches and vaulting. Dungeons, citadels, ruins and castles all run
 * on this; `broken` decides whether the arcade still holds a roof up. */
function paintColonnade(ctx, W, H, rand, c, o = {}) {
  const pw = o.pillarW || 10;
  const gap = o.gap || 16;
  const top = o.top === undefined ? Math.round(H * 0.22) : o.top;
  const pitch = pw + gap;
  const count = Math.max(2, Math.round(W / pitch));
  const realPitch = W / count;   // exact division keeps the tiling honest

  if (!o.broken) {                                              // entablature
    fillWrap(ctx, W, 0, top - 6, W, 6, c.body);
    fillWrap(ctx, W, 0, top - 6, W, 1, c.edge);
    fillWrap(ctx, W, 0, top - 1, W, 1, c.dark);
  }
  for (let i = 0; i < count; i++) {
    const x = Math.round(i * realPitch);
    const cut = o.broken && rand() < 0.4;
    const ph = cut ? Math.round((H - top) * (0.3 + rand() * 0.5)) : H - top;
    const y = H - ph;
    fillWrap(ctx, W, x, y, pw, ph, c.body);
    fillWrap(ctx, W, x, y, 2, ph, c.light);
    fillWrap(ctx, W, x + pw - 3, y, 3, ph, c.dark);
    for (let f = 3; f < pw - 3; f += 3) {                        // fluting
      fillWrap(ctx, W, x + f, y, 1, ph, c.dark);
    }
    if (!cut) {
      fillWrap(ctx, W, x - 2, top, pw + 4, 3, c.body);           // capital
      fillWrap(ctx, W, x - 2, top, pw + 4, 1, c.edge);
      fillWrap(ctx, W, x - 1, H - 4, pw + 2, 4, c.body);         // base
      fillWrap(ctx, W, x - 1, H - 4, pw + 2, 1, c.light);
      if (o.arch) {
        const span = Math.round(realPitch) - pw;
        for (let k = 0; k <= span >> 1; k++) {                   // arch haunch
          fillWrap(ctx, W, x + pw + k, top + 3 + (span >> 1) - k, 1,
                   Math.max(1, (span >> 1) - k), c.body);
          fillWrap(ctx, W, x + Math.round(realPitch) - k - 1,
                   top + 3 + (span >> 1) - k, 1,
                   Math.max(1, (span >> 1) - k), c.dark);
        }
      }
    } else {
      fillWrap(ctx, W, x, y, pw, 1, c.edge);                     // snapped top
      fillWrap(ctx, W, x + 1, y - 1, Math.max(1, pw - 4), 1, c.body);
    }
  }
}

/* A masonry wall. The far layer of anything indoors, and the thing that makes a
 * dungeon read as enclosed rather than as night. */
function paintWall(ctx, W, H, rand, c, o = {}) {
  const bh = o.brick || 8;
  const bw = o.brickW || 16;
  // Mortar at full contrast turns a wall into a scanline pattern, which at this
  // scale reads as interference rather than as masonry.
  const mortar = mix(c.dark, c.body, 0.5);
  const highlight = mix(c.light, c.body, 0.45);
  ctx.fillStyle = c.body;
  ctx.fillRect(0, 0, W, H);
  for (let y = 0; y < H; y += bh) {
    const off = ((y / bh) % 2) * (bw >> 1);
    fillWrap(ctx, W, 0, y, W, 1, mortar);
    for (let x = 0; x < W; x += bw) {
      fillWrap(ctx, W, x + off, y, 1, bh, mortar);
      fillWrap(ctx, W, x + off + 1, y + 1, bw - 2, 1, highlight);
      if (rand() < 0.16) fillWrap(ctx, W, x + off + 2, y + 2, bw - 4, bh - 3, c.dark);
    }
  }
  // A wall that ends in a ruler-straight line across the frame reads as a band
  // of colour, not as architecture. Cornice, dentils, then a broken rubble edge.
  ctx.fillStyle = c.light;
  ctx.fillRect(0, 0, W, 2);
  ctx.fillStyle = c.dark;
  ctx.fillRect(0, 2, W, 1);
  for (let x = 0; x < W; x += 6) {
    fillWrap(ctx, W, x, 3, 3, 3, c.body);
    fillWrap(ctx, W, x, 3, 1, 3, c.light);
  }
  for (let x = 0; x < W; x += 2) {
    const notch = Math.round(rand() * 3);
    if (notch) clearWrap(ctx, W, x, 0, 2, notch);
  }

  if (o.stains) {                                               // damp streaks
    for (let i = 0; i < Math.round(W / 12); i++) {
      const x = Math.round(rand() * W);
      const len = Math.round(H * (0.3 + rand() * 0.6));
      for (let y = 0; y < len; y++) {
        if (((x * 13 + y * 7) % 5) < 3) fillWrap(ctx, W, x, y, 1 + (y % 2), 1, c.dark);
      }
    }
  }
}

/* Cavern teeth. `down` hangs them from the ceiling, otherwise they grow from
 * the floor. Both, on different layers, is what a cave actually looks like. */
function paintCavern(ctx, W, H, rand, c, o = {}) {
  const down = !!o.down;
  const step = o.dense ? 7 : 11;
  for (let x = 0; x < W; x += Math.max(4, Math.round(step * (0.5 + rand())))) {
    // Tall and thin reads as rain. A cave tooth is short and fat with a fast
    // taper, and it needs to be wider than the gap beside it.
    const th = Math.round(H * (0.18 + rand() * 0.44));
    const tw = 5 + Math.round(rand() * 10);
    for (let i = 0; i < th; i++) {
      const k = i / th;
      const cw = Math.max(1, Math.round(tw * (1 - k * k)));
      const y = down ? i : H - 1 - i;
      fillWrap(ctx, W, x + ((tw - cw) >> 1), y, cw, 1, c.body);
      fillWrap(ctx, W, x + ((tw - cw) >> 1), y, 1, 1, c.light);
      if (cw > 2) fillWrap(ctx, W, x + ((tw - cw) >> 1) + cw - 1, y, 1, 1, c.dark);
    }
    fillWrap(ctx, W, x + (tw >> 1), down ? th - 1 : H - th, 1, 1, c.edge);
  }
  // The rock the teeth hang off, so the layer does not float.
  fillWrap(ctx, W, 0, down ? 0 : H - 3, W, 3, c.body);
  fillWrap(ctx, W, 0, down ? 2 : H - 3, W, 1, down ? c.dark : c.edge);
}

/* Crystal clusters and pit timber. The mine's whole identity is a cold seam of
 * light inside a warm, rotting frame. */
function paintCrystal(ctx, W, H, rand, c, o = {}) {
  for (let x = 0; x < W; x += 9 + Math.round(rand() * 14)) {
    const shards = 2 + Math.round(rand() * 3);
    for (let s = 0; s < shards; s++) {
      const sh = Math.round(H * (0.2 + rand() * 0.6));
      const sw = 3 + Math.round(rand() * 4);
      const sx = x + s * 3 - shards;
      const lean = rand() < 0.5 ? -1 : 1;
      for (let i = 0; i < sh; i++) {
        const k = i / sh;
        const cw = Math.max(1, Math.round(sw * (1 - k * 0.85)));
        const px = sx + Math.round(lean * k * 3);
        fillWrap(ctx, W, px, H - 1 - i, cw, 1, c.body);
        fillWrap(ctx, W, px, H - 1 - i, 1, 1, c.light);
        if (k > 0.25 && k < 0.9 && cw > 1) {
          fillWrap(ctx, W, px + (cw >> 1), H - 1 - i, 1, 1, c.glow || c.edge);
        }
      }
    }
  }
  if (o.timber) {
    for (let x = 0; x < W; x += 34 + Math.round(rand() * 20)) {
      const ph = Math.round(H * 0.8);
      fillWrap(ctx, W, x, H - ph, 4, ph, c.dark);
      fillWrap(ctx, W, x, H - ph, 1, ph, c.body);
      fillWrap(ctx, W, x + 22, H - ph, 4, ph, c.dark);
      fillWrap(ctx, W, x - 2, H - ph, 30, 4, c.dark);
      fillWrap(ctx, W, x - 2, H - ph, 30, 1, c.body);
    }
  }
}

/* Leaf masses hanging from the top of the frame, plus vines. Used for the
 * canopy and for the near layer of both forests. */
function paintCanopyMass(ctx, W, H, rand, c, o = {}) {
  const depth = o.depth || 0.55;
  for (let x = -6; x < W + 6; x += 5 + Math.round(rand() * 5)) {
    const mh = Math.round(H * depth * (0.5 + rand()));
    for (let y = 0; y < mh; y++) {
      const k = y / mh;
      const half = Math.round((1 - k * k) * (5 + rand() * 3)) + 2;
      fillWrap(ctx, W, x - half, y, half * 2, 1, k < 0.3 ? c.dark : c.body);
    }
    fillWrap(ctx, W, x - 3, 0, 6, 1, c.light);
  }
  if (o.vines) {
    for (let i = 0; i < Math.round(W / 16); i++) {
      const x = Math.round(rand() * W);
      const len = Math.round(H * (0.4 + rand() * 0.5));
      for (let y = 0; y < len; y++) {
        fillWrap(ctx, W, x + Math.round(Math.sin(y * 0.22 + i) * 2), y, 1, 1,
                 y % 7 === 0 ? c.edge : c.dark);
      }
    }
  }
}

/* Tiered stands with a crowd in them. The heads are 2x2 and the shoulders 4x2:
 * any more detail at this distance turns into noise. */
function paintCrowd(ctx, W, H, rand, c, o = {}) {
  const tiers = o.tiers || 3;
  const th = Math.floor(H / tiers);
  for (let t = 0; t < tiers; t++) {
    const y = H - (t + 1) * th;
    fillWrap(ctx, W, 0, y, W, th, t % 2 ? c.body : c.dark);
    fillWrap(ctx, W, 0, y, W, 1, c.light);
    for (let x = 1; x < W; x += 5) {
      if (rand() < 0.86) {
        const hx = x + Math.round(rand() * 2);
        fillWrap(ctx, W, hx, y + 2, 4, 3, c.dark);               // shoulders
        fillWrap(ctx, W, hx + 1, y - 1, 2, 3, rand() < 0.2 ? c.edge : c.body);
      }
    }
    fillWrap(ctx, W, 0, y + th - 2, W, 2, c.dark);               // rail
  }
  if (o.banners) {
    for (let x = 8; x < W; x += 30 + Math.round(rand() * 18)) {
      const bh = 12 + Math.round(rand() * 10);
      fillWrap(ctx, W, x, 0, 7, bh, c.glow || c.edge);
      fillWrap(ctx, W, x, 0, 1, bh, c.light);
      fillWrap(ctx, W, x + 6, 0, 1, bh, c.dark);
      fillWrap(ctx, W, x + 2, bh - 6, 3, 3, c.dark);             // device
      for (let i = 0; i < 4; i++) fillWrap(ctx, W, x + i, bh + i, 7 - i * 2, 1, c.glow || c.edge);
    }
  }
}

/* Iron frame: beams, struts, diagonal braces and gear discs. The tower and the
 * mine both run on it, one in blued steel and one in rust. */
function paintGantry(ctx, W, H, rand, c, o = {}) {
  const decks = o.decks || 3;
  for (let d = 0; d < decks; d++) {
    const y = Math.round(((d + 1) / (decks + 1)) * H);
    fillWrap(ctx, W, 0, y, W, 3, c.body);
    fillWrap(ctx, W, 0, y, W, 1, c.light);
    fillWrap(ctx, W, 0, y + 2, W, 1, c.dark);
    for (let x = 0; x < W; x += 18 + Math.round(rand() * 10)) {
      const sh = Math.round(H / (decks + 1));
      fillWrap(ctx, W, x, y, 3, sh, c.dark);
      fillWrap(ctx, W, x, y, 1, sh, c.body);
      for (let i = 0; i < sh; i += 2) {                          // brace
        fillWrap(ctx, W, x + 3 + Math.round(i * 0.8), y + i, 2, 1, c.dark);
      }
    }
  }
  if (o.gears) {
    for (let i = 0; i < Math.round(W / 70) + 1; i++) {
      const gx = Math.round(rand() * W), gy = Math.round(H * (0.2 + rand() * 0.5));
      const r = 9 + Math.round(rand() * 7);
      blockEllipse(ctx, gx, gy, r, r, c.body);
      blockEllipse(ctx, gx, gy, r - 3, r - 3, c.dark);
      blockEllipse(ctx, gx, gy, 2, 2, c.body);
      for (let t = 0; t < 10; t++) {                             // teeth
        const a = (t / 10) * 6.283;
        fillWrap(ctx, W, gx + Math.cos(a) * (r + 1) - 1, gy + Math.sin(a) * (r + 1) - 1,
                 3, 3, c.body);
      }
      blockEllipse(ctx, gx - 2, gy - 2, r - 6, r - 6, c.light, 0.5);
    }
  }
}

/* Reeds and standing water. Sold entirely by the lean and the reflections. */
function paintReeds(ctx, W, H, rand, c, o = {}) {
  if (o.water) {
    fillWrap(ctx, W, 0, H - Math.round(H * 0.3), W, Math.round(H * 0.3), c.dark);
    for (let i = 0; i < W; i += 3) {
      if (rand() < 0.4) {
        fillWrap(ctx, W, i, H - Math.round(H * 0.3) + Math.round(rand() * H * 0.28),
                 2 + Math.round(rand() * 4), 1, c.light);
      }
    }
  }
  for (let x = 0; x < W; x += 2 + Math.round(rand() * 3)) {
    const rh = Math.round(H * (0.3 + rand() * 0.6));
    const lean = (rand() - 0.5) * 5;
    for (let y = 0; y < rh; y++) {
      const k = y / rh;
      fillWrap(ctx, W, x + Math.round(lean * k * k), H - 1 - y, 1, 1,
               k > 0.8 ? c.light : (k > 0.4 ? c.body : c.dark));
    }
    if (rand() < 0.24) {                                        // seed head
      fillWrap(ctx, W, x + Math.round(lean), H - rh - 3, 2, 4, c.edge);
    }
  }
}

/* Dunes, rubble fields and broken monoliths. The wastes and the ruins share it;
 * the ruins get taller stones and the wastes get bones. */
function paintDebris(ctx, W, H, rand, c, o = {}) {
  const base = Math.round(H * 0.4);
  for (let x = 0; x < W; x++) {
    const u = (x / W) * 6.283;
    const col = Math.round(base + Math.sin(u * 2.1 + 0.7) * H * 0.18
                                + Math.sin(u * 5.3) * H * 0.07);
    ctx.fillStyle = c.body;
    ctx.fillRect(x, H - col, 1, col);
    ctx.fillStyle = c.edge;
    ctx.fillRect(x, H - col, 1, 1);
    ctx.fillStyle = c.dark;
    ctx.fillRect(x, H - Math.round(col * 0.5), 1, Math.round(col * 0.5));
  }
  for (let x = 0; x < W; x += 20 + Math.round(rand() * 26)) {
    const mh = Math.round(H * (0.4 + rand() * 0.55));
    const mw = 4 + Math.round(rand() * 6);
    const lean = Math.round((rand() - 0.5) * 4);
    for (let y = 0; y < mh; y++) {
      const k = y / mh;
      fillWrap(ctx, W, x + Math.round(lean * k), H - Math.round(H * 0.38) - y, mw, 1,
               k > 0.9 ? c.edge : c.body);
      fillWrap(ctx, W, x + Math.round(lean * k), H - Math.round(H * 0.38) - y, 1, 1, c.light);
      fillWrap(ctx, W, x + Math.round(lean * k) + mw - 1,
               H - Math.round(H * 0.38) - y, 1, 1, c.dark);
    }
    if (o.snapped && rand() < 0.5) {
      clearWrap(ctx, W, x - 1, H - Math.round(H * 0.38) - mh,
                mw + 2, Math.round(mh * 0.3));
    }
  }
  if (o.bones) {
    for (let i = 0; i < Math.round(W / 24); i++) {
      const bx = Math.round(rand() * W), by = H - Math.round(rand() * H * 0.3) - 4;
      const len = 6 + Math.round(rand() * 10);
      fillWrap(ctx, W, bx, by, len, 2, c.cap || c.edge);
      fillWrap(ctx, W, bx - 1, by - 1, 2, 4, c.cap || c.edge);
      fillWrap(ctx, W, bx + len - 1, by - 1, 2, 4, c.cap || c.edge);
    }
  }
}

const PAINTERS = {
  ridge: paintRidge,
  hills: paintHills,
  treeline: paintTreeline,
  skyline: paintSkyline,
  colonnade: paintColonnade,
  wall: paintWall,
  cavern: paintCavern,
  crystal: paintCrystal,
  canopy: paintCanopyMass,
  crowd: paintCrowd,
  gantry: paintGantry,
  reeds: paintReeds,
  debris: paintDebris,
};

/* ================================================================
 * BIOMES
 * ================================================================
 * One entry per biome in gauntlet/world.py. Seventeen rooms, each with three
 * depth layers, a horizon treatment, an animated element and its own frame
 * furniture. The region palette still tints everything — `hue` is how much of
 * the region's own colour survives the grade — so Hashmap Highlands and Twin
 * Pointer Pass share a painter and still do not look alike.
 *
 * layer.src   which palette entry the layer is graded from
 * layer.tone  lightness offset after grading; far layers sit darker and flatter
 * layer.depth parallax depth, 0 = painted on the sky, 1 = at the platform
 * layer.rate  logical pixels per second of self-motion (wind, not camera)
 */
const BIOMES = {
  village: {
    accent: METAL.fire, hue: 0.66, fog: '#2a2733',
    sky: ['#0a0912', '#1b1726', '#2c2130'], horizon: 'moon',
    anim: ['torch', 'fog'], occluder: 'banner', platform: 'cobble',
    layers: [
      { paint: 'ridge',   src: 'far',  h: 42, depth: 0.10, rate: 1, tone: -34, o: { wide: true, minH: 0.2 } },
      { paint: 'skyline', src: 'mid',  h: 50, depth: 0.30, rate: 4, tone: -20, o: { style: 'village', glow: true } },
      { paint: 'skyline', src: 'mid',  h: 36, depth: 0.62, rate: 11, tone: -6, o: { style: 'village', glow: true } },
    ],
  },
  grass: {
    accent: METAL.violet, hue: 0.58, fog: '#26283a',
    sky: ['#080a14', '#141a2c', '#232a42'], horizon: 'storm',
    anim: ['lightning', 'rain', 'fog'], occluder: 'reed', platform: 'sod',
    layers: [
      { paint: 'ridge',    src: 'far',    h: 38, depth: 0.10, rate: 1, tone: -36, o: { wide: true, minH: 0.18 } },
      { paint: 'treeline', src: 'foliage', h: 34, depth: 0.32, rate: 5, tone: -22, o: { step: 9 } },
      { paint: 'hills',    src: 'ground', h: 30, depth: 0.60, rate: 12, tone: -10, o: { wall: true, amp: 0.3 } },
    ],
  },
  highland: {
    accent: METAL.cyan, hue: 0.58, fog: '#2b3040',
    sky: ['#070b12', '#131b28', '#233040'], horizon: 'moon',
    anim: ['fog', 'snow'], occluder: 'stone', platform: 'flag',
    layers: [
      { paint: 'ridge', src: 'far',    h: 50, depth: 0.08, rate: 1, tone: -38, o: { wide: true, sharp: 1.4, snow: true } },
      { paint: 'ridge', src: 'mid',    h: 38, depth: 0.30, rate: 4, tone: -22, o: { sharp: 1.9 } },
      { paint: 'hills', src: 'ground', h: 28, depth: 0.62, rate: 11, tone: -8, o: { wall: true } },
    ],
  },
  forest: {
    accent: METAL.bile, hue: 0.68, fog: '#1e2a24',
    sky: ['#070c0a', '#111c16', '#1b2a20'], horizon: 'fogbank',
    anim: ['fog', 'flies'], occluder: 'branch', platform: 'root',
    layers: [
      { paint: 'treeline', src: 'far',     h: 46, depth: 0.10, rate: 1, tone: -38, o: { step: 5 } },
      { paint: 'treeline', src: 'foliage', h: 40, depth: 0.32, rate: 4, tone: -22, o: { step: 8 } },
      { paint: 'treeline', src: 'foliage', h: 34, depth: 0.64, rate: 12, tone: -8, o: { step: 13 } },
    ],
  },
  cave: {
    accent: METAL.cyan, hue: 0.7, fog: '#1c202a',
    sky: ['#050608', '#0c0f15', '#141921'], horizon: 'ceiling',
    anim: ['drip', 'fog'], occluder: 'stalagmite', platform: 'stone',
    layers: [
      { paint: 'wall',   src: 'far',    h: 60, depth: 0.08, rate: 0, tone: -40, o: { stains: true, brick: 9 } },
      { paint: 'cavern', src: 'mid',    h: 44, depth: 0.30, rate: 3, tone: -26, o: { down: true, dense: true } },
      { paint: 'cavern', src: 'ground', h: 30, depth: 0.64, rate: 10, tone: -10, o: {} },
    ],
  },
  swamp: {
    accent: METAL.bile, hue: 0.6, fog: '#243026',
    sky: ['#070b09', '#121a14', '#1d2a1e'], horizon: 'fogbank',
    anim: ['fog', 'rain', 'flies'], occluder: 'reed', platform: 'bog',
    layers: [
      { paint: 'treeline', src: 'far',     h: 44, depth: 0.10, rate: 1, tone: -38, o: { dead: true, step: 8 } },
      { paint: 'treeline', src: 'mid',     h: 36, depth: 0.32, rate: 4, tone: -24, o: { dead: true, step: 11 } },
      { paint: 'reeds',    src: 'foliage', h: 28, depth: 0.66, rate: 13, tone: -10, o: { water: true } },
    ],
  },
  mountain: {
    accent: METAL.chrome, hue: 0.62, fog: '#2d3340',
    sky: ['#060910', '#101725', '#1e2838'], horizon: 'storm',
    anim: ['snow', 'lightning'], occluder: 'stone', platform: 'stone',
    layers: [
      { paint: 'ridge', src: 'far',    h: 56, depth: 0.07, rate: 1, tone: -40, o: { wide: true, sharp: 1.3, snow: true } },
      { paint: 'ridge', src: 'mid',    h: 42, depth: 0.28, rate: 3, tone: -24, o: { sharp: 1.6, snow: true } },
      { paint: 'ridge', src: 'ground', h: 26, depth: 0.64, rate: 10, tone: -10, o: { sharp: 2.2 } },
    ],
  },
  mine: {
    accent: METAL.fire, hue: 0.55, fog: '#2a1d18',
    sky: ['#0a0605', '#160c08', '#23120b'], horizon: 'glow',
    anim: ['ember', 'lava'], occluder: 'chain', platform: 'plank',
    layers: [
      { paint: 'wall',    src: 'far',    h: 58, depth: 0.08, rate: 0, tone: -40, o: { stains: true } },
      { paint: 'crystal', src: 'accent', h: 40, depth: 0.30, rate: 3, tone: -20, o: { timber: true } },
      { paint: 'gantry',  src: 'ground', h: 34, depth: 0.64, rate: 11, tone: -12, o: { decks: 2 } },
    ],
  },
  citadel: {
    accent: METAL.violet, hue: 0.6, fog: '#262038',
    sky: ['#08060f', '#130e20', '#1e1630'], horizon: 'glass',
    anim: ['godray', 'fog'], occluder: 'pillar', platform: 'marble',
    layers: [
      { paint: 'wall',      src: 'far',    h: 62, depth: 0.08, rate: 0, tone: -42, o: { brick: 8, brickW: 18 } },
      { paint: 'colonnade', src: 'mid',    h: 52, depth: 0.30, rate: 3, tone: -24, o: { arch: true, pillarW: 11, gap: 20 } },
      { paint: 'colonnade', src: 'ground', h: 40, depth: 0.62, rate: 10, tone: -10, o: { pillarW: 14, gap: 34 } },
    ],
  },
  deepforest: {
    accent: METAL.violet, hue: 0.56, fog: '#20182e',
    sky: ['#060510', '#0e0b1a', '#171128'], horizon: 'fogbank',
    anim: ['fog', 'flies'], occluder: 'branch', platform: 'root',
    layers: [
      { paint: 'treeline', src: 'far', h: 50, depth: 0.09, rate: 1, tone: -42, o: { step: 4 } },
      { paint: 'treeline', src: 'mid', h: 44, depth: 0.30, rate: 3, tone: -28, o: { step: 7, dead: true } },
      { paint: 'canopy',   src: 'foliage', h: 44, depth: 0.66, rate: 9, tone: -14, o: { vines: true, depth: 0.8 }, top: true },
    ],
  },
  canopy: {
    accent: METAL.cyan, hue: 0.58, fog: '#1c2a2c',
    sky: ['#060c10', '#0f1a22', '#1a2a32'], horizon: 'moon',
    anim: ['leaves', 'fog'], occluder: 'branch', platform: 'branch',
    layers: [
      { paint: 'treeline', src: 'far',     h: 44, depth: 0.09, rate: 1, tone: -40, o: { step: 6 } },
      { paint: 'canopy',   src: 'foliage', h: 40, depth: 0.30, rate: 3, tone: -24, o: { depth: 0.7 }, top: true },
      { paint: 'canopy',   src: 'foliage', h: 46, depth: 0.64, rate: 10, tone: -10, o: { vines: true, depth: 0.9 }, top: true },
    ],
  },
  wastes: {
    accent: METAL.blood, hue: 0.7, fog: '#302a2c',
    sky: ['#0a0708', '#170f10', '#241618'], horizon: 'sun',
    anim: ['ash', 'fog'], occluder: 'bone', platform: 'ash',
    layers: [
      { paint: 'ridge',  src: 'far',    h: 40, depth: 0.09, rate: 1, tone: -38, o: { wide: true, minH: 0.16 } },
      { paint: 'debris', src: 'mid',    h: 40, depth: 0.30, rate: 3, tone: -24, o: { snapped: true } },
      { paint: 'debris', src: 'ground', h: 32, depth: 0.64, rate: 10, tone: -10, o: { bones: true } },
    ],
  },
  ruins: {
    accent: METAL.bone, hue: 0.66, fog: '#2c2a30',
    sky: ['#08070c', '#141218', '#201c24'], horizon: 'moon',
    anim: ['ash', 'fog'], occluder: 'pillar', platform: 'flag',
    layers: [
      { paint: 'skyline',   src: 'far',    h: 48, depth: 0.09, rate: 1, tone: -40, o: { style: 'ruin' } },
      { paint: 'colonnade', src: 'mid',    h: 46, depth: 0.30, rate: 3, tone: -24, o: { broken: true, pillarW: 9, gap: 18 } },
      { paint: 'debris',    src: 'ground', h: 30, depth: 0.64, rate: 10, tone: -10, o: { snapped: true } },
    ],
  },
  dungeon: {
    accent: METAL.fire, hue: 0.72, fog: '#232430',
    sky: ['#050508', '#0c0c11', '#13131a'], horizon: 'ceiling',
    anim: ['torch', 'drip'], occluder: 'chain', platform: 'stone',
    layers: [
      { paint: 'wall',      src: 'far',    h: 62, depth: 0.07, rate: 0, tone: -42, o: { stains: true } },
      { paint: 'colonnade', src: 'mid',    h: 50, depth: 0.28, rate: 2, tone: -26, o: { arch: true, pillarW: 12, gap: 22 } },
      { paint: 'colonnade', src: 'ground', h: 38, depth: 0.62, rate: 9, tone: -12, o: { pillarW: 16, gap: 40 } },
    ],
  },
  tower: {
    accent: METAL.cyan, hue: 0.6, fog: '#20283a',
    sky: ['#05070f', '#0d1322', '#172034'], horizon: 'storm',
    anim: ['lightning', 'rain', 'fog'], occluder: 'chain', platform: 'iron',
    layers: [
      { paint: 'skyline', src: 'far',    h: 44, depth: 0.06, rate: 1, tone: -42, o: { style: 'castle' } },
      { paint: 'gantry',  src: 'mid',    h: 54, depth: 0.28, rate: 3, tone: -26, o: { decks: 3, gears: true } },
      { paint: 'gantry',  src: 'ground', h: 40, depth: 0.62, rate: 10, tone: -12, o: { decks: 2, gears: true } },
    ],
  },
  arena: {
    accent: METAL.fire, hue: 0.64, fog: '#2e2620',
    sky: ['#0a0806', '#171009', '#241a0e'], horizon: 'moon',
    anim: ['torch', 'ember'], occluder: 'banner', platform: 'sand',
    layers: [
      { paint: 'crowd',     src: 'far',    h: 46, depth: 0.08, rate: 0, tone: -40, o: { tiers: 3 } },
      { paint: 'crowd',     src: 'mid',    h: 40, depth: 0.26, rate: 0, tone: -24, o: { tiers: 2, banners: true } },
      { paint: 'colonnade', src: 'ground', h: 30, depth: 0.60, rate: 0, tone: -12, o: { pillarW: 8, gap: 26, top: 6 } },
    ],
  },
  castle: {
    accent: METAL.blood, hue: 0.68, fog: '#2a2026',
    sky: ['#070509', '#110a10', '#1b0f18'], horizon: 'glass',
    anim: ['torch', 'godray'], occluder: 'banner', platform: 'marble',
    layers: [
      { paint: 'wall',      src: 'far',    h: 62, depth: 0.07, rate: 0, tone: -44, o: { brick: 7, brickW: 20, stains: true } },
      { paint: 'colonnade', src: 'mid',    h: 54, depth: 0.28, rate: 2, tone: -28, o: { arch: true, pillarW: 12, gap: 24 } },
      { paint: 'skyline',   src: 'ground', h: 34, depth: 0.62, rate: 8, tone: -14, o: { style: 'castle', glow: true } },
    ],
  },
};

export const BIOME_KEYS = Object.freeze(Object.keys(BIOMES));

/* ================================================================
 * HORIZON TREATMENTS
 * ================================================================
 * Painted into the sky canvas at build time. The horizon is what tells the
 * player where they are before a single silhouette resolves, so each one is a
 * distinct shape rather than a tint: a disc, a slatted sun, a storm front, a
 * lava seam, a rose window, a rock vault, a fog bank.
 */

function stars(ctx, W, H, rand, colour, count) {
  for (let i = 0; i < count; i++) {
    const x = Math.round(rand() * W);
    const y = Math.round(rand() * H * 0.62);
    ctx.globalAlpha = 0.2 + rand() * 0.55;
    ctx.fillStyle = colour;
    ctx.fillRect(x, y, 1, 1);
    if (rand() < 0.08) {                                   // the odd bright one
      ctx.fillRect(x - 1, y, 3, 1);
      ctx.fillRect(x, y - 1, 1, 3);
    }
  }
  ctx.globalAlpha = 1;
}

function horizonMoon(ctx, W, H, rand, c) {
  stars(ctx, W, H, rand, c.bone, Math.round(W / 3));
  // Drawn where the light rig says the light is, not where it looked nice. The
  // source being visibly in the same place it is lighting from is free, and it
  // is the difference between a lit room and a room with a lamp drawn on it.
  const cx = Math.round(W * c.ux), cy = Math.round(H * c.uy), r = 11;
  for (let i = 4; i >= 1; i--) {                            // halo
    ctx.globalAlpha = 0.05 * i;
    blockEllipse(ctx, cx, cy, r + i * 5, r + i * 5, c.accent);
  }
  ctx.globalAlpha = 1;
  blockEllipse(ctx, cx, cy, r, r, c.bone);
  blockEllipse(ctx, cx + 2, cy + 2, r - 1, r - 1, shade(c.bone, -18), 0.5);
  // Craters, placed by hand-ish jitter so they never form a ring.
  for (let i = 0; i < 5; i++) {
    blockEllipse(ctx, cx + (rand() - 0.5) * r * 1.3, cy + (rand() - 0.5) * r * 1.3,
                 1 + Math.round(rand() * 2), 1 + Math.round(rand() * 2),
                 shade(c.bone, -34), 0.8);
  }
  blockEllipse(ctx, cx - 3, cy - 4, 4, 4, '#ffffff', 0.25);
}

function horizonSun(ctx, W, H, rand, c) {
  const cx = Math.round(W * c.ux), cy = H - 2, r = 26;
  for (let i = 5; i >= 1; i--) {
    ctx.globalAlpha = 0.07 * i;
    blockEllipse(ctx, cx, cy, r + i * 9, Math.round((r + i * 9) * 0.7), c.accent);
  }
  ctx.globalAlpha = 1;
  blockEllipse(ctx, cx, cy, r, r, c.accent);
  blockEllipse(ctx, cx, cy - 2, r - 6, r - 6, shade(c.accent, 34));
  // Slats. A disc cut by horizontal bars is the single most 1987 thing on the
  // stage, and it also reads as heat haze at this size.
  for (let y = cy - r - 8; y < cy; y += 4) {
    const dy = (cy - y) / r;
    const half = dy >= 1 ? 0 : Math.round(r * Math.sqrt(1 - dy * dy)) + 3;
    if (half <= 0) continue;
    ctx.clearRect(cx - half, y, half * 2, Math.max(1, Math.round(dy * 2)));
  }
}

function horizonStorm(ctx, W, H, rand, c) {
  stars(ctx, W, H, rand, c.bone, Math.round(W / 8));
  for (let band = 0; band < 4; band++) {
    const y = Math.round(H * (0.24 + band * 0.15));
    const tone = shade(c.cloud, -14 + band * 7);
    for (let x = -10; x < W + 10; x += 7) {
      const rx = 9 + Math.round(rand() * 16);
      const ry = 3 + Math.round(rand() * 4);
      blockEllipse(ctx, x + rand() * 6, y + (rand() - 0.5) * 5, rx, ry, tone, 0.9);
    }
    // Lit underside: the storm is lit from below by whatever is burning.
    for (let x = -10; x < W + 10; x += 11) {
      blockEllipse(ctx, x, y + 3 + rand() * 3, 7, 1, shade(c.cloud, 22), 0.4);
    }
  }
}

function horizonGlow(ctx, W, H, rand, c) {
  // A lava seam at the horizon, bleeding upward. Everything above it is smoke.
  for (let i = 6; i >= 1; i--) {
    ctx.globalAlpha = 0.06 * i;
    ctx.fillStyle = c.accent;
    ctx.fillRect(0, H - i * 7, W, i * 7);
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = c.accent;
  ctx.fillRect(0, H - 3, W, 3);
  ctx.fillStyle = shade(c.accent, 40);
  ctx.fillRect(0, H - 2, W, 1);
  for (let x = 0; x < W; x += 3) {                          // vents and crust
    if (rand() < 0.45) {
      const vh = 2 + Math.round(rand() * 7);
      ctx.fillStyle = shade(c.accent, -60);
      ctx.fillRect(x, H - 3 - vh, 2 + Math.round(rand() * 3), vh);
    }
  }
}

function horizonGlass(ctx, W, H, rand, c) {
  // A rose window. Lead lines are drawn as gaps, which is how real glass reads
  // at a distance: colour, black line, colour.
  const cx = Math.round(W * c.ux), cy = Math.round(H * c.uy), r = 30;
  const panes = [c.accent, shade(c.accent, -30), c.bone, METAL.blood, METAL.violet];
  for (let i = 5; i >= 1; i--) {
    ctx.globalAlpha = 0.028 * i;
    blockEllipse(ctx, cx, cy, r + i * 5, Math.round((r + i * 5) * 0.66), c.accent);
  }
  ctx.globalAlpha = 1;
  blockEllipse(ctx, cx, cy, r, r, shade(c.accent, -50));
  for (let ring = 3; ring >= 1; ring--) {
    const rr = Math.round(r * (ring / 3)) - 1;
    const seg = ring * 6;
    for (let s = 0; s < seg; s++) {
      const a0 = (s / seg) * 6.283;
      const px = cx + Math.cos(a0) * rr * 0.72;
      const py = cy + Math.sin(a0) * rr * 0.72;
      blockEllipse(ctx, px, py, Math.max(2, rr * 0.22), Math.max(2, rr * 0.22),
                   panes[(s + ring) % panes.length], 0.92);
    }
  }
  blockEllipse(ctx, cx, cy, 5, 5, c.bone);
  for (let s = 0; s < 12; s++) {                            // lead spokes
    const a0 = (s / 12) * 6.283;
    segment(ctx, cx + Math.cos(a0) * 5, cy + Math.sin(a0) * 5,
            cx + Math.cos(a0) * r, cy + Math.sin(a0) * r, 1, METAL.black);
  }
}

function horizonCeiling(ctx, W, H, rand, c) {
  // No sky at all: rock, with one crack of cold light so the frame has a top.
  ctx.fillStyle = c.rock;
  ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < W * 3; i++) {
    const x = Math.round(rand() * W), y = Math.round(rand() * H);
    ctx.fillStyle = shade(c.rock, rand() < 0.5 ? 12 : -14);
    ctx.fillRect(x, y, 1 + (rand() < 0.15 ? 1 : 0), 1);
  }
  let x = W * c.ux;                    // the crack is the source: put it there
  let y = 0;
  while (y < H * 0.8) {                                      // the crack
    const len = 3 + rand() * 6;
    const nx = x + (rand() - 0.5) * 12, ny = y + len;
    segment(ctx, x, y, nx, ny, 1, shade(c.accent, -10));
    segment(ctx, x + 1, y, nx + 1, ny, 1, shade(c.rock, -40));
    x = nx; y = ny;
  }
  for (let i = 5; i >= 1; i--) {                             // its bleed
    ctx.globalAlpha = 0.04 * i;
    blockEllipse(ctx, x, H * 0.4, 26 - i * 3, 40 - i * 4, c.accent);
  }
  ctx.globalAlpha = 1;
}

function horizonFogbank(ctx, W, H, rand, c) {
  stars(ctx, W, H, rand, c.bone, Math.round(W / 10));
  // A fog bank with nothing behind it is a grey field, and a room whose key
  // light has no visible source in frame reads as underexposed rather than as
  // atmospheric. So: a moon, diffused, drawn first and then buried in the bank.
  const mx = Math.round(W * c.ux), my = Math.round(H * c.uy);
  for (let i = 6; i >= 1; i--) {
    ctx.globalAlpha = 0.022 * i;
    blockEllipse(ctx, mx, my, 7 + i * 5, Math.round((7 + i * 5) * 0.78), c.accent);
  }
  ctx.globalAlpha = 0.42;
  blockEllipse(ctx, mx, my, 8, 8, mix(c.bone, c.accent, 0.45));
  ctx.globalAlpha = 0.34;
  blockEllipse(ctx, mx + 2, my + 2, 7, 7, c.fog);
  ctx.globalAlpha = 1;
  for (let band = 0; band < 7; band++) {
    const y = H - 4 - band * 5;
    ctx.globalAlpha = 0.1 + band * 0.035;
    ctx.fillStyle = c.fog;
    for (let x = -8; x < W + 8; x += 9) {
      blockEllipse(ctx, x + rand() * 8, y + (rand() - 0.5) * 3,
                   10 + rand() * 12, 2 + rand() * 2, c.fog);
    }
  }
  ctx.globalAlpha = 1;
}

const HORIZONS = {
  moon: horizonMoon, sun: horizonSun, storm: horizonStorm, glow: horizonGlow,
  glass: horizonGlass, ceiling: horizonCeiling, fogbank: horizonFogbank,
};

/* ================================================================
 * THE LIGHT RIG
 * ================================================================
 * ONE dominant source per room, and everything on the stage agrees with it.
 *
 * This is the highest-leverage thing a 2D stage can do and it costs almost
 * nothing. Two figures rimmed from opposite sides is the tell of a scene
 * assembled out of separately-drawn parts. Two figures rimmed from the SAME
 * side, with their cast shadows falling the other way, a pool of that same
 * colour on the deck between them and a shaft of it hanging in the air, reads
 * as a lit set. Nothing else here is more of what "expensive" means.
 *
 * So the rig is singular and it is published: scene.light carries the position,
 * the colour, the direction and the rim, and drawRimLight / drawFigureShadow
 * default to it rather than to whatever the caller felt like. A caller has to
 * go out of its way to break the agreement.
 *
 * Position comes from the horizon treatment, because the horizon is where the
 * source visibly is. The moon is high and to the right; the crack in a cave
 * roof is high and to the left; the lava seam is low and central. The colour
 * comes from the region accent, warmed or cooled by what kind of thing is
 * burning, so each realm is lit in its own hue without leaving the register.
 *
 *   ux, uy  apparent source, as a fraction of stage width / ground height
 *   warm    0 is moonlight, 1 is a furnace
 *   spread  how far the pool of it reaches across the deck
 *   flick   how much it gutters; 0 would be daylight and we have none
 *   shaft   how much of it hangs visibly in the air between camera and set
 */
const LIGHT = {
  moon:    { ux: 0.72, uy: 0.20, warm: 0.10, spread: 1.00, flick: 0.04, shaft: 0.34 },
  sun:     { ux: 0.54, uy: 0.74, warm: 0.92, spread: 1.26, flick: 0.06, shaft: 0.60 },
  storm:   { ux: 0.24, uy: 0.14, warm: 0.22, spread: 1.12, flick: 0.11, shaft: 0.24 },
  glow:    { ux: 0.54, uy: 0.94, warm: 1.00, spread: 1.18, flick: 0.18, shaft: 0.00 },
  glass:   { ux: 0.54, uy: 0.30, warm: 0.58, spread: 1.06, flick: 0.03, shaft: 0.86 },
  ceiling: { ux: 0.32, uy: 0.12, warm: 0.30, spread: 0.92, flick: 0.13, shaft: 0.72 },
  fogbank: { ux: 0.64, uy: 0.34, warm: 0.26, spread: 1.28, flick: 0.05, shaft: 0.44 },
};

function buildLightRig(spec, stage, accent, isBoss) {
  const L = LIGHT[spec.horizon] || LIGHT.moon;
  // Which side the light lives on. A boss slides the key further onto its own
  // shoulder but never across the centre line: swapping sides inside a region
  // would break the one thing this rig exists to hold together.
  const dir = L.ux >= 0.5 ? 1 : -1;
  const ux = clamp(L.ux + (isBoss ? dir * 0.05 : 0), 0.06, 0.94);
  const sx = Math.round(stage.w * ux);
  // The apparent source can sit anywhere, but the beam has to start far enough
  // above the deck to read as a beam rather than as a stain on the floor.
  const sy = Math.min(Math.round(stage.ground * L.uy) - 6, stage.ground - 56);
  // Where the light lands. Pulled back toward the middle of the fight, because
  // a key that lands outside the frame lights nothing the player is looking at.
  const x = Math.round(lerp(stage.w / 2, sx, 0.66)) + (isBoss ? dir * 6 : 0);
  const y = stage.ground - (isBoss ? 40 : 32);
  const colour = mix(accent, L.warm > 0.5 ? METAL.ember : METAL.chrome,
                     Math.abs(L.warm - 0.5) * 0.46);
  return {
    x, y, sx, sy, dir,
    warm: L.warm, spread: L.spread, flick: L.flick, shaft: L.shaft,
    colour,
    // The hot rim off the story bible: the key's own hue pushed toward bone.
    rim: mix(colour, METAL.bone, 0.36 + L.warm * 0.14),
    // The only other light in the room, and it is not a second key: it is this
    // one coming back off the deck, so it is dimmer, cooler and much lower.
    bounce: mix(shade(colour, -46), METAL.steel, 0.5),
  };
}

/* The visible beam. Four overlapping wedges from the source to the deck, each
 * quantised to four alpha steps. A smooth cone is a bloom shader; four steps is
 * a cartridge, and it is also what makes the dust inside it read as dust. */
function buildShaft(light, stage, seed) {
  const W = stage.w + PAD * 2;
  const H = stage.ground + PAD + 4;
  const s = surface(W, H);
  const ctx = s.ctx;
  const rand = rng((seed ^ 0x5417f00d) >>> 0);
  const oy = PAD + light.sy;
  const ty = PAD + stage.ground + 2;
  const span = Math.max(8, ty - oy);
  for (let b = 0; b < 4; b++) {
    const ap = 2 + rand() * 4;                     // half-width at the aperture
    const foot = 13 + rand() * 24;                 // half-width where it lands
    const lx = PAD + light.sx + (rand() - 0.5) * 11;
    const land = PAD + light.x + (rand() - 0.5) * 26;
    const peak = 0.09 + rand() * 0.11;
    for (let y = 0; y < span; y++) {
      const k = y / span;
      const q = Math.round(Math.pow(1 - k, 1.4) * 4) / 4;
      if (q <= 0) continue;
      const half = Math.max(1, Math.round(lerp(ap, foot, k)));
      const cxp = Math.round(lerp(lx, land, k));
      ctx.globalAlpha = peak * q;
      ctx.fillStyle = light.colour;
      ctx.fillRect(cxp - half, oy + y, half * 2, 1);
      if (half > 3) {
        ctx.globalAlpha = peak * q * 0.55;
        ctx.fillStyle = light.rim;
        const core = Math.max(1, Math.round(half * 0.5));
        ctx.fillRect(cxp - (core >> 1), oy + y, core, 1);
      }
    }
  }
  ctx.globalAlpha = 1;
  return s.canvas;
}

/* ---------------- sky ----------------
 * Banded in whole rows. A smooth vertical gradient is the tell of a CSS
 * backdrop; ten hard bands is the tell of a cartridge. */
function buildSky(spec, tint, seed, W, H, boss) {
  const s = surface(W, H);
  const rand = rng(seed ^ 0x5eed);
  const top = mix(spec.sky[0], tint, 0.1);
  const midC = mix(spec.sky[1], tint, 0.16);
  const low = mix(spec.sky[2], tint, 0.2);
  const bands = 11;
  for (let i = 0; i < bands; i++) {
    const k = i / (bands - 1);
    const colour = k < 0.5 ? mix(top, midC, k * 2) : mix(midC, low, (k - 0.5) * 2);
    s.ctx.fillStyle = boss ? shade(colour, -16) : colour;
    const y0 = Math.round((i / bands) * H);
    const y1 = Math.round(((i + 1) / bands) * H);
    s.ctx.fillRect(0, y0, W, y1 - y0);
    // One row of ordered dither on each seam. It costs nothing and it is the
    // difference between eleven bands and eleven stripes.
    s.ctx.fillStyle = k < 0.5 ? mix(top, midC, Math.min(1, k * 2 + 0.12))
                              : mix(midC, low, Math.min(1, (k - 0.5) * 2 + 0.12));
    for (let x = (i % 2); x < W; x += 2) s.ctx.fillRect(x, y1 - 1, 1, 1);
  }
  const paint = HORIZONS[spec.horizon] || horizonMoon;
  const lr = LIGHT[spec.horizon] || LIGHT.moon;
  paint(s.ctx, W, H, rand, {
    accent: spec.accent,
    bone: METAL.bone,
    fog: spec.fog,
    cloud: mix(spec.sky[1], METAL.steel, 0.4),
    rock: mix(spec.sky[2], METAL.gun, 0.5),
    // Where the one light lives, so the disc, the seam, the window and the
    // crack are all drawn at the same place the stage is lit from.
    ux: lr.ux, uy: clamp(lr.uy, 0.08, 0.62),
  });
  return s.canvas;
}

/* ================================================================
 * THE PLATFORM
 * ================================================================
 * The combatants stand on a slab, not on the horizon line. It has a top plane
 * that bows away from the viewer, a lit front lip, a chiselled face and a drop
 * into darkness underneath with the slab's own shadow cast on it. That drop is
 * what makes the fight read as staged and elevated rather than as two sprites
 * standing in a field.
 */
const PLATFORM_TOP = 12;   // rows of the canvas above the standing line

function bow(x, W, amount) {
  const u = (x / (W - 1)) * 2 - 1;
  const k = 1 - u * u;
  return k <= 0 ? 0 : Math.round(amount * k);
}

function buildPlatform(kind, c, seed, stage, boss) {
  const W = stage.w + PAD * 2;
  const H = stage.h - (stage.ground - PLATFORM_TOP) + PAD;
  const s = surface(W, H);
  const ctx = s.ctx;
  const rand = rng(seed ^ 0x9a11);
  const stand = PLATFORM_TOP;                    // local y of the standing line

  for (let x = 0; x < W; x++) {
    const xs = x - PAD;
    const backY = stand - 7 - bow(xs, stage.w, 3);
    const lipY = stand + 3 + bow(xs, stage.w, 3);
    // Top plane: darkest at the back, so the figures' feet sit on a lit strip.
    for (let y = backY; y <= lipY; y++) {
      const k = (y - backY) / Math.max(1, lipY - backY);
      ctx.fillStyle = mix(c.deck, c.deckLight, k * 0.85);
      ctx.fillRect(x, y, 1, 1);
    }
    ctx.fillStyle = c.deckBack;                  // the shaded seam at the back
    ctx.fillRect(x, backY, 1, 2);
    ctx.fillStyle = c.lip;                       // the lit front lip
    ctx.fillRect(x, lipY, 1, 1);
    ctx.fillStyle = c.faceTop;
    ctx.fillRect(x, lipY + 1, 1, 2);
    for (let y = lipY + 3; y < lipY + 17; y++) { // the face, falling off fast
      const k = (y - lipY - 3) / 14;
      ctx.fillStyle = mix(c.face, METAL.black, Math.pow(k, 0.8));
      ctx.fillRect(x, y, 1, 1);
    }
    // Not quite black: a dead rectangle under the slab reads as a crop, and a
    // hint of the deck's own colour down there reads as depth under it.
    ctx.fillStyle = mix(METAL.black, c.face, 0.14);
    ctx.fillRect(x, lipY + 17, 1, H - lipY - 17);
  }

  // Chisel grooves on the face. Irregular spacing, because an even comb reads
  // as a fence rather than as cut stone.
  for (let x = 2; x < W; x += 5 + Math.round(rand() * 7)) {
    const xs = x - PAD;
    const lipY = stand + 3 + bow(xs, stage.w, 3);
    const gh = 6 + Math.round(rand() * 8);
    ctx.globalAlpha = 0.5;
    ctx.fillStyle = METAL.black;
    ctx.fillRect(x, lipY + 2, 1, gh);
    ctx.fillStyle = c.lip;
    ctx.fillRect(x + 1, lipY + 2, 1, Math.round(gh * 0.6));
    ctx.globalAlpha = 1;
  }

  // Surface treatment. The deck is the one surface the player stares at for a
  // whole fight, so each biome family gets its own.
  if (kind === 'flag' || kind === 'stone' || kind === 'marble') {
    for (let x = 4; x < W; x += 17 + Math.round(rand() * 7)) {
      const xs = x - PAD;
      const backY = stand - 7 - bow(xs, stage.w, 3);
      const lipY = stand + 3 + bow(xs, stage.w, 3);
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = c.joint;
      ctx.fillRect(x, backY + 2, 1, lipY - backY - 1);
      ctx.globalAlpha = 1;
    }
    ctx.globalAlpha = 0.4;
    ctx.fillStyle = c.joint;
    ctx.fillRect(0, stand - 2, W, 1);
    ctx.globalAlpha = 1;
    if (kind === 'marble') {
      for (let i = 0; i < 14; i++) {             // veins
        let x = rand() * W, y = stand - 6 + rand() * 8;
        for (let k = 0; k < 10; k++) {
          const nx = x + (rand() - 0.3) * 9, ny = y + (rand() - 0.5) * 2;
          ctx.globalAlpha = 0.3;
          segment(ctx, x, y, nx, ny, 1, c.lip);
          x = nx; y = ny;
        }
      }
      ctx.globalAlpha = 1;
    }
  } else if (kind === 'cobble') {
    for (let i = 0; i < 260; i++) {
      const x = Math.round(rand() * W), y = stand - 7 + Math.round(rand() * 10);
      blockEllipse(ctx, x, y, 1 + Math.round(rand() * 1), 1, rand() < 0.5 ? c.lip : c.joint, 0.6);
    }
  } else if (kind === 'sand' || kind === 'ash') {
    for (let i = 0; i < 420; i++) {
      const x = Math.round(rand() * W), y = stand - 7 + Math.round(rand() * 11);
      ctx.globalAlpha = 0.35 + rand() * 0.4;
      ctx.fillStyle = rand() < 0.5 ? c.lip : c.joint;
      ctx.fillRect(x, y, 1, 1);
    }
    ctx.globalAlpha = 0.25;
    for (let i = 0; i < 9; i++) {                // drag ripples
      const y = stand - 6 + Math.round(rand() * 9);
      ctx.fillStyle = c.joint;
      for (let x = Math.round(rand() * W), n = 0; n < 40; n++, x++) {
        ctx.fillRect(x % W, y + Math.round(Math.sin(x * 0.2) * 1), 1, 1);
      }
    }
    ctx.globalAlpha = 1;
  } else if (kind === 'plank' || kind === 'iron' || kind === 'branch' || kind === 'root') {
    for (let x = 0; x < W; x += kind === 'iron' ? 24 : 13) {
      ctx.globalAlpha = 0.5;
      ctx.fillStyle = c.joint;
      ctx.fillRect(x, stand - 7, 1, 11);
      ctx.globalAlpha = 1;
      if (kind === 'iron') {                     // rivets
        for (let y = stand - 5; y < stand + 4; y += 4) {
          ctx.fillStyle = c.lip;
          ctx.fillRect(x + 2, y, 1, 1);
          ctx.fillStyle = c.joint;
          ctx.fillRect(x + 2, y + 1, 1, 1);
        }
      }
    }
    if (kind !== 'iron') {                       // grain
      ctx.globalAlpha = 0.3;
      for (let i = 0; i < 40; i++) {
        const y = stand - 6 + Math.round(rand() * 9);
        ctx.fillStyle = c.joint;
        ctx.fillRect(Math.round(rand() * W), y, 4 + Math.round(rand() * 10), 1);
      }
      ctx.globalAlpha = 1;
    }
  } else if (kind === 'sod') {
    for (let x = 0; x < W; x += 2) {             // blades along the lip
      const xs = x - PAD;
      const lipY = stand + 3 + bow(xs, stage.w, 3);
      const bh = 1 + Math.round(rand() * 3);
      ctx.fillStyle = rand() < 0.4 ? c.lip : c.joint;
      ctx.fillRect(x, lipY - bh, 1, bh + 1);
    }
  } else if (kind === 'bog') {
    for (let i = 0; i < 7; i++) {                // standing water
      const x = Math.round(rand() * W), y = stand - 4 + Math.round(rand() * 6);
      const rx = 5 + Math.round(rand() * 9);
      blockEllipse(ctx, x, y, rx, 2, METAL.black, 0.7);
      blockEllipse(ctx, x, y - 1, rx - 2, 1, c.lip, 0.35);
    }
  }

  // Cracks. Every arena in this game has been fought in before.
  for (let i = 0; i < (boss ? 7 : 4); i++) {
    let x = rand() * W, y = stand - 5 + rand() * 8;
    ctx.globalAlpha = 0.55;
    for (let k = 0; k < 5; k++) {
      const nx = x + (rand() - 0.5) * 14, ny = y + (rand() - 0.5) * 3;
      segment(ctx, x, y, nx, ny, 1, METAL.black);
      x = nx; y = ny;
    }
    ctx.globalAlpha = 1;
  }

  // The slab's cast shadow on whatever is below it, plus a bounce of the key
  // light on the underside of the lip so the edge does not read as a cut-out.
  const shadowTop = stand + 20;
  for (let i = 0; i < 10; i++) {
    ctx.globalAlpha = 0.1;
    blockEllipse(ctx, W / 2, shadowTop + 6 + i, Math.round(W * 0.46) - i * 3,
                 3 + i, METAL.black);
  }
  ctx.globalAlpha = 0.18;
  ctx.fillStyle = c.lip;
  ctx.fillRect(PAD, stand + 6, stage.w, 1);
  ctx.globalAlpha = 1;
  return s.canvas;
}

/* The boss floor sigil. Two rings, twelve abstract glyphs and four spokes. The
 * glyphs are generated from a seeded bit pattern, so they are not any script
 * that exists — they only have to look like a language. */
function buildSigil(colour, seed, stage) {
  const W = stage.w;
  const H = 34;
  const s = surface(W, H);
  const ctx = s.ctx;
  const rand = rng(seed ^ 0x5163);
  const cx = W / 2, cy = H / 2;
  const rx = Math.round(W * 0.32), ry = Math.round(H * 0.4);

  const ring = (fx, fy, alpha, col) => {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = col;
    for (let a = 0; a < 360; a += 2) {
      const r = (a * Math.PI) / 180;
      ctx.fillRect(Math.round(cx + Math.cos(r) * fx), Math.round(cy + Math.sin(r) * fy), 1, 1);
    }
    ctx.globalAlpha = 1;
  };
  ring(rx, ry, 0.9, colour);
  ring(rx - 4, ry - 2, 0.45, colour);
  ring(Math.round(rx * 0.42), Math.round(ry * 0.42), 0.7, shade(colour, 30));

  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * 6.283;
    const gx = Math.round(cx + Math.cos(a) * (rx - 2));
    const gy = Math.round(cy + Math.sin(a) * (ry - 1));
    const bits = (rand() * 0xffff) | 0;
    ctx.fillStyle = colour;
    for (let b = 0; b < 12; b++) {
      if (!((bits >> b) & 1)) continue;
      ctx.fillRect(gx - 1 + (b % 3), gy - 2 + Math.floor(b / 3), 1, 1);
    }
  }
  for (let i = 0; i < 4; i++) {                  // spokes
    const a = (i / 4) * 6.283 + 0.4;
    segment(ctx, cx + Math.cos(a) * rx * 0.45, cy + Math.sin(a) * ry * 0.45,
            cx + Math.cos(a) * rx * 0.92, cy + Math.sin(a) * ry * 0.92, 1,
            shade(colour, 20));
  }
  return s.canvas;
}

/* A brazier: tripod, bowl, coals. The flame is drawn live on top of it. */
function buildBrazier(c) {
  const s = surface(15, 24);
  const ctx = s.ctx;
  const iron = c.iron, lit = c.lit;
  ctx.fillStyle = iron;
  ctx.fillRect(6, 8, 3, 12);                      // stem
  ctx.fillStyle = shade(iron, 22);
  ctx.fillRect(6, 8, 1, 12);
  segment(ctx, 7, 18, 2, 23, 1, iron);            // legs
  segment(ctx, 7, 18, 12, 23, 1, iron);
  segment(ctx, 7, 18, 7, 23, 1, shade(iron, -20));
  ctx.fillStyle = iron;                           // bowl
  for (let y = 0; y < 6; y++) {
    const w = 15 - y * 2;
    ctx.fillRect(Math.round((15 - w) / 2), 4 + y, w, 1);
  }
  ctx.fillStyle = shade(iron, 26);
  ctx.fillRect(0, 4, 15, 1);
  ctx.fillStyle = shade(iron, -26);
  ctx.fillRect(1, 8, 13, 1);
  ctx.fillStyle = lit;                            // coals
  ctx.fillRect(3, 3, 9, 2);
  ctx.fillStyle = shade(lit, 36);
  ctx.fillRect(5, 3, 5, 1);
  return s.canvas;
}

/* ================================================================
 * FOREGROUND OCCLUDERS
 * ================================================================
 * Something solid and near-black at each edge of the frame, moving faster than
 * anything behind it. It costs almost nothing and it is the single strongest
 * depth cue on the stage: the fight is happening *inside* a place, past the
 * pillar the camera is standing behind.
 */
const OCC_W = PAD + 40;

function buildOccluder(kind, c, seed, stage) {
  const H = stage.h + PAD * 2;
  const s = surface(OCC_W, H);
  const ctx = s.ctx;
  const rand = rng(seed);
  const dark = c.dark, rim = c.rim, mid = c.mid;

  if (kind === 'pillar') {
    const w = 26;
    ctx.fillStyle = dark;
    ctx.fillRect(0, 0, w, H);
    ctx.fillStyle = mid;
    ctx.fillRect(w - 3, 0, 3, H);
    ctx.fillStyle = rim;
    ctx.fillRect(w - 1, 0, 1, H);
    for (let f = 5; f < w - 5; f += 6) {
      ctx.fillStyle = METAL.black;
      ctx.fillRect(f, 0, 2, H);
    }
    ctx.fillStyle = mid;                                   // capital and base
    ctx.fillRect(0, PAD + 6, w + 6, 8);
    ctx.fillRect(0, H - PAD - 22, w + 5, 10);
    ctx.fillStyle = rim;
    ctx.fillRect(0, PAD + 6, w + 6, 1);
    ctx.fillRect(0, H - PAD - 22, w + 5, 1);
  } else if (kind === 'chain') {
    for (let n = 0; n < 3; n++) {
      const x = 6 + n * 13 + Math.round(rand() * 4);
      const len = Math.round(H * (0.35 + rand() * 0.45));
      ctx.fillStyle = mid;
      ctx.fillRect(x - 4, 0, 12, 5);                       // the beam it hangs from
      ctx.fillStyle = rim;
      ctx.fillRect(x - 4, 0, 12, 1);
      for (let y = 5; y < len; y += 6) {
        const wide = ((y / 6) | 0) % 2 === 0;
        ctx.fillStyle = dark;
        ctx.fillRect(x - (wide ? 3 : 1), y, wide ? 6 : 3, 6);
        ctx.fillStyle = METAL.black;
        ctx.fillRect(x - (wide ? 1 : 0), y + 2, wide ? 2 : 1, 2);
        ctx.fillStyle = rim;
        ctx.fillRect(x - (wide ? 3 : 1), y, 1, 5);
      }
      ctx.fillStyle = dark;                                 // manacle at the end
      ctx.fillRect(x - 5, len, 10, 4);
      ctx.fillStyle = rim;
      ctx.fillRect(x - 5, len, 10, 1);
    }
  } else if (kind === 'banner') {
    const x = 6, w = 26;
    const len = Math.round(H * (0.52 + rand() * 0.2));
    ctx.fillStyle = mid;                                    // rail
    ctx.fillRect(0, PAD, w + 12, 4);
    ctx.fillStyle = rim;
    ctx.fillRect(0, PAD, w + 12, 1);
    ctx.fillStyle = dark;
    ctx.fillRect(x, PAD + 4, w, len);
    ctx.fillStyle = mid;                                    // fold catching light
    ctx.fillRect(x, PAD + 4, 4, len);
    ctx.fillStyle = METAL.black;
    ctx.fillRect(x + w - 5, PAD + 4, 5, len);
    ctx.fillStyle = rim;                                    // vertical trim
    ctx.fillRect(x + 1, PAD + 4, 1, len);
    ctx.fillRect(x + w - 2, PAD + 4, 1, len);
    const dy = PAD + 24;                                    // a device, abstract
    ctx.fillStyle = rim;
    ctx.fillRect(x + 8, dy, 10, 2);
    ctx.fillRect(x + 12, dy, 2, 14);
    ctx.fillRect(x + 7, dy + 14, 12, 2);
    ctx.fillRect(x + 9, dy + 5, 2, 6);
    ctx.fillRect(x + 15, dy + 5, 2, 6);
    for (let i = 0; i < w; i += 6) {                        // torn hem
      const cut = 3 + Math.round(rand() * 6);
      ctx.clearRect(x + i, PAD + 4 + len - cut, 4, cut);
    }
  } else if (kind === 'branch') {
    let bx = -2, by = PAD + 4;
    ctx.fillStyle = dark;
    for (let i = 0; i < 44; i++) {                          // the limb, sagging
      const t = i / 44;
      bx += 1;
      by += t * 1.1;
      ctx.fillRect(Math.round(bx), Math.round(by), 1, Math.round(9 - t * 5));
      if (i % 9 === 0) {                                    // twig
        segment(ctx, bx, by, bx + 4 + rand() * 6, by - 6 - rand() * 8, 1, dark);
      }
    }
    for (let i = 0; i < 26; i++) {                          // leaf mass
      const lx = 2 + rand() * (OCC_W - 6);
      const ly = PAD + 2 + rand() * 30;
      blockEllipse(ctx, lx, ly, 3 + rand() * 4, 2 + rand() * 3, dark, 0.95);
      blockEllipse(ctx, lx - 1, ly - 1, 2, 1, mid, 0.5);
    }
    ctx.fillStyle = rim;
    ctx.fillRect(0, PAD + 4, 30, 1);
  } else if (kind === 'reed') {
    for (let x = 0; x < OCC_W; x += 2) {
      const rh = Math.round(H * (0.16 + rand() * 0.34) * (1 - x / (OCC_W * 1.6)));
      const lean = (rand() - 0.5) * 6;
      for (let y = 0; y < rh; y++) {
        const k = y / Math.max(1, rh);
        ctx.fillStyle = k > 0.88 ? rim : dark;
        ctx.fillRect(Math.round(x + lean * k * k), H - PAD - y, 1, 1);
      }
    }
  } else if (kind === 'bone') {
    const base = H - PAD;
    for (let i = 0; i < 9; i++) {                           // long bones
      const x = rand() * (OCC_W - 8), y = base - 4 - rand() * 26;
      const len = 8 + rand() * 16, lean = (rand() - 0.5) * 10;
      segment(ctx, x, y, x + len, y + lean, 3, dark);
      segment(ctx, x, y, x + len, y + lean, 1, mid);
      ctx.fillStyle = dark;
      ctx.fillRect(Math.round(x) - 1, Math.round(y) - 2, 4, 5);
      ctx.fillRect(Math.round(x + len) - 1, Math.round(y + lean) - 2, 4, 5);
    }
    for (let i = 0; i < 5; i++) {                           // ribs
      const x = 4 + rand() * 20, y = base - 30 - rand() * 20;
      for (let k = 0; k < 14; k++) {
        ctx.fillStyle = dark;
        ctx.fillRect(Math.round(x + Math.sin(k * 0.22) * 10), Math.round(y + k * 2), 2, 2);
      }
    }
    const sx = 6 + rand() * 14, sy = base - 12;             // a skull, half sunk
    blockEllipse(ctx, sx, sy, 7, 6, dark);
    blockEllipse(ctx, sx, sy - 1, 6, 4, mid, 0.5);
    ctx.fillStyle = METAL.black;
    ctx.fillRect(Math.round(sx) - 4, Math.round(sy) - 2, 3, 3);
    ctx.fillRect(Math.round(sx) + 1, Math.round(sy) - 2, 3, 3);
    ctx.fillStyle = rim;
    ctx.fillRect(Math.round(sx) - 4, Math.round(sy) - 2, 1, 1);
  } else if (kind === 'stalagmite') {
    for (let n = 0; n < 5; n++) {
      const x = rand() * OCC_W;
      const down = n % 2 === 0;
      const th = Math.round(H * (0.2 + rand() * 0.4));
      const tw = 6 + Math.round(rand() * 9);
      for (let i = 0; i < th; i++) {
        const k = i / th;
        const cw = Math.max(1, Math.round(tw * (1 - k * k)));
        const y = down ? i : H - 1 - i;
        ctx.fillStyle = dark;
        ctx.fillRect(Math.round(x - cw / 2), y, cw, 1);
        ctx.fillStyle = mid;
        ctx.fillRect(Math.round(x - cw / 2), y, 1, 1);
      }
    }
  } else {                                                   // 'stone' outcrop
    const base = H - PAD;
    for (let n = 0; n < 4; n++) {
      const x = rand() * (OCC_W - 10);
      const w = 12 + rand() * 22, h = 24 + rand() * 52;
      for (let y = 0; y < h; y++) {
        const k = y / h;
        const cw = Math.round(w * (0.35 + k * 0.75));
        ctx.fillStyle = dark;
        ctx.fillRect(Math.round(x - cw * 0.3), base - h + y, cw, 1);
        ctx.fillStyle = mid;
        ctx.fillRect(Math.round(x - cw * 0.3), base - h + y, 1, 1);
      }
      ctx.fillStyle = rim;
      ctx.fillRect(Math.round(x - w * 0.3), base - h, Math.round(w * 0.5), 1);
    }
  }
  return s.canvas;
}

/* A wall bracket for a torch, painted onto the occluder so the flame has
 * something to sit in. Returns the flame anchor in occluder-local coords. */
function addTorchBracket(canvas, c, x, y) {
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = c.mid;
  ctx.fillRect(x - 1, y + 4, 3, 9);
  ctx.fillStyle = c.dark;
  ctx.fillRect(x + 2, y + 4, 1, 9);
  for (let i = 0; i < 4; i++) {                              // flared cup
    ctx.fillStyle = i < 2 ? c.mid : c.dark;
    ctx.fillRect(x - 2 - i, y + i, 5 + i * 2, 1);
  }
  ctx.fillStyle = c.rim;
  ctx.fillRect(x - 5, y, 11, 1);
  return { x, y: y - 1 };
}

/* ================================================================
 * THE APRON
 * ================================================================
 * The fourth depth: a strip of ground between the camera and the platform,
 * drawn in front of the combatants, moving faster than anything else in the
 * frame. Far, mid, near, and then this.
 *
 * It is the cheapest way to say "you are standing in this room, looking across
 * it". The occluders frame the fight from the sides; the apron puts something
 * under the camera's own feet. It is near-black, because it is the closest
 * thing to the lens and nothing that close is lit — except its crest, which
 * takes one pixel of the key like everything else on the stage does.
 *
 * Its tall elements are kept to the outer thirty pixels of the frame. A tuft of
 * grass through the middle of a sword swing is not staging, it is an obstacle.
 */
const APRON_OFF = 20;      // slack either side, so parallax cannot show an edge
const APRON_LIFT = 2;      // rows above the standing line the crest may reach

function buildApron(kind, c, seed, stage) {
  const W = stage.w + PAD * 2 + APRON_OFF * 2;
  const H = Math.max(10, stage.h + PAD - (stage.ground - APRON_LIFT));
  const s = surface(W, H);
  const ctx = s.ctx;
  const rand = rng((seed ^ 0x4a27b19d) >>> 0);
  const edgeOf = (x) => {
    const xs = x - PAD - APRON_OFF;
    return xs < 34 || xs > stage.w - 28;
  };

  // The crest: two sines and a hash jitter, so the near edge is a ragged line
  // rather than a ruled one. A straight foreground edge reads as a letterbox.
  const crest = new Int16Array(W);
  for (let x = 0; x < W; x++) {
    const u = (x / W) * 6.283;
    // Sixteen rows down, which puts the near edge just below the platform's
    // front lip: low enough to leave the chiselled face visible, high enough
    // that the tall pieces at the frame edges can reach the standing line.
    crest[x] = Math.max(6, Math.round(
      16 + Math.sin(u * 3.1 + 0.6) * 3.4 + Math.sin(u * 7.7 + 2.2) * 1.8 + ((x * 37) % 3)));
  }
  for (let x = 0; x < W; x++) {
    const top = crest[x];
    ctx.fillStyle = c.body;
    ctx.fillRect(x, top, 1, H - top);
    ctx.fillStyle = c.mid;                       // one row of turned-up face
    ctx.fillRect(x, top + 1, 1, 2);
    ctx.fillStyle = c.rim;                       // the one lit pixel: the crest
    ctx.fillRect(x, top, 1, 1);
  }

  // Scatter across the whole width, but low enough to stay under a knee.
  for (let x = 2; x < W; x += 2 + Math.round(rand() * 3)) {
    const top = crest[x];
    const h = 1 + Math.round(rand() * (kind === 'blade' ? 4 : 2));
    if (kind === 'blade') {
      const lean = (rand() - 0.5) * 3;
      for (let i = 0; i < h; i++) {
        ctx.fillStyle = i === h - 1 ? c.rim : c.body;
        ctx.fillRect(Math.round(x + lean * (i / Math.max(1, h))), top - i, 1, 1);
      }
    } else if (kind === 'plank') {
      ctx.fillStyle = c.body;
      ctx.fillRect(x, top - h, 3, h + 2);
      ctx.fillStyle = c.rim;
      ctx.fillRect(x, top - h, 3, 1);
    } else {
      const w = 2 + Math.round(rand() * 3);
      ctx.fillStyle = c.body;
      ctx.fillRect(x, top - h, w, h + 2);
      ctx.fillStyle = c.mid;
      ctx.fillRect(x, top - h, 1, h + 1);
      ctx.fillStyle = c.rim;
      ctx.fillRect(x, top - h, w, 1);
    }
  }

  // The tall pieces, out at the edges where they frame rather than obstruct.
  for (let x = 1; x < W; x += 9 + Math.round(rand() * 13)) {
    if (!edgeOf(x)) continue;
    const top = crest[x];
    // Capped by the crest itself, so nothing can be driven up past row 0 and
    // pile into a solid bar along the top of the strip.
    const th = Math.min(top - 1, 9 + Math.round(rand() * 11));
    if (th < 4) continue;
    if (kind === 'blade') {
      const blades = 3 + Math.round(rand() * 4);
      for (let b = 0; b < blades; b++) {
        const bx = x + b - (blades >> 1);
        const bh = Math.round(th * (0.45 + rand() * 0.55));
        const lean = (rand() - 0.5) * 7;
        for (let i = 0; i < bh; i++) {
          const k = i / Math.max(1, bh);
          ctx.fillStyle = k > 0.82 ? c.rim : (k > 0.5 ? c.mid : c.body);
          ctx.fillRect(Math.round(bx + lean * k * k), Math.max(0, top - i), 1, 1);
        }
      }
    } else if (kind === 'plank') {
      const w = 4 + Math.round(rand() * 4);
      ctx.fillStyle = c.body;
      ctx.fillRect(x, Math.max(0, top - th), w, th + 3);
      ctx.fillStyle = c.mid;
      ctx.fillRect(x, Math.max(0, top - th), 1, th + 2);
      ctx.fillStyle = c.rim;
      ctx.fillRect(x, Math.max(0, top - th), w, 1);
      for (let y = top - th + 3; y < top; y += 5) {   // bolt heads
        ctx.fillStyle = c.rim;
        ctx.fillRect(x + 2, Math.max(0, y), 1, 1);
      }
    } else {
      // A broken block: wider at the base, one chipped shoulder, lit crown.
      const w = 5 + Math.round(rand() * 6);
      for (let i = 0; i < th; i++) {
        const k = i / th;
        const cw = Math.max(2, Math.round(w * (1 - k * 0.4)));
        ctx.fillStyle = c.body;
        ctx.fillRect(x, Math.max(0, top - i), cw, 1);
        ctx.fillStyle = c.mid;
        ctx.fillRect(x, Math.max(0, top - i), 1, 1);
      }
      ctx.fillStyle = c.rim;
      ctx.fillRect(x, Math.max(0, top - th), Math.max(2, w - 2), 1);
      if (rand() < 0.5) {
        ctx.clearRect(x + w - 3, Math.max(0, top - th), 3, 2 + Math.round(rand() * 3));
      }
    }
  }
  return s.canvas;
}

function apronKind(platform) {
  if (platform === 'sod' || platform === 'bog' || platform === 'root'
      || platform === 'branch') return 'blade';
  if (platform === 'plank' || platform === 'iron') return 'plank';
  return 'rubble';
}

function mirrorCanvas(src) {
  const s = surface(src.width, src.height);
  s.ctx.translate(src.width, 0);
  s.ctx.scale(-1, 1);
  s.ctx.drawImage(src, 0, 0);
  return s.canvas;
}

/* ---------------- volumetrics ---------------- */

function buildFogBand(colour, seed, W, H) {
  const s = surface(W, H);
  const rand = rng(seed);
  for (let i = 0; i < Math.round(W / 4); i++) {
    const x = rand() * W, y = rand() * H;
    const rx = 8 + rand() * 26, ry = 2 + rand() * 5;
    s.ctx.globalAlpha = 0.06 + rand() * 0.1;
    blockEllipse(s.ctx, x, y, rx, ry, colour);
    // Wrap the blob so the band tiles.
    if (x + rx > W) blockEllipse(s.ctx, x - W, y, rx, ry, colour);
    if (x - rx < 0) blockEllipse(s.ctx, x + W, y, rx, ry, colour);
  }
  s.ctx.globalAlpha = 1;
  return s.canvas;
}

function buildGodrays(colour, seed, W, H) {
  const s = surface(W, H);
  const rand = rng(seed ^ 0x7a11);
  for (let i = 0; i < 6; i++) {
    const x0 = rand() * W;
    const w = 5 + rand() * 13;
    const lean = 18 + rand() * 16;
    for (let y = 0; y < H; y++) {
      const k = y / H;
      s.ctx.globalAlpha = 0.05 * (1 - k) + 0.012;
      s.ctx.fillStyle = colour;
      s.ctx.fillRect(Math.round(x0 + lean * k), y, Math.round(w * (1 + k * 0.6)), 1);
    }
  }
  s.ctx.globalAlpha = 1;
  return s.canvas;
}

/* Darkness falling off toward the frame. Painted as black, then punched out of
 * the middle, which is far cheaper than evaluating a falloff per pixel. */
function buildVignette(W, H, strength, tint) {
  const s = surface(W, H);
  s.ctx.fillStyle = tint || METAL.black;
  s.ctx.fillRect(0, 0, W, H);
  s.ctx.globalCompositeOperation = 'destination-out';
  const steps = 11;
  // A boss stage passes a higher strength, which erases less of the middle and
  // so leaves more black in the corners. Same bitmap, darker room.
  const erase = clamp(0.40 - (strength - 1) * 0.1, 0.14, 0.5);
  for (let i = steps; i >= 1; i--) {
    const k = i / steps;
    s.ctx.globalAlpha = erase;
    blockEllipse(s.ctx, W / 2, H * 0.52, Math.round(W * 0.62 * k),
                 Math.round(H * 0.72 * k), '#ffffff');
  }
  s.ctx.globalCompositeOperation = 'source-over';
  s.ctx.globalAlpha = 1;
  // The corners get an extra bite: a rectangular frame reads as a screen edge,
  // an elliptical one reads as a lens, and the second is what we want.
  return s.canvas;
}

/* ================================================================
 * ANIMATED ELEMENTS
 * ================================================================
 * Every one of these is analytic: position is a pure function of `time`, so
 * there is no update pass, no per-frame state and no allocation. It also means
 * two stages built from the same key and fed the same clock are pixel
 * identical, which is what makes the harness able to check anything at all.
 */

/* x, y, speed, phase, roll — five floats per mote, in one flat array. */
function buildMotes(seed, count, W, H) {
  const rand = rng(seed);
  const a = new Float32Array(count * 5);
  for (let i = 0; i < count; i++) {
    a[i * 5 + 0] = rand() * W;
    a[i * 5 + 1] = rand() * H;
    a[i * 5 + 2] = 0.35 + rand() * 1.7;
    a[i * 5 + 3] = rand() * 6.283;
    a[i * 5 + 4] = rand();
  }
  return a;
}

function drawMotes(ctx, a, t, o) {
  const W = o.w, H = o.h, dir = o.dir || 1, speed = o.speed || 8;
  const sway = o.sway === undefined ? 3 : o.sway;
  ctx.globalAlpha = o.alpha === undefined ? 0.5 : o.alpha;
  ctx.fillStyle = o.colour;
  for (let i = 0; i < a.length; i += 5) {
    let y = a[i + 1] + dir * t * speed * a[i + 2];
    y = ((y % H) + H) % H;
    let x = a[i] + Math.sin(t * 0.8 * a[i + 2] + a[i + 3]) * sway;
    x = ((x % W) + W) % W;
    const big = a[i + 4] > 0.82 ? 1 : 0;
    ctx.fillRect((x | 0) + o.x0, (y | 0) + o.y0, o.size + big,
                 (o.streak ? o.size * 3 : o.size) + big);
  }
  ctx.globalAlpha = 1;
}

/* Fireflies and wisps: they orbit rather than fall, and they pulse. */
function drawWisps(ctx, a, t, o) {
  ctx.fillStyle = o.colour;
  for (let i = 0; i < a.length; i += 5) {
    const ph = a[i + 3];
    const x = a[i] + Math.sin(t * 0.6 * a[i + 2] + ph) * 9;
    const y = a[i + 1] + Math.cos(t * 0.43 * a[i + 2] + ph * 1.7) * 6;
    const pulse = 0.3 + 0.7 * Math.max(0, Math.sin(t * 2.2 + ph * 3));
    ctx.globalAlpha = (o.alpha || 0.8) * pulse;
    ctx.fillRect(Math.round(x), Math.round(y), 1, 1);
    if (pulse > 0.8) {
      ctx.globalAlpha = (o.alpha || 0.8) * 0.3;
      ctx.fillRect(Math.round(x) - 1, Math.round(y), 3, 1);
      ctx.fillRect(Math.round(x), Math.round(y) - 1, 1, 3);
    }
  }
  ctx.globalAlpha = 1;
}

/* A flame, drawn as three tongues with a hot core. Flicker is two sines and a
 * value noise, which beats a random() because it stays smooth between frames
 * and stays identical between runs. */
function drawFlame(ctx, x, y, size, t, seed, cool, alpha = 1) {
  const outer = cool ? METAL.cyan : METAL.fire;
  const midC = cool ? '#9fe8f4' : METAL.ember;
  const core = cool ? '#eaffff' : '#fff3c4';
  ctx.globalAlpha = alpha;
  for (let i = 0; i < 3; i++) {
    const s = seed + i * 3.7;
    const wob = noise(t * 7 + s) * 0.5 + 0.6;
    const fh = Math.max(2, size * wob * (i === 0 ? 1 : 0.62));
    const sway = Math.sin(t * 5.5 + s * 2.1) * (i === 0 ? 1.2 : 2.4);
    const bx = x + (i === 1 ? -size * 0.28 : i === 2 ? size * 0.28 : 0);
    for (let k = 0; k < fh; k++) {
      const kk = k / fh;
      const w = Math.max(1, Math.round((1 - kk * kk) * size * (i === 0 ? 0.46 : 0.26)));
      ctx.fillStyle = kk > 0.62 ? outer : kk > 0.28 ? midC : core;
      ctx.fillRect(Math.round(bx - w / 2 + sway * kk * kk), Math.round(y - k), w, 1);
    }
  }
  ctx.globalAlpha = alpha * 0.55;                  // the glow it throws
  ctx.fillStyle = outer;
  const r = Math.round(size * (0.8 + noise(t * 3 + seed) * 0.2));
  blockEllipse(ctx, x, y - size * 0.3, r, r, outer, 0.25);
  ctx.globalAlpha = 1;
}

/* Rain. Analytic like everything else: a drop's position is its phase through a
 * fall, so there is no simulation and no state. Sheared by a fixed wind rather
 * than falling straight, because vertical rain reads as a scratched film print.
 *
 * x, y, speed, length — four floats, one flat array.
 */
function buildRain(seed, count, W, H) {
  const rand = rng((seed ^ 0x9a17c3) >>> 0);
  const a = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) {
    a[i * 4 + 0] = rand() * W;
    a[i * 4 + 1] = rand() * H;
    a[i * 4 + 2] = 0.7 + rand() * 0.6;
    a[i * 4 + 3] = 3 + rand() * 5;
  }
  return a;
}

const RAIN_WIND = 0.42;                  // horizontal pixels per vertical pixel

function drawRain(ctx, a, t, o) {
  const W = o.w, H = o.h, speed = o.speed, colour = o.colour;
  const splash = o.splash;
  ctx.fillStyle = colour;
  for (let i = 0; i < a.length; i += 4) {
    const sp = a[i + 2];
    let y = a[i + 1] + t * speed * sp;
    const cycle = ((y % H) + H) % H;
    let x = a[i] - cycle * RAIN_WIND;
    x = ((x % W) + W) % W;
    const len = Math.round(a[i + 3] * (o.stretch || 1));
    const yy = Math.round(cycle) + o.y0;
    ctx.globalAlpha = o.alpha;
    for (let k = 0; k < len; k++) {
      ctx.fillRect(Math.round(x + k * RAIN_WIND) + o.x0, yy - k, 1, 1);
    }
    // The hit. Only the drops that land on the deck get one, which is what
    // tells the eye where the floor is.
    if (splash && cycle > H - 5) {
      const s2 = (cycle - (H - 5)) / 5;
      ctx.globalAlpha = o.alpha * (1 - s2) * 0.9;
      const r = 1 + Math.round(s2 * 3);
      ctx.fillRect(Math.round(x) + o.x0 - r, yy - 1, r * 2, 1);
      ctx.fillRect(Math.round(x) + o.x0, yy - 2 - Math.round(s2 * 2), 1, 1);
    }
  }
  ctx.globalAlpha = 1;
}

/* Dust hanging in the key light. It drifts up rather than falling, it is drawn
 * additively in the key's own colour, and it is only bright where the beam is.
 * A mote that glows on the shadow side of the room is a sticker; a mote that
 * only lights up when it crosses the shaft is what makes air look like air. */
function drawDust(ctx, a, t, o) {
  const W = o.w, H = o.h, lx = o.lightX, reach = o.reach;
  ctx.fillStyle = o.colour;
  for (let i = 0; i < a.length; i += 5) {
    const sp = a[i + 2], ph = a[i + 3];
    let y = a[i + 1] - t * o.speed * sp;
    y = ((y % H) + H) % H;
    const x = a[i] + Math.sin(t * 0.42 * sp + ph) * 7;
    const inBeam = 1 - Math.min(1, Math.abs(x - lx) / reach);
    if (inBeam <= 0.02) continue;
    const twinkle = 0.55 + 0.45 * Math.sin(t * 1.9 + ph * 4);
    ctx.globalAlpha = o.alpha * inBeam * inBeam * twinkle;
    ctx.fillRect(Math.round(((x % W) + W) % W) + o.x0, Math.round(y) + o.y0,
                 a[i + 4] > 0.9 ? 2 : 1, 1);
  }
  ctx.globalAlpha = 1;
}

function buildDrips(seed, count, stage) {
  const rand = rng(seed ^ 0xd819);
  const a = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) {
    a[i * 4 + 0] = 8 + rand() * (stage.w - 16);
    a[i * 4 + 1] = 6 + rand() * 34;               // where it lets go
    a[i * 4 + 2] = 1.6 + rand() * 3.4;            // period
    a[i * 4 + 3] = rand() * 6;                    // offset
  }
  return a;
}

function drawDrips(ctx, a, t, colour, stage) {
  for (let i = 0; i < a.length; i += 4) {
    const x = a[i], y0 = a[i + 1], period = a[i + 2];
    const k = (((t + a[i + 3]) % period) + period) % period / period;
    const fall = stage.ground - 6 - y0;
    const y = y0 + fall * Math.min(1, k * k * 1.25);
    ctx.globalAlpha = 0.75;
    ctx.fillStyle = colour;
    if (k < 0.92) {
      ctx.fillRect(Math.round(x), Math.round(y), 1, k > 0.3 ? 3 : 2);
      ctx.globalAlpha = 0.3;
      ctx.fillRect(Math.round(x), Math.round(y) - 2, 1, 2);
    } else {                                       // the splash, briefly
      const s = (k - 0.92) / 0.08;
      ctx.globalAlpha = 0.6 * (1 - s);
      const r = Math.round(1 + s * 4);
      ctx.fillRect(Math.round(x - r), stage.ground - 6, r * 2, 1);
      ctx.fillRect(Math.round(x - 1), stage.ground - 7, 2, 1);
    }
    ctx.globalAlpha = 1;
  }
}

function buildBolts(seed, count, stage) {
  const out = [];
  for (let b = 0; b < count; b++) {
    const rand = rng((seed ^ 0xb017) + b * 7919);
    const pts = [];
    let x = 24 + rand() * (stage.w - 48);
    let y = -8;
    while (y < stage.ground - 20) {
      pts.push(x, y);
      y += 5 + rand() * 9;
      x += (rand() - 0.5) * 18;
    }
    pts.push(x, y);
    out.push(Float32Array.from(pts));
  }
  return out;
}

/* Two spikes and a long tail: a strike that flashes once, gutters, then flashes
 * again is the one that reads as weather rather than as a screen glitch. */
function boltEnvelope(k) {
  if (k > 0.28) return 0;
  const a = Math.max(0, 1 - k / 0.06);
  const b = k > 0.1 && k < 0.2 ? Math.max(0, 1 - Math.abs(k - 0.14) / 0.05) * 0.7 : 0;
  return Math.max(a * a, b);
}

function drawBolt(ctx, pts, env, colour) {
  ctx.globalAlpha = env;
  for (let i = 0; i < pts.length - 2; i += 2) {
    segment(ctx, pts[i], pts[i + 1], pts[i + 2], pts[i + 3], 2, colour);
  }
  ctx.globalAlpha = env * 0.55;
  for (let i = 0; i < pts.length - 2; i += 2) {
    segment(ctx, pts[i] + 2, pts[i + 1], pts[i + 2] + 2, pts[i + 3], 4, colour);
  }
  ctx.globalAlpha = 1;
}

/* ================================================================
 * CAMERA
 * ================================================================
 * The stage never moves on its own; the camera does, and it has opinions about
 * when. Six behaviours, and the FX layer drives all of them:
 *
 *   idle    a slow lissajous drift that OPENS OUT during a lull and closes
 *           down the instant anything lands. A camera that breathes the same
 *           way through a quiet turn and a finisher is a camera nobody
 *           believes.
 *   shake   decaying, on impact, with a directional kick and an overshoot back
 *           through centre — the snap back, which is the part that sells it.
 *   punch   a fast push-in and release, on a critical strike
 *   cast    a slow push-in, a hold, and a slow release, over a whole cast
 *   focus   a gentle lean toward whoever is acting, eased in and eased out
 *   push    a slow, long push-in for a boss entrance
 *
 * baseZoom is 1.03 rather than 1 so the frame is always slightly over-scanned.
 * That is what lets drift, lean and shake move the whole world without any
 * caller having to clamp them, and it costs 3% of a 192x128 stage.
 *
 * MOTION SICKNESS IS A FAILURE, so every term is small and the sum is clamped
 * hard at the end: seven logical pixels across, five down, and a fifth of a
 * stop of zoom. Everything here is meant to be felt and not seen. If you can
 * point at the camera move, it is too big.
 */
export function createCamera(opts = {}) {
  const base = opts.baseZoom || 1.03;
  return {
    baseZoom: base,
    zoom: base,
    ox: 0, oy: 0,
    t: 0,
    reducedMotion: !!opts.reducedMotion,
    drift: opts.drift === undefined ? 1 : opts.drift,
    _shake: 0, _shakeT: 0, _shakeDur: 0,
    _kick: 0, _kickDir: 1, _kickT: 1,
    _punch: 0, _punchT: 0, _punchDur: 0,
    _cast: 0, _castT: 0, _castDur: 0, _castHold: 0,
    _pushFrom: 0, _pushT: 0, _pushDur: 0, _pushLift: 0,
    _lean: 0, _leanTo: 0,
    _calm: 9,

    setReducedMotion(v) { this.reducedMotion = !!v; return this; },

    /* Anything the fight does closes the idle drift down. It reopens on its
     * own over the next few seconds of quiet. */
    _busy() { this._calm = 0; return this; },

    /* mag is in logical pixels of throw. 3 is a hit, 6 a crit, 10 a boss.
     * dirX is which way the blow came from: -1, 0 or +1. */
    shake(mag, dur = 0.36, dirX = 0) {
      const m = Math.max(0, mag) * (this.reducedMotion ? 0.2 : 1);
      this._calm = 0;
      if (m <= this._shake * Math.max(0, 1 - this._shakeT / Math.max(0.01, this._shakeDur))) return this;
      this._shake = m; this._shakeT = 0; this._shakeDur = Math.max(0.05, dur);
      // The kick: the frame is shoved once along the blow and springs back
      // through centre. Without it a shake is a vibration, not an impact.
      this._kick = m * 0.55;
      this._kickDir = dirX < 0 ? -1 : dirX > 0 ? 1 : (noise(this.t * 53.1) < 0.5 ? -1 : 1);
      this._kickT = 0;
      return this;
    },

    /* amount is extra zoom: 0.06 is a crit, 0.12 is a finisher. */
    punch(amount = 0.06, dur = 0.42) {
      this._punch = amount * (this.reducedMotion ? 0.25 : 1);
      this._punchT = 0; this._punchDur = Math.max(0.08, dur);
      this._calm = 0;
      return this;
    },

    /* The cast: in over a quarter of a second, hold while the spell builds,
     * out as it lands. Slower and smaller than a punch, and the two stack. */
    cast(amount = 0.05, dur = 1.1, hold = 0.34) {
      this._cast = amount * (this.reducedMotion ? 0.2 : 1);
      this._castT = 0;
      this._castDur = Math.max(0.15, dur);
      this._castHold = clamp(hold, 0, 0.6);
      this._calm = 0;
      return this;
    },

    /* Lean toward whoever is acting. `x` is a logical stage x; the frame moves
     * a small fraction of the way there and eases back when released. */
    focus(x, stage = SCENE_STAGE) {
      const half = Math.max(1, stage.w / 2);
      this._leanTo = clamp((x - half) / half * 2.6, -3, 3);
      this._calm = 0;
      return this;
    },

    release() { this._leanTo = 0; return this; },

    /* Snap back: drop the lean and the cast now, and spring through centre.
     * This is the beat after a finisher, not something to call every frame. */
    snap() {
      this._leanTo = 0;
      this._castT = this._castDur;
      this._kick = Math.max(this._kick * 0.5, Math.abs(this._lean) * 0.6);
      this._kickDir = this._lean > 0 ? -1 : 1;
      this._kickT = 0;
      this._calm = 0;
      return this;
    },

    /* The boss entrance: start wide and creep in over several seconds. */
    push(dur = 4.5, from = 1.16, lift = 3) {
      this._pushFrom = from;
      this._pushLift = lift;
      this._pushT = 0;
      this._pushDur = this.reducedMotion ? 0.3 : Math.max(0.2, dur);
      this._calm = 0;
      return this;
    },

    stopPush() { this._pushT = this._pushDur; return this; },

    reset() {
      this.zoom = this.baseZoom; this.ox = 0; this.oy = 0; this.t = 0;
      this._shake = 0; this._shakeT = 0; this._shakeDur = 0;
      this._kick = 0; this._kickT = 1; this._kickDir = 1;
      this._punch = 0; this._punchT = 0; this._punchDur = 0;
      this._cast = 0; this._castT = 0; this._castDur = 0; this._castHold = 0;
      this._pushDur = 0; this._pushT = 0;
      this._lean = 0; this._leanTo = 0;
      this._calm = 9;
      return this;
    },

    update(dt) {
      const step = Math.min(0.05, Math.max(0, dt || 0));
      this.t += step;
      this._calm += step;
      let x = 0, y = 0, z = this.baseZoom;

      if (!this.reducedMotion && this.drift) {
        // Half amplitude while the fight is live, full after five seconds of
        // nothing happening. The lull is the only time the camera wanders.
        const lull = 0.5 + 0.5 * clamp((this._calm - 1.1) / 5, 0, 1);
        const d = this.drift * lull;
        x += (Math.sin(this.t * 0.37) * 1.1 + Math.sin(this.t * 0.11 + 2.1) * 0.6) * d;
        y += (Math.sin(this.t * 0.23 + 1.7) * 0.7) * d;
      }
      // The lean is always easing somewhere, which is why it never reads as a
      // cut. Frozen under reduced motion, like everything else lateral.
      this._lean += (this._leanTo - this._lean) * Math.min(1, step * 3.2);
      if (!this.reducedMotion) x += this._lean;

      if (this._shakeT < this._shakeDur) {
        this._shakeT += step;
        const k = Math.max(0, 1 - this._shakeT / this._shakeDur);
        const m = this._shake * k * k;
        x += (noise(this._shakeT * 137.1) - 0.5) * 2 * m;
        y += (noise(this._shakeT * 91.7 + 9.3) - 0.5) * 2 * m * 0.7;
      }
      if (this._kickT < 1) {
        // One shove out, one overshoot back, settled by a second. A decaying
        // sine rather than a decaying random: the eye reads it as the room
        // taking the hit and recovering, which is the point.
        this._kickT += step / 0.55;
        const k = Math.min(1, this._kickT);
        const sp = Math.sin(k * 8.6) * Math.pow(1 - k, 2.2);
        x += this._kick * this._kickDir * sp;
        y += this._kick * sp * 0.3;
      }
      if (this._punchT < this._punchDur) {
        this._punchT += step;
        const k = this._punchT / this._punchDur;
        // Snap in over the first fifth, drift back out over the rest.
        const curve = k < 0.2 ? easeOut(k / 0.2) : 1 - easeInOut((k - 0.2) / 0.8);
        z += this._punch * curve;
      }
      if (this._castT < this._castDur) {
        this._castT += step;
        const k = this._castT / this._castDur;
        const rise = clamp(k / 0.26, 0, 1);
        const tail = Math.max(0.08, 0.74 - this._castHold);
        const fall = clamp((k - 0.26 - this._castHold) / tail, 0, 1);
        const held = easeInOut(rise) - easeInOut(fall);
        z += this._cast * held;
        y += this._cast * 9 * held;         // a breath of lift with the push
      }
      if (this._pushT < this._pushDur) {
        this._pushT += step;
        const k = this._pushT / this._pushDur;
        z = lerp(this._pushFrom, z, easeInOut(k));
        y += this._pushLift * (1 - easeInOut(k));
      }
      // The hard stop. Every term above is deliberately small; this is what
      // guarantees they can never sum into something that makes anyone ill,
      // and it is also what lets the over-scan margin be a fixed 16 pixels.
      this.ox = clamp(x, -7, 7);
      this.oy = clamp(y, -5, 5);
      this.zoom = clamp(z, this.baseZoom - 0.02, this.baseZoom + 0.22);
      return this;
    },
  };
}

/* The default camera. Exported so fx.js can drive it without owning it:
 *   import { camera } from './battlescene.js';
 *   camera.shake(6); camera.punch(0.08);
 */
export const camera = createCamera();

/* Multiplies the caller's transform. Zoom is about the fight, not the frame
 * centre, so a push-in closes on the combatants rather than on the floor. */
export function applyCamera(ctx, cam, stage = SCENE_STAGE) {
  if (!cam) return;
  const cx = stage.w / 2;
  const cy = stage.ground - 14;
  ctx.translate(cx + cam.ox, cy + cam.oy);
  ctx.scale(cam.zoom, cam.zoom);
  ctx.translate(-cx, -cy);
}

/* Where the caller should put feet. Handed out rather than assumed, because a
 * boss stage lifts the standing line by a pixel or two. */
export function sceneAnchors(scene) {
  const stage = (scene && scene.stage) || SCENE_STAGE;
  const rig = scene && scene.light;
  return {
    ground: stage.ground,
    heroX: stage.heroX,
    enemyX: stage.enemyX,
    centreX: stage.w / 2,
    keyX: scene ? scene.keyX : stage.enemyX,
    // Added alongside, never in place of: the one light, so a caller that
    // wants to lean a sprite's own shading the right way can ask.
    lightX: rig ? rig.x : stage.enemyX,
    lightY: rig ? rig.y : stage.ground - 32,
    lightDir: rig ? rig.dir : 1,
  };
}

/* The scene's light rig, for anything outside this module that has to agree
 * with it — a sprite that wants its own specular on the correct side, an
 * effect that wants to be the same colour as the room. Added alongside
 * sceneAnchors rather than folded into it, because it is a different question.
 */
export function sceneLight(scene) {
  const rig = scene && scene.light;
  if (!rig) {
    return {
      x: SCENE_STAGE.enemyX, y: SCENE_STAGE.ground - 32, sx: SCENE_STAGE.enemyX,
      sy: 20, dir: 1, warm: 0.2, spread: 1,
      colour: METAL.chrome, rim: METAL.bone, bounce: METAL.steel,
    };
  }
  return {
    x: rig.x, y: rig.y, sx: rig.sx, sy: rig.sy, dir: rig.dir,
    warm: rig.warm, spread: rig.spread,
    colour: rig.colour, rim: rig.rim, bounce: rig.bounce,
  };
}

/* ================================================================
 * SCENE CONSTRUCTION
 * ================================================================ */

/* Build every surface a stage needs. Call once per encounter — this is the only
 * function in the module that allocates, and it is the reason drawScene() does
 * not have to.
 *
 *   biome         one of BIOME_KEYS (region.biome from gauntlet/world.py)
 *   boss          false, true, or the boss record {id, name, colour, sprite}
 *   palette       a pixel.PALETTES name, or a palette object
 *   reducedMotion freezes drift, weather, flicker and lightning
 *   key / seed    determinism: the same key always builds the same stage
 *   stage         geometry override, defaults to SCENE_STAGE
 */
export function createScene(opts = {}) {
  const stage = opts.stage || SCENE_STAGE;
  const biome = BIOMES[opts.biome] ? opts.biome : 'grass';
  const spec = BIOMES[biome];
  const bossObj = (opts.boss && typeof opts.boss === 'object') ? opts.boss : null;
  const isBoss = !!opts.boss;
  const palName = typeof opts.palette === 'string' ? opts.palette : null;
  const pal = (palName && PALETTES[palName])
    || (opts.palette && opts.palette.ground ? opts.palette : PALETTES.iron);
  const bossColour = (bossObj && bossObj.colour) || opts.colour || spec.accent;
  const key = opts.key || [
    biome, palName || 'iron',
    isBoss ? ((bossObj && (bossObj.id || bossObj.name || bossObj.sprite)) || 'boss') : 'field',
  ].join('|');
  const seed = (opts.seed === undefined ? hash(key) : (opts.seed >>> 0)) || 1;
  const reducedMotion = !!opts.reducedMotion;
  const has = k => spec.anim.indexOf(k) >= 0;

  // A boss drags the whole room toward its own colour. That is most of why a
  // boss arena reads as a different place rather than as the same place louder.
  const accent = isBoss ? mix(spec.accent, bossColour, 0.6) : spec.accent;
  const tint = pal.mid || pal.ground || METAL.gun;
  // The haze has to be LIGHTER than the sky it sits against, or a far layer
  // mixed toward it just gets darker and the depth ramp collapses into one
  // value. This is the colour distance is painted in.
  const hazeColour = shade(mix(mix(spec.sky[2], spec.fog, 0.5), METAL.steel, 0.4), 26);
  const W2 = stage.w * 2;

  /* ---- parallax layers ---- */
  const layers = [];
  for (let i = 0; i < spec.layers.length; i++) {
    const L = spec.layers[i];
    const src = pal[L.src] || pal.mid || METAL.steel;
    // Atmospheric perspective, and it has to run the right way round: far layers
    // wash toward the sky and lose contrast, near layers fall to near-black
    // silhouette. Backwards — near layers lightest — is exactly what makes a
    // generated backdrop read as wallpaper, every layer the same weight with no
    // air between any of them.
    const hazeK = clamp(1 - L.depth / 0.72, 0, 1);
    const hazed = mix(grade(src, spec.hue, -10), hazeColour, hazeK * 0.55);
    const body = shade(hazed, L.tone * 0.28 - (1 - hazeK) * 30 - (isBoss ? 8 : 0));
    const c = {
      body,
      light: shade(body, 30 + hazeK * 8),
      dark: shade(body, -26),
      // At this contrast the rim carries the whole read, so it is pushed harder
      // toward the accent on the near layers, where the body is nearly black.
      edge: mix(shade(body, 54), accent, 0.34 + (1 - hazeK) * 0.3),
      glow: mix(accent, METAL.ember, 0.25),
      cap: mix(METAL.bone, body, 0.3),
    };
    const s = surface(W2, L.h);
    const paint = PAINTERS[L.paint] || paintRidge;
    paint(s.ctx, W2, L.h, rng(seed + i * 2654435761), c, L.o || {});
    layers.push({
      canvas: s.canvas,
      depth: L.depth,
      rate: reducedMotion ? 0 : L.rate,
      // `top` layers hang from the ceiling; everything else stands on the floor.
      y: L.top ? -PAD : stage.ground - L.h,
    });
  }

  /* ---- sky and horizon ---- */
  const sky = buildSky(spec, tint, seed, stage.w + PAD * 2, stage.ground + PAD, isBoss);

  /* ---- the platform ---- */
  const deck = grade(pal.ground || pal.mid, spec.hue * 0.85, -30);
  const platform = buildPlatform(spec.platform, {
    deck,
    deckLight: shade(deck, 32),
    deckBack: shade(deck, -30),
    lip: mix(shade(deck, 72), accent, 0.45),
    faceTop: shade(deck, -34),
    face: shade(deck, -46),
    joint: shade(deck, -40),
  }, seed, stage, isBoss);

  /* ---- light ----
   * One source. Its position, colour, direction and rim are all published on
   * the scene so that the figures, their shadows, the deck pool and the beam
   * in the air cannot disagree about where it is. See THE LIGHT RIG above. */
  const light = buildLightRig(spec, stage, accent, isBoss);
  const keyX = light.x;
  const keyY = light.y;
  const keyGlow = radialGlow(Math.round((isBoss ? 78 : 62) * light.spread), light.colour, 9, 1);
  const floorPool = ovalGlow(Math.round((isBoss ? 62 : 46) * light.spread),
                             isBoss ? 15 : 11, light.colour, 8, 0.9);
  // Not a second key: the key coming back off the deck. Dimmer, cooler, low.
  const fillGlow = radialGlow(44, light.bounce, 7, 1);
  const shaft = light.shaft > 0.1 ? buildShaft(light, stage, seed) : null;
  // The corners fall to the region's own darkness rather than to pure black,
  // which is a quarter of the per-realm mood on its own.
  const vignette = buildVignette(stage.w + PAD * 2, stage.h + PAD * 2,
                                 isBoss ? 2.2 : 1.5,
                                 mix(METAL.black, spec.fog, 0.13));

  /* ---- frame furniture ---- */
  const occC = {
    dark: mix(METAL.black, accent, 0.09),
    mid: mix(METAL.gun, accent, 0.2),
    rim: mix(accent, METAL.bone, 0.25),
  };
  const occLeft = buildOccluder(spec.occluder, occC, seed ^ 0x11, stage);
  const occRightSrc = buildOccluder(spec.occluder, occC, seed ^ 0x22, stage);
  const torches = [];
  if (has('torch')) {
    const a = addTorchBracket(occLeft, occC, 34, 46);
    addTorchBracket(occRightSrc, occC, 34, 46);
    torches.push({ x: -PAD + a.x, y: -PAD + a.y, seed: 1.7 });
    // The right bracket is mirrored with its canvas, so its anchor mirrors too.
    torches.push({
      x: stage.w + PAD - OCC_W + (OCC_W - 1 - a.x),
      y: -PAD + a.y,
      seed: 5.3,
    });
  }
  const occRight = mirrorCanvas(occRightSrc);

  /* ---- the apron: the fourth depth, in front of the fight ---- */
  const apron = buildApron(apronKind(spec.platform), {
    body: mix(METAL.black, accent, 0.06),
    mid: mix(METAL.black, occC.mid, 0.45),
    rim: mix(light.rim, METAL.black, 0.45),
  }, seed ^ 0x33, stage);
  const apronY = stage.ground - APRON_LIFT;

  /* ---- volumetrics and weather ---- */
  // Every room has air in it. A biome that does not call for fog still gets the
  // three bands, at a third of the weight: the point is not weather, it is that
  // there is something between the camera and the far layer, and without it the
  // depth ramp has nothing to hang on.
  const fogK = (has('fog') || has('godray')) ? 1 : 0.34;
  const fog = [];
  fog.push({ canvas: buildFogBand(spec.fog, seed + 3, W2, 34), y: stage.ground - 44, rate: 3, depth: 0.25, alpha: 0.55 * fogK });
  fog.push({ canvas: buildFogBand(spec.fog, seed + 7, W2, 26), y: stage.ground - 22, rate: 7, depth: 0.5, alpha: 0.42 * fogK });
  fog.push({ canvas: buildFogBand(mix(spec.fog, METAL.black, 0.3), seed + 11, W2, 30), y: stage.ground + 2, rate: 13, depth: 0.9, alpha: 0.5 * fogK });
  const godrays = has('godray')
    ? buildGodrays(mix(accent, METAL.bone, 0.35), seed, stage.w + PAD * 2, stage.ground + PAD)
    : null;

  let motes = null, moteStyle = null, foreMotes = null;
  const weather = has('ash') ? 'ash' : has('snow') ? 'snow' : has('leaves') ? 'leaves'
    : has('ember') ? 'ember' : null;
  if (weather) {
    motes = buildMotes(seed + 17, 34, stage.w, stage.ground);
    foreMotes = buildMotes(seed + 23, 14, stage.w, stage.h);
    moteStyle = {
      ash:    { colour: mix(METAL.bone, METAL.steel, 0.55), dir: 1, speed: 5, sway: 4, alpha: 0.4, size: 1 },
      snow:   { colour: '#e6eefc', dir: 1, speed: 7, sway: 5, alpha: 0.55, size: 1 },
      leaves: { colour: mix(METAL.bile, METAL.rust, 0.5), dir: 1, speed: 9, sway: 7, alpha: 0.5, size: 1 },
      ember:  { colour: METAL.ember, dir: -1, speed: 11, sway: 3, alpha: 0.75, size: 1 },
    }[weather];
  }
  const wisps = has('flies') ? buildMotes(seed + 31, 18, stage.w, stage.ground - 12) : null;
  const drips = has('drip') ? buildDrips(seed, 9, stage) : null;
  const bolts = has('lightning') && !reducedMotion ? buildBolts(seed, 6, stage) : null;
  // Rain is two sheets at two depths. The depth cue is entirely the speed and
  // the length of the streak; the near sheet is what puts the camera outside.
  const rain = (has('rain') && !reducedMotion) ? buildRain(seed + 41, 46, stage.w, stage.ground + 4) : null;
  const foreRain = rain ? buildRain(seed + 43, 22, stage.w, stage.h) : null;
  // Dust in the beam. Every room gets it, because every room has a key light.
  const dust = buildMotes(seed + 53, 18, stage.w, stage.ground - 6);

  /* ---- boss furniture ---- */
  const sigil = isBoss ? buildSigil(bossColour, seed, stage) : null;
  const brazier = isBoss ? buildBrazier({
    iron: mix(METAL.gun, accent, 0.18),
    lit: mix(bossColour, METAL.ember, 0.4),
  }) : null;
  const braziers = isBoss ? [
    { x: 24, y: stage.ground + 4, seed: 0.4 },
    { x: stage.w - 24, y: stage.ground + 4, seed: 3.1 },
  ] : null;

  /* ---- rim-light scratch pool ----
   * Four 64x64 surfaces, reused forever. Tinting a sprite silhouette needs a
   * scratch canvas; allocating one per call would put a canvas in the draw
   * loop, which is the one thing this module does not do. */
  const tintPool = [];
  for (let i = 0; i < 4; i++) {
    const s = surface(64, 64);
    tintPool.push({ canvas: s.canvas, ctx: s.ctx, src: null, colour: null });
  }

  return {
    key, seed, biome, stage, spec, pal, reducedMotion,
    boss: isBoss, bossColour, accent,
    sky, layers, platform, fog, godrays,
    occLeft, occRight, occX: { left: -PAD, right: stage.w + PAD - OCC_W },
    apron, apronY, apronX: -PAD - APRON_OFF,
    torches,
    motes, moteStyle, foreMotes, wisps, drips, bolts, weather,
    rain, foreRain, dust,
    sigil, brazier, braziers,
    keyGlow, floorPool, fillGlow, shaft, vignette,
    keyX, keyY, light,
    // Both figures are rimmed in the SAME colour from the SAME side. This is
    // the whole point of the rig: rimColour and heroRim are deliberately equal
    // now, and heroRim survives only so older callers keep working.
    rimColour: light.rim,
    heroRim: light.rim,
    rimDir: light.dir,
    bounceColour: light.bounce,
    // The grade, in two passes. A multiply in the region's own shadow tone
    // pulls everything into one colour space; a very low additive pass in a
    // near-black version of the key hue tints the blacks, which is what stops
    // seventeen dark rooms reading as the same dark room.
    gradeColour: mix(spec.sky[1], isBoss ? bossColour : spec.accent, 0.22),
    gradeLift: mix(METAL.black, light.colour, 0.15),
    gradeK: isBoss ? 0.26 : 0.18,
    liftK: 0.18 + light.warm * 0.1,
    lavaPulse: has('lava'),
    tintPool, tintNext: 0,
  };
}

/* Drop every surface a scene holds. The GC would get there anyway; this makes
 * it immediate when a long session cycles through a lot of encounters. */
export function destroyScene(scene) {
  if (!scene) return;
  scene.layers = [];
  scene.fog = [];
  scene.tintPool = [];
  scene.sky = scene.platform = scene.sigil = scene.brazier = null;
  scene.occLeft = scene.occRight = scene.vignette = scene.apron = null;
  scene.keyGlow = scene.floorPool = scene.fillGlow = scene.godrays = null;
  scene.shaft = null;
  scene.rain = scene.foreRain = scene.dust = null;
}

/* ================================================================
 * DRAWING
 * ================================================================ */

function blitWrapped(ctx, canvas, shift, y) {
  const W = canvas.width;
  const off = Math.round(((shift % W) + W) % W) - W;
  ctx.drawImage(canvas, off, Math.round(y));
  ctx.drawImage(canvas, off + W, Math.round(y));
}

function blitFog(ctx, band, t, cx, wobble) {
  const shift = -(t * band.rate) - cx * (1 - band.depth);
  ctx.globalAlpha = band.alpha;
  blitWrapped(ctx, band.canvas, shift, band.y + Math.sin(t * 0.31 + wobble) * 2);
  ctx.globalAlpha = 1;
}

/* Everything behind the combatants. Call inside the camera transform.
 *
 *   ctx        already scaled to the logical stage
 *   scene      from createScene()
 *   time       seconds; monotonic, not delta
 *   camera     optional; used for parallax, not for the transform
 */
export function drawScene(ctx, scene, time = 0, cam = null) {
  if (!scene || !scene.sky) return;
  const stage = scene.stage;
  const t = scene.reducedMotion ? 0 : (time || 0);
  const cx = cam ? cam.ox : 0;
  const cy = cam ? cam.oy : 0;

  /* --- sky: parallax at almost nothing, so it feels far rather than fixed --- */
  ctx.drawImage(scene.sky, Math.round(-PAD - cx * 0.9), Math.round(-PAD - cy * 0.85));

  /* --- lightning, behind the silhouettes so the ridge line stays black --- */
  let boltEnv = 0;
  if (scene.bolts && scene.bolts.length) {
    const period = 6.4;
    const k = ((t % period) + period) % period / period;
    boltEnv = boltEnvelope(k);
    if (boltEnv > 0.01) {
      const idx = Math.floor(t / period) % scene.bolts.length;
      ctx.globalAlpha = boltEnv * 0.22;                 // sky bloom around it
      ctx.fillStyle = scene.accent;
      ctx.fillRect(-PAD, -PAD, stage.w + PAD * 2, stage.ground + PAD);
      ctx.globalAlpha = 1;
      drawBolt(ctx, scene.bolts[idx], boltEnv, mix(scene.accent, '#ffffff', 0.6));
    }
  }
  scene._bolt = boltEnv || 0;

  /* --- lava seam breathing at the horizon --- */
  if (scene.lavaPulse) {
    const pulse = 0.35 + 0.2 * Math.sin(t * 1.3) + 0.1 * noise(t * 2.1);
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = clamp(pulse, 0, 1) * 0.5;
    ctx.drawImage(scene.floorPool,
                  Math.round(stage.w / 2 - scene.floorPool.width / 2),
                  Math.round(stage.ground - 16));
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  /* --- the three depth layers, with fog sliding between them --- */
  for (let i = 0; i < scene.layers.length; i++) {
    const L = scene.layers[i];
    blitWrapped(ctx, L.canvas, -(t * L.rate) - cx * (1 - L.depth),
                L.y - cy * (1 - L.depth) * 0.4);
    if (scene.fog[i]) blitFog(ctx, scene.fog[i], t, cx, i * 2.1);
  }

  /* --- godrays through whatever is above --- */
  if (scene.godrays) {
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.5 + 0.16 * Math.sin(t * 0.5);
    ctx.drawImage(scene.godrays,
                  Math.round(-PAD + Math.sin(t * 0.19) * 3 - cx * 0.4), -PAD);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  /* --- ambient weather behind the fight --- */
  if (scene.motes) {
    drawMotes(ctx, scene.motes, t, {
      w: stage.w, h: stage.ground, x0: 0, y0: 0,
      colour: scene.moteStyle.colour, dir: scene.moteStyle.dir,
      speed: scene.moteStyle.speed, sway: scene.moteStyle.sway,
      alpha: scene.moteStyle.alpha * 0.75, size: scene.moteStyle.size,
    });
  }
  if (scene.wisps) {
    drawWisps(ctx, scene.wisps, t, { colour: mix(scene.accent, '#ffffff', 0.4), alpha: 0.7 });
  }
  if (scene.drips) drawDrips(ctx, scene.drips, t, mix(scene.accent, '#ffffff', 0.5), stage);
  if (scene.rain) {
    drawRain(ctx, scene.rain, t, {
      w: stage.w, h: stage.ground + 4, x0: 0, y0: 0,
      colour: mix(scene.light.rim, '#ffffff', 0.3),
      speed: 96, alpha: 0.28, stretch: 1, splash: true,
    });
  }

  /* --- the platform, and the light pooled on it --- */
  ctx.drawImage(scene.platform, -PAD, Math.round(stage.ground - PLATFORM_TOP));

  if (scene.sigil) {
    // The sigil breathes, and flares when the key light flickers. Drawn with
    // 'lighter' so it reads as burnt into the floor rather than painted on it.
    const pulse = 0.42 + 0.2 * Math.sin(t * 1.6) + 0.08 * noise(t * 5);
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = clamp(pulse, 0, 1);
    ctx.drawImage(scene.sigil, 0, Math.round(stage.ground - 19));
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = (scene.boss ? 0.38 : 0.24) + 0.05 * noise(t * 3.3);
  ctx.drawImage(scene.floorPool,
                Math.round(scene.keyX - scene.floorPool.width / 2),
                Math.round(stage.ground - scene.floorPool.height / 2 + 2));
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';

  /* --- braziers: lit only for a boss, which is the point of them --- */
  if (scene.braziers) {
    for (let i = 0; i < scene.braziers.length; i++) {
      const b = scene.braziers[i];
      ctx.drawImage(scene.brazier, Math.round(b.x - scene.brazier.width / 2),
                    Math.round(b.y - scene.brazier.height));
      drawFlame(ctx, b.x, Math.round(b.y - scene.brazier.height + 4), 11,
                scene.reducedMotion ? 0.5 : t, b.seed, false, 1);
    }
  }

  /* --- THE LIGHT ---------------------------------------------------------
   * One source, in the region's colour, and everything downstream of it is
   * subordinate: the beam hanging in the air, the dust inside the beam, the
   * pool it lands in, and a single dim bounce off the deck. There is no second
   * key. Both figures are rimmed off this, from the same side, by drawRimLight
   * defaulting to scene.rimDir — which is the change that makes the stage read
   * as lit rather than as assembled. */
  const rig = scene.light;
  const flick = 1 + rig.flick * (noise(t * 7.3) - 0.5) * 2 + 0.4 * scene._bolt;

  ctx.globalCompositeOperation = 'lighter';
  if (scene.shaft) {
    ctx.globalAlpha = clamp(rig.shaft * 0.34 * flick, 0, 1);
    ctx.drawImage(scene.shaft, Math.round(-PAD - cx * 0.45),
                  Math.round(-PAD - cy * 0.4));
  }
  if (scene.dust) {
    drawDust(ctx, scene.dust, t, {
      w: stage.w, h: stage.ground - 6, x0: 0, y0: 0,
      colour: rig.rim, alpha: 0.5, speed: 3.2,
      lightX: lerp(rig.sx, rig.x, 0.5), reach: 44 * rig.spread,
    });
  }
  ctx.globalAlpha = clamp(((scene.boss ? 0.24 : 0.16) + 0.04 * noise(t * 2.7 + 4)) * flick, 0, 1);
  ctx.drawImage(scene.keyGlow, Math.round(scene.keyX - scene.keyGlow.width / 2),
                Math.round(scene.keyY - scene.keyGlow.height / 2));
  // The only other light in the room is this one coming back off the deck:
  // low, dim, on the shadow side, in a cooled version of the same hue. A fill
  // that is a second key of its own colour flattens the stage; a bounce keeps
  // the shadow side from going to a dead black, which is all it is for.
  ctx.globalAlpha = 0.09;
  ctx.drawImage(scene.fillGlow,
                Math.round(stage.w / 2 - rig.dir * 42 - scene.fillGlow.width / 2),
                Math.round(stage.ground - 6 - scene.fillGlow.height / 2));
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
}

/* Everything in front of the combatants. Call after the sprites, still inside
 * the camera transform. */
export function drawForeground(ctx, scene, time = 0, cam = null) {
  if (!scene || !scene.vignette) return;
  const stage = scene.stage;
  const t = scene.reducedMotion ? 0 : (time || 0);
  const cx = cam ? cam.ox : 0;
  const cy = cam ? cam.oy : 0;
  const fw = stage.w + PAD * 2;
  const fh = stage.h + PAD * 2;

  /* --- weather in front, larger and faster: the depth cue is the speed --- */
  if (scene.foreMotes) {
    drawMotes(ctx, scene.foreMotes, t, {
      w: stage.w, h: stage.h, x0: 0, y0: -PAD,
      colour: scene.moteStyle.colour, dir: scene.moteStyle.dir,
      speed: scene.moteStyle.speed * 2.6, sway: scene.moteStyle.sway * 1.4,
      alpha: scene.moteStyle.alpha, size: scene.moteStyle.size + 1,
    });
  }
  if (scene.fog[2]) blitFog(ctx, scene.fog[2], t, cx, 4.4);

  /* --- the near sheet of rain: shorter cycle, longer streaks, twice the
   *     speed. Nothing else about it is different, and that is the whole
   *     depth cue. --- */
  if (scene.foreRain) {
    drawRain(ctx, scene.foreRain, t, {
      w: stage.w, h: stage.h, x0: 0, y0: -PAD,
      colour: mix(scene.light.rim, '#ffffff', 0.45),
      speed: 210, alpha: 0.2, stretch: 2.1, splash: false,
    });
  }

  /* --- the apron: the fourth depth, under the camera's own feet, moving
   *     faster than the occluders and far faster than the set --- */
  if (scene.apron) {
    ctx.drawImage(scene.apron,
                  Math.round(scene.apronX + cx * 0.55),
                  Math.round(scene.apronY + cy * 0.3));
  }

  /* --- the occluders, moving faster than anything behind them --- */
  const occShift = Math.round(cx * 0.32);
  ctx.drawImage(scene.occLeft, scene.occX.left + occShift, -PAD);
  ctx.drawImage(scene.occRight, scene.occX.right + occShift, -PAD);

  for (let i = 0; i < scene.torches.length; i++) {
    const tor = scene.torches[i];
    drawFlame(ctx, tor.x + occShift, tor.y, 9,
              scene.reducedMotion ? 0.5 : t, tor.seed, false, 1);
  }

  /* --- the lightning flash, over everything, because it lights the room --- */
  if (scene._bolt > 0.01) {
    ctx.globalAlpha = scene._bolt * 0.3;
    ctx.fillStyle = mix(scene.accent, '#ffffff', 0.75);
    ctx.fillRect(-PAD, -PAD, fw, fh);
    ctx.globalAlpha = 1;
  }

  /* --- darkness toward the frame --- */
  ctx.globalAlpha = scene.boss ? 0.95 : 0.78;
  ctx.drawImage(scene.vignette, -PAD, -PAD);
  ctx.globalAlpha = 1;

  /* --- the grade, in two passes, so sky, stone and sprite share a colour
   *     space and each realm still has its own mood.
   *
   *     Pass one multiplies the region's shadow tone over everything: this is
   *     what makes a sprite drawn from one palette and a backdrop drawn from
   *     another look like they were photographed together.
   *
   *     Pass two adds a near-black version of the KEY colour. Additive at this
   *     weight touches almost nothing in the highlights and tints the blacks,
   *     which is exactly what a colour grade does and exactly what stops
   *     seventeen dark rooms reading as one dark room. --- */
  ctx.globalCompositeOperation = 'multiply';
  ctx.globalAlpha = scene.gradeK === undefined ? (scene.boss ? 0.26 : 0.18) : scene.gradeK;
  ctx.fillStyle = scene.gradeColour;
  ctx.fillRect(-PAD, -PAD, fw, fh);
  if (scene.gradeLift) {
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = scene.liftK === undefined ? 0.3 : scene.liftK;
    ctx.fillStyle = scene.gradeLift;
    ctx.fillRect(-PAD, -PAD, fw, fh);
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
}

/* ---------------- rim light ----------------
 * Tint a sprite's silhouette and stamp it a pixel off-centre, underneath the
 * sprite itself, so only the fringe shows. Cheaper than a shader and it keeps
 * the hero legible against a dark stage, which is the whole job.
 *
 * Call BEFORE drawing the sprite, at the same position.
 */
function tinted(scene, image, colour) {
  const pool = scene.tintPool;
  for (let i = 0; i < pool.length; i++) {
    if (pool[i].src === image && pool[i].colour === colour) return pool[i].canvas;
  }
  const e = pool[scene.tintNext % pool.length];
  scene.tintNext = (scene.tintNext + 1) % 1024;
  e.src = image; e.colour = colour;
  e.ctx.globalCompositeOperation = 'source-over';
  e.ctx.clearRect(0, 0, e.canvas.width, e.canvas.height);
  e.ctx.drawImage(image, 0, 0);
  e.ctx.globalCompositeOperation = 'source-in';
  e.ctx.fillStyle = colour;
  e.ctx.fillRect(0, 0, e.canvas.width, e.canvas.height);
  e.ctx.globalCompositeOperation = 'source-over';
  return e.canvas;
}

export function drawRimLight(ctx, scene, image, x, y, opts = {}) {
  if (!scene || !image || !scene.tintPool || !scene.tintPool.length) return;
  const w = image.width, h = image.height;
  const pool = scene.tintPool[0];
  if (w > pool.canvas.width || h > pool.canvas.height) return;
  const colour = opts.colour || scene.rimColour;
  const alpha = opts.alpha === undefined ? 0.75 : opts.alpha;
  // THE DEFAULT IS THE SCENE'S OWN LIGHT, not a per-caller guess. Pass dir
  // explicitly only when you mean to contradict the rig, which is almost never:
  // two figures rimmed from opposite sides is the thing this file exists to
  // stop. +1 is lit from the right.
  const dir = opts.dir === undefined ? (scene.rimDir || 1) : opts.dir;
  const img = tinted(scene, image, colour);
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = alpha;
  ctx.drawImage(img, 0, 0, w, h, Math.round(x + dir), Math.round(y), w, h);
  ctx.globalAlpha = alpha * 0.8;
  ctx.drawImage(img, 0, 0, w, h, Math.round(x + dir), Math.round(y - 1), w, h);
  ctx.globalAlpha = alpha * 0.5;
  ctx.drawImage(img, 0, 0, w, h, Math.round(x), Math.round(y - 1), w, h);
  // The bounce off the deck, on the shadow side, at a third of the weight.
  // Not a second rim light: it is what stops the unlit side going to a flat
  // silhouette, and it is drawn in the key's own cooled hue so the figure is
  // still only ever lit by one thing.
  if (scene.bounceColour && opts.bounce !== false) {
    ctx.globalAlpha = alpha * 0.26;
    ctx.drawImage(tinted(scene, image, scene.bounceColour), 0, 0, w, h,
                  Math.round(x - dir), Math.round(y + 1), w, h);
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
}

/* Contact shadow for a figure standing on the deck. Prebaked ovals would mean
 * one per sprite width; four fillRect rows is cheaper and hard-edged, which is
 * what the rest of the art is. */
export function drawFigureShadow(ctx, scene, x, width, opts = {}) {
  const stage = (scene && scene.stage) || SCENE_STAGE;
  const rx = Math.max(3, Math.round(width * 0.42));
  const ry = Math.max(1, Math.round(rx * 0.34));
  const y = (opts.y === undefined ? stage.ground + 1 : opts.y);
  const a = opts.alpha === undefined ? 0.5 : opts.alpha;
  // A shadow directly under a figure says the light is directly overhead, and
  // nothing in this game is lit from directly overhead. It is thrown away from
  // the key, which is the other half of the rim: together they are what tells
  // the eye where the source is without the source ever being in shot.
  const dir = opts.dir === undefined ? ((scene && scene.rimDir) || 1) : opts.dir;
  const cast = opts.offset === undefined
    ? -dir * Math.max(1, Math.round(rx * 0.5)) : opts.offset;
  ctx.globalAlpha = a * 0.45;
  blockEllipse(ctx, x + cast, y, rx + 1, ry, METAL.black);      // the cast
  ctx.globalAlpha = a * 0.3;
  blockEllipse(ctx, x + cast, y, rx + 3, ry + 1, METAL.black);  // its penumbra
  ctx.globalAlpha = a;
  blockEllipse(ctx, x, y, Math.max(2, rx - 2), ry, METAL.black); // the contact
  ctx.globalAlpha = 1;
}

export const SCENE_VERSION = '1.1.0';

/* ================================================================
 * WIRING (for whoever integrates this; nothing below runs)
 * ================================================================
 *
 * In fx.js, alongside the existing pixel/sprites imports:
 *
 *   import * as stagelayer from './battlescene.js';
 *
 * In BattleFX.setScene(), after the palette and biome are resolved:
 *
 *   this.stage3d = stagelayer.createScene({
 *     biome,
 *     boss: enemy && enemy.boss ? enemy : false,
 *     palette: palName,
 *     reducedMotion: this.reducedMotion,
 *     key: (region && region.id) || palName,
 *     stage: STAGE,
 *   });
 *   this.cam = stagelayer.camera.reset();
 *   if (enemy && enemy.boss) this.cam.push(4.5);
 *
 * In _update(dt): this.cam.update(dt);
 * In _render(), replace the shake offset and _drawBackdrop() with:
 *
 *   ctx.setTransform(this.px, 0, 0, this.px, this.ox, this.oy);
 *   ctx.save();
 *   stagelayer.applyCamera(ctx, this.cam, STAGE);
 *   stagelayer.drawScene(ctx, this.stage3d, this.clock, this.cam);
 *   ... _drawHero / _drawEnemy / _drawEffects / _drawParticles ...
 *   stagelayer.drawForeground(ctx, this.stage3d, this.clock, this.cam);
 *   ctx.restore();
 *   ... _drawHud and everything else, outside the camera transform ...
 *
 * THE ONE RULE FOR THE FIGURES. Both of them are lit by the same thing, from
 * the same side. _drawHero and _drawEnemy should each call, immediately before
 * their drawImage, EXACTLY THE SAME WAY:
 *
 *   stagelayer.drawFigureShadow(ctx, this.stage3d, x, width);
 *   stagelayer.drawRimLight(ctx, this.stage3d, frame, x, y);
 *
 * with no colour and no dir. Both default off scene.light: the same rim hue,
 * the same side, and a cast shadow thrown the other way. Passing { dir: -1 } to
 * one of them to make it "face" the other is the single easiest way to undo
 * everything this module does — it is what makes a stage read as two sprites on
 * a picture instead of two bodies in a room. If a figure needs to be special,
 * change its alpha, not its direction.
 *
 * The camera has opinions and wants to be told what is happening:
 *
 *   this.cam.shake(mag, 0.36, fromLeft ? -1 : 1);   where shakeMag was set
 *   this.cam.punch(0.08, 0.45);                     on DAMAGE_KIND.CRIT
 *   this.cam.cast(0.05);        this.cam.focus(x);  when a spell starts
 *   this.cam.snap();                                when it lands
 *   this.cam.release();                             at the end of a turn
 *   this.cam.push(4.5);                             on the boss name card
 *   this.cam.setReducedMotion(v);                   in setReducedMotion
 *
 * Nothing has to be clamped by the caller: update() clamps the sum to seven
 * logical pixels across and five down, and the art is built PAD oversize.
 *
 * BattleFX._drawBackdrop, buildBackdrop, silhouette, BIOME_FORM and the weather
 * particle set in fx.js are all superseded and can go.
 */
