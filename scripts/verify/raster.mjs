/* A canvas stub that actually RASTERISES.
 *
 * stub.mjs answers the question "did this code run without throwing, and did it
 * allocate?" — it records calls and never keeps a pixel. That is the right tool
 * for the boss, loot and spell harnesses, and it is the wrong tool for the one
 * claim the armour work has to stand on, which is a claim about pixels: a piece
 * of loot that does not change the sprite has not been implemented, and you
 * cannot tell whether the sprite changed by counting fillRect calls.
 *
 * So this is the same idea taken one step further: fillRect, drawImage and
 * friends composite into a real RGBA buffer, and the buffer can be diffed,
 * counted and hashed. It implements exactly what sprites.js and pixel.js touch
 * on the way to a sprite — the drawGrid path is fillStyle plus a 1x1 fillRect,
 * and scaleSprite is a nearest-neighbour drawImage — and nothing else. Anything
 * outside that (gradients, text metrics) answers plausibly and paints nothing,
 * because a harness that quietly half-draws is worse than one that does not
 * draw at all.
 *
 * Deliberately dependency-free and integer-exact: no canvas package, no
 * antialiasing, no floating-point compositing when alpha is 1. Two runs of the
 * same input produce byte-identical buffers, which is what lets determinism be
 * a measurement here rather than an assertion.
 */

/* #rgb, #rrggbb, #rrggbbaa and rgb()/rgba() — the shapes our own palettes emit.
 * An eight-digit hex is honoured rather than truncated: pixel.js shipped
 * '#b8955180' in a palette for a long time and a harness that silently drops
 * the alpha byte is a harness that cannot see that class of bug. */
function parseColour(css) {
  if (typeof css !== 'string') return [0, 0, 0, 255];
  const s = css.trim();
  if (s.charCodeAt(0) === 35) {
    let h = s.slice(1);
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    const n = parseInt(h.slice(0, 6), 16);
    if (!Number.isFinite(n)) return [0, 0, 0, 255];
    const a = h.length >= 8 ? parseInt(h.slice(6, 8), 16) : 255;
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, Number.isFinite(a) ? a : 255];
  }
  const m = /rgba?\(([^)]+)\)/.exec(s);
  if (m) {
    const p = m[1].split(',').map(Number);
    return [p[0] | 0, p[1] | 0, p[2] | 0, p.length > 3 ? Math.round(p[3] * 255) : 255];
  }
  return [0, 0, 0, 255];
}

class RasterContext {
  constructor(canvas) {
    this.canvas = canvas;
    this.fillStyle = '#000000'; this.strokeStyle = '#000000';
    this.globalAlpha = 1; this.globalCompositeOperation = 'source-over';
    this.imageSmoothingEnabled = false; this.lineWidth = 1;
    this.font = '8px monospace'; this.textAlign = 'left'; this.textBaseline = 'top';
    this.lineCap = 'butt'; this.lineJoin = 'miter';
    this.shadowBlur = 0; this.shadowColor = '#000000';
    this.shadowOffsetX = 0; this.shadowOffsetY = 0;
    this.filter = 'none'; this.miterLimit = 10; this.lineDashOffset = 0;
  }

  _put(x, y, rgba) {
    const c = this.canvas;
    x |= 0; y |= 0;
    if (x < 0 || y < 0 || x >= c.width || y >= c.height) return;
    const i = (y * c.width + x) * 4;
    const a = rgba[3] * this.globalAlpha;
    // The opaque case is a straight store. Sprite art is opaque, and rounding a
    // blend that did not need to happen is how a "deterministic" harness starts
    // reporting one-bit differences between runs of the same input.
    if (a >= 255) {
      c.data[i] = rgba[0]; c.data[i + 1] = rgba[1]; c.data[i + 2] = rgba[2]; c.data[i + 3] = 255;
      return;
    }
    if (a <= 0) return;
    const t = a / 255, inv = 1 - t;
    c.data[i]     = Math.round(rgba[0] * t + c.data[i]     * inv);
    c.data[i + 1] = Math.round(rgba[1] * t + c.data[i + 1] * inv);
    c.data[i + 2] = Math.round(rgba[2] * t + c.data[i + 2] * inv);
    c.data[i + 3] = Math.round(255      * t + c.data[i + 3] * inv);
  }

  fillRect(x, y, w, h) {
    const col = parseColour(this.fillStyle);
    x = Math.round(x); y = Math.round(y); w = Math.round(w); h = Math.round(h);
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this._put(x + i, y + j, col);
  }

  clearRect(x, y, w, h) {
    const c = this.canvas;
    x = Math.round(x); y = Math.round(y); w = Math.round(w); h = Math.round(h);
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      const xx = x + i, yy = y + j;
      if (xx < 0 || yy < 0 || xx >= c.width || yy >= c.height) continue;
      const k = (yy * c.width + xx) * 4;
      c.data[k] = c.data[k + 1] = c.data[k + 2] = c.data[k + 3] = 0;
    }
  }

  /* Nearest neighbour, which is the only scaling this game ever asks for: one
   * pixel grid, integer scale, everywhere. */
  drawImage(img, ...r) {
    if (!img || !img.data) return;
    let sx = 0, sy = 0, sw = img.width, sh = img.height;
    let dx = 0, dy = 0, dw = img.width, dh = img.height;
    if (r.length === 2) { dx = r[0]; dy = r[1]; }
    else if (r.length === 4) { dx = r[0]; dy = r[1]; dw = r[2]; dh = r[3]; }
    else if (r.length === 8) { sx = r[0]; sy = r[1]; sw = r[2]; sh = r[3]; dx = r[4]; dy = r[5]; dw = r[6]; dh = r[7]; }
    dw = Math.round(dw); dh = Math.round(dh);
    const ox = Math.round(dx), oy = Math.round(dy);
    for (let j = 0; j < dh; j++) {
      const v = sy + Math.floor(j * sh / dh);
      if (v < 0 || v >= img.height) continue;
      for (let i = 0; i < dw; i++) {
        const u = sx + Math.floor(i * sw / dw);
        if (u < 0 || u >= img.width) continue;
        const k = (v * img.width + u) * 4;
        const a = img.data[k + 3];
        if (!a) continue;
        this._put(ox + i, oy + j, [img.data[k], img.data[k + 1], img.data[k + 2], a]);
      }
    }
  }

  getImageData(x, y, w, h) {
    const c = this.canvas;
    const W = Math.max(1, w | 0), H = Math.max(1, h | 0);
    const out = new Uint8ClampedArray(W * H * 4);
    for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
      const xx = (x | 0) + i, yy = (y | 0) + j;
      if (xx < 0 || yy < 0 || xx >= c.width || yy >= c.height) continue;
      const k = (yy * c.width + xx) * 4, o = (j * W + i) * 4;
      out[o] = c.data[k]; out[o + 1] = c.data[k + 1];
      out[o + 2] = c.data[k + 2]; out[o + 3] = c.data[k + 3];
    }
    return { width: W, height: H, data: out };
  }

  putImageData(d, x, y) {
    for (let j = 0; j < d.height; j++) for (let i = 0; i < d.width; i++) {
      const k = (j * d.width + i) * 4;
      this._put((x | 0) + i, (y | 0) + j, [d.data[k], d.data[k + 1], d.data[k + 2], d.data[k + 3]]);
    }
  }

  createLinearGradient() { return { addColorStop() {} }; }
  createRadialGradient() { return { addColorStop() {} }; }
  createPattern() { return {}; }
  measureText(t) { return { width: String(t).length * 6 }; }
}

/* Path and transform calls are accepted and ignored. Nothing on the character
 * path uses them — every sprite in sprites.js is grids and fillRects — and a
 * stub that pretended to implement them would be lying about coverage. */
for (const m of ['beginPath', 'closePath', 'fill', 'stroke', 'save', 'restore', 'clip',
  'moveTo', 'lineTo', 'arc', 'arcTo', 'ellipse', 'rect', 'roundRect',
  'quadraticCurveTo', 'bezierCurveTo', 'translate', 'scale', 'rotate', 'transform',
  'setTransform', 'resetTransform', 'strokeRect', 'fillText', 'strokeText',
  'setLineDash', 'getLineDash']) {
  RasterContext.prototype[m] = function () {};
}

class RasterCanvas {
  constructor() { this._w = 0; this._h = 0; this.data = new Uint8ClampedArray(0); this._ctx = null; }
  get width() { return this._w; }
  set width(v) { this._w = v | 0; this._alloc(); }
  get height() { return this._h; }
  set height(v) { this._h = v | 0; this._alloc(); }
  _alloc() { this.data = new Uint8ClampedArray(Math.max(0, this._w * this._h * 4)); }
  getContext() { if (!this._ctx) this._ctx = new RasterContext(this); return this._ctx; }
  toDataURL() { return 'data:,'; }
  addEventListener() {} removeEventListener() {}
  get style() { return (this._style ||= {}); }
  getBoundingClientRect() { return { x: 0, y: 0, width: this._w, height: this._h, top: 0, left: 0, right: this._w, bottom: this._h }; }
}

/* Counts canvases as they are created, so a harness can prove a cache is doing
 * its job without a second mechanism. */
export const RASTER = { canvases: 0, counting: false };

export function installRaster() {
  globalThis.document = {
    createElement(tag) {
      if (tag === 'canvas') { if (RASTER.counting) RASTER.canvases++; return new RasterCanvas(); }
      return { style: {}, getContext: () => new RasterContext(new RasterCanvas()) };
    },
    body: { appendChild() {} },
    documentElement: { style: {} },
  };
  globalThis.window = globalThis;
  globalThis.OffscreenCanvas = function (w, h) { const c = new RasterCanvas(); c.width = w; c.height = h; return c; };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};
  globalThis.devicePixelRatio = 1;
  globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
}

/* ---------- measurement ---------- */

/** Pixels whose RGBA differs. The headline "did this piece change anything". */
export function pixelDiff(a, b) {
  let n = 0;
  const len = Math.min(a.data.length, b.data.length);
  for (let i = 0; i < len; i += 4) {
    if (a.data[i] !== b.data[i] || a.data[i + 1] !== b.data[i + 1]
      || a.data[i + 2] !== b.data[i + 2] || a.data[i + 3] !== b.data[i + 3]) n++;
  }
  return n;
}

/** Pixels whose COVERAGE differs — colour discarded entirely. This is the test
 * that separates loot from a recolour: if a helm only repaints the head, this
 * number is zero and the player cannot see the helm from across a room. */
export function silhouetteDiff(a, b) {
  let n = 0;
  const len = Math.min(a.data.length, b.data.length);
  for (let i = 3; i < len; i += 4) if ((a.data[i] > 0) !== (b.data[i] > 0)) n++;
  return n;
}

/** Distinct opaque RGB values actually painted. Counted from the raster, never
 * from the palette dict: a palette with sixteen entries that only ever paints
 * fifteen of them is inside the budget, and a palette with fifteen entries that
 * a shading pass turns into sixteen is not. */
export function colourCount(cv) {
  const seen = new Set();
  for (let i = 0; i < cv.data.length; i += 4) {
    if (!cv.data[i + 3]) continue;
    seen.add((cv.data[i] << 16) | (cv.data[i + 1] << 8) | cv.data[i + 2]);
  }
  return seen.size;
}

/** FNV-1a over the whole buffer. Byte-identical frames hash identically. */
export function frameHash(cv) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < cv.data.length; i++) { h ^= cv.data[i]; h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(16).padStart(8, '0');
}
