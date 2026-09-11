// Instrumented canvas/DOM stub. Records the four failure classes that a parse
// check cannot see: nullish drawImage sources, non-finite coordinates, paint
// values that resolve to undefined (a missing palette key renders transparent,
// silently), and canvas allocation while a render loop is running.

export const REC = {
  nullImage: [], nonFinite: [], badPaint: [], allocInLoop: [],
  allocTotal: 0, drawCalls: 0, ctxCalls: 0,
  loopDepth: 0, where: '(top)',
};

export function enterLoop(name) { REC.loopDepth++; REC.where = name; }
export function exitLoop() { REC.loopDepth--; }
export function setWhere(w) { REC.where = w; }

const FINITE_ARGS = {
  fillRect: 4, clearRect: 4, strokeRect: 4, rect: 4, moveTo: 2, lineTo: 2,
  arc: 5, ellipse: 7, quadraticCurveTo: 4, bezierCurveTo: 6, translate: 2,
  scale: 2, rotate: 1, setTransform: 6, fillText: 3, strokeText: 3,
  createLinearGradient: 4, createRadialGradient: 6, roundRect: 4,
};

function checkFinite(name, args) {
  const n = FINITE_ARGS[name];
  if (n === undefined) return;
  for (let i = 0; i < Math.min(n, args.length); i++) {
    const v = args[i];
    if (typeof v !== 'number' || !Number.isFinite(v)) {
      REC.nonFinite.push({ where: REC.where, op: name, argIndex: i, value: String(v) });
      return;
    }
  }
}

function checkPaint(prop, value) {
  // A palette lookup that misses yields undefined; assigning it to fillStyle is
  // a no-op in the browser and the pixels stay transparent. Catch it here.
  if (value === undefined || value === null) {
    REC.badPaint.push({ where: REC.where, prop, value: String(value) });
    return;
  }
  if (typeof value === 'string' && (value.includes('undefined') || value.includes('NaN') || value === '')) {
    REC.badPaint.push({ where: REC.where, prop, value });
  }
}

class Gradient {
  addColorStop(o, c) { checkPaint('gradientStop', c); }
}
class Pattern {}

class Ctx {
  constructor(canvas) {
    this.canvas = canvas;
    this._fillStyle = '#000'; this._strokeStyle = '#000';
    this.globalAlpha = 1; this.globalCompositeOperation = 'source-over';
    this.lineWidth = 1; this.lineCap = 'butt'; this.lineJoin = 'miter';
    this.font = '10px sans-serif'; this.textAlign = 'start'; this.textBaseline = 'alphabetic';
    this.imageSmoothingEnabled = true; this.imageSmoothingQuality = 'low';
    this.shadowBlur = 0; this.shadowColor = 'transparent';
    this.shadowOffsetX = 0; this.shadowOffsetY = 0;
    this.filter = 'none'; this.miterLimit = 10; this.lineDashOffset = 0;
    for (const m of ['beginPath','closePath','fill','stroke','save','restore','clip',
      'moveTo','lineTo','arc','arcTo','ellipse','rect','roundRect','quadraticCurveTo',
      'bezierCurveTo','translate','scale','rotate','transform','setTransform','resetTransform',
      'fillRect','clearRect','strokeRect','fillText','strokeText','setLineDash','getLineDash']) {
      this[m] = (...a) => { REC.ctxCalls++; checkFinite(m, a); };
    }
  }
  get fillStyle() { return this._fillStyle; }
  set fillStyle(v) { checkPaint('fillStyle', v); this._fillStyle = v; }
  get strokeStyle() { return this._strokeStyle; }
  set strokeStyle(v) { checkPaint('strokeStyle', v); this._strokeStyle = v; }

  drawImage(img, ...rest) {
    REC.drawCalls++; REC.ctxCalls++;
    if (img === null || img === undefined) {
      REC.nullImage.push({ where: REC.where, reason: 'nullish source', value: String(img) });
    } else if (typeof img === 'object' && ('width' in img) && (!img.width || !img.height)) {
      REC.nullImage.push({ where: REC.where, reason: 'zero-size source', value: `${img.width}x${img.height}` });
    }
    for (let i = 0; i < rest.length; i++) {
      const v = rest[i];
      if (typeof v !== 'number' || !Number.isFinite(v)) {
        REC.nonFinite.push({ where: REC.where, op: 'drawImage', argIndex: i + 1, value: String(v) });
        break;
      }
    }
  }
  createLinearGradient(...a) { REC.ctxCalls++; checkFinite('createLinearGradient', a); return new Gradient(); }
  createRadialGradient(...a) { REC.ctxCalls++; checkFinite('createRadialGradient', a); return new Gradient(); }
  createPattern() { return new Pattern(); }
  measureText(t) { return { width: String(t == null ? '' : t).length * 6, actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 }; }
  getImageData(x, y, w, h) {
    const W = Math.max(1, Math.floor(w) || 1), H = Math.max(1, Math.floor(h) || 1);
    return { width: W, height: H, data: new Uint8ClampedArray(W * H * 4) };
  }
  putImageData() { REC.ctxCalls++; }
  createImageData(w, h) { return this.getImageData(0, 0, w, h); }
}

class Canvas {
  constructor(w = 300, h = 150) {
    this._w = w; this._h = h; this._ctx = null;
    REC.allocTotal++;
    if (REC.loopDepth > 0) {
      REC.allocInLoop.push({ where: REC.where, stack: new Error().stack.split('\n').slice(2, 5).join(' | ') });
    }
  }
  get width() { return this._w; }
  set width(v) { this._w = v; }
  get height() { return this._h; }
  set height(v) { this._h = v; }
  getContext() { if (!this._ctx) this._ctx = new Ctx(this); return this._ctx; }
  toDataURL() { return 'data:image/png;base64,'; }
  get style() { return (this._style ||= {}); }
  addEventListener() {} removeEventListener() {}
  getBoundingClientRect() { return { x:0, y:0, width:this._w, height:this._h, top:0, left:0, right:this._w, bottom:this._h }; }
}

class El {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.style = {}; this.children = []; this.dataset = {}; this.classList = { add(){}, remove(){}, toggle(){}, contains(){ return false; } }; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { return c; }
  setAttribute() {} getAttribute() { return null; }
  addEventListener() {} removeEventListener() {}
  getBoundingClientRect() { return { x:0,y:0,width:0,height:0,top:0,left:0,right:0,bottom:0 }; }
  remove() {}
}

export function installStub() {
  const doc = {
    createElement(tag) { return String(tag).toLowerCase() === 'canvas' ? new Canvas() : new El(tag); },
    getElementById() { return null },
    querySelector() { return null },
    querySelectorAll() { return [] },
    body: new El('body'),
    documentElement: new El('html'),
    addEventListener() {}, removeEventListener() {},
    createDocumentFragment() { return new El('fragment'); },
  };
  globalThis.document = doc;
  globalThis.HTMLCanvasElement = Canvas;
  globalThis.OffscreenCanvas = Canvas;
  globalThis.Image = Canvas;
  globalThis.window = globalThis;
  globalThis.devicePixelRatio = 2;
  globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
  globalThis.cancelAnimationFrame = () => {};
  globalThis.matchMedia = () => ({ matches: false, addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} });
  if (!globalThis.performance) globalThis.performance = { now: () => Date.now() };
  return { Canvas, Ctx };
}

export function newCanvas(w, h) { const c = new Canvas(w, h); return c; }
export function newCtx(w = 640, h = 360) { return new Canvas(w, h).getContext('2d'); }
export function snapshot() { return JSON.parse(JSON.stringify({
  nullImage: REC.nullImage.length, nonFinite: REC.nonFinite.length,
  badPaint: REC.badPaint.length, allocInLoop: REC.allocInLoop.length,
  allocTotal: REC.allocTotal, drawCalls: REC.drawCalls, ctxCalls: REC.ctxCalls })); }
