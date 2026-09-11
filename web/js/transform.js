/* The transformation — "BY THE SOURCE, I NAME IT."
 *
 * Filmation's He-Man ran the same forty-second transformation in nearly every
 * episode for two seasons, and it never got skipped, because it was the moment
 * the show was actually about. We are borrowing the STRUCTURE of that beat and
 * none of its content: raise, charge, discharge, reveal, hold.
 *
 * It fires on a clutch clear — a hard problem solved unaided, a boss taken down
 * at low health. That timing is the whole point. The sequence is a reward for a
 * thing the player did well, so it has to be gated on evidence rather than on a
 * cooldown, or it becomes an interruption instead of a payoff.
 *
 * See docs/09-story-bible.md §7. Nothing here is copied from any existing work;
 * the beats of a power-up sequence are not ownable, and the art is ours.
 */

import { RAMPS } from './palette.js';

/* Five acts, in seconds from the start. Timings are lifted from how these
 * sequences actually read on screen: the CHARGE is the long one, because
 * anticipation is what makes the discharge land, and the HOLD has to outlast
 * the player's urge to press a key or the payoff gets clipped. */
const ACTS = Object.freeze({
  RAISE:     [0.00, 0.55],
  CHARGE:    [0.55, 1.70],
  DISCHARGE: [1.70, 2.15],
  REVEAL:    [2.15, 3.10],
  HOLD:      [3.10, 4.20],
});
const TOTAL = 4.20;

const PHRASE = 'BY THE SOURCE';
const OATH = 'I NAME IT';

/* Deterministic noise. Math.random() during a cinematic means the sequence looks
 * different every time it replays from the same state, which makes it impossible
 * to tune and impossible to screenshot-test. */
function hash(n) {
  let h = (n * 374761393 + 668265263) >>> 0;
  h = (h ^ (h >>> 13)) >>> 0;
  h = (h * 1274126177) >>> 0;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

const easeOut = t => 1 - Math.pow(1 - t, 3);
const easeIn = t => t * t * t;

/* Where are we inside an act, 0..1, or -1 if the act has not started. */
function actPhase(t, act) {
  const [a, b] = ACTS[act];
  if (t < a) return -1;
  if (t >= b) return 1;
  return (t - a) / (b - a);
}

export class Transformation {
  constructor() {
    this.active = false;
    this.t = 0;
    this.bolts = [];
    this.onDone = null;
    this.title = '';
  }

  /* `title` is the rank the player just earned, shown at the reveal. Passing it
   * in rather than reading it here keeps this module ignorant of game state. */
  begin(title, onDone) {
    this.active = true;
    this.t = 0;
    this.title = (title || 'ARCHITECT').toUpperCase();
    this.onDone = onDone || null;
    this.bolts = [];
    for (let i = 0; i < 14; i++) {
      this.bolts.push({
        angle: (i / 14) * Math.PI * 2 + hash(i) * 0.4,
        delay: hash(i * 7) * 0.5,
        len: 0.55 + hash(i * 13) * 0.45,
        seed: i * 97,
      });
    }
  }

  cancel() {
    if (!this.active) return;
    this.active = false;
    const cb = this.onDone;
    this.onDone = null;
    if (cb) cb();
  }

  /* dt in seconds, clamped by the caller's frame clock. */
  update(dt) {
    if (!this.active) return;
    this.t += dt;
    if (this.t >= TOTAL) this.cancel();
  }

  draw(ctx, w, h) {
    if (!this.active) return;
    const t = this.t;
    const cx = w / 2;
    const ground = h * 0.78;

    this._backdrop(ctx, w, h, t);
    this._beam(ctx, cx, ground, w, h, t);
    this._bolts(ctx, cx, ground, h, t);
    this._figure(ctx, cx, ground, h, t);
    this._flash(ctx, w, h, t);
    this._lettering(ctx, cx, w, h, t);
  }

  /* --- the backdrop drains to black so the figure is the only lit thing. */
  _backdrop(ctx, w, h, t) {
    const charge = actPhase(t, 'CHARGE');
    let dark = 0.55;
    if (charge >= 0) dark = 0.55 + easeIn(charge) * 0.4;
    const rev = actPhase(t, 'REVEAL');
    if (rev >= 0) dark = 0.95 - easeOut(rev) * 0.35;

    ctx.fillStyle = `rgba(4,3,10,${Math.min(0.97, dark)})`;
    ctx.fillRect(0, 0, w, h);

    /* Frazetta keeps one hot source low in the frame and lets everything else
     * fall to near-black. The radial here is that source. */
    const g = ctx.createRadialGradient(w / 2, h * 0.72, 0, w / 2, h * 0.72, h * 0.7);
    const heat = charge >= 0 ? 0.10 + charge * 0.22 : 0.06;
    g.addColorStop(0, `rgba(150,110,255,${heat})`);
    g.addColorStop(0.5, `rgba(70,40,140,${heat * 0.4})`);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }

  /* --- the column of light the figure stands in. */
  _beam(ctx, cx, ground, w, h, t) {
    const charge = actPhase(t, 'CHARGE');
    if (charge < 0) return;
    const disc = actPhase(t, 'DISCHARGE');

    let width = 26 + easeOut(charge) * 40;
    let alpha = 0.30 + charge * 0.45;
    if (disc >= 0) { width += easeOut(disc) * 220; alpha = 0.75 * (1 - disc); }

    const g = ctx.createLinearGradient(0, ground, 0, 0);
    g.addColorStop(0, `rgba(226,214,255,${alpha})`);
    g.addColorStop(0.45, `rgba(150,110,255,${alpha * 0.55})`);
    g.addColorStop(1, 'rgba(90,60,200,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(cx - width * 0.34, 0);
    ctx.lineTo(cx + width * 0.34, 0);
    ctx.lineTo(cx + width, ground);
    ctx.lineTo(cx - width, ground);
    ctx.closePath();
    ctx.fill();

    /* The ground disc, so the beam lands on something instead of stopping. */
    ctx.save();
    ctx.translate(cx, ground);
    ctx.scale(1, 0.22);
    const rg = ctx.createRadialGradient(0, 0, 0, 0, 0, width * 2.4);
    rg.addColorStop(0, `rgba(240,232,255,${alpha * 0.9})`);
    rg.addColorStop(0.6, `rgba(140,100,250,${alpha * 0.3})`);
    rg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = rg;
    ctx.beginPath();
    ctx.arc(0, 0, width * 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  /* --- bolts crawling up into the figure during the charge. */
  _bolts(ctx, cx, ground, h, t) {
    const charge = actPhase(t, 'CHARGE');
    if (charge < 0) return;
    const disc = actPhase(t, 'DISCHARGE');
    const outward = disc >= 0 ? easeOut(disc) : 0;

    ctx.lineCap = 'round';
    for (const b of this.bolts) {
      const p = (charge - b.delay) / Math.max(0.05, 1 - b.delay);
      if (p <= 0) continue;
      const reach = Math.min(1, p) * b.len * (h * 0.34) + outward * h * 0.5;
      const ox = Math.cos(b.angle) * reach;
      const oy = Math.sin(b.angle) * reach * 0.5;
      const sx = cx + ox;
      const sy = ground - h * 0.16 + oy;

      /* Jagged, not straight: three segments with hashed lateral offset. */
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      for (let s = 1; s <= 3; s++) {
        const f = s / 3;
        const jx = (hash(b.seed + s * 31) - 0.5) * 18;
        const jy = (hash(b.seed + s * 57) - 0.5) * 14;
        ctx.lineTo(
          sx + (cx - sx) * f + jx,
          sy + (ground - h * 0.16 - sy) * f + jy,
        );
      }
      const a = Math.min(1, p) * (1 - outward);
      ctx.strokeStyle = `rgba(210,190,255,${a * 0.85})`;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.strokeStyle = `rgba(255,255,255,${a})`;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
  }

  /* --- the silhouette. Read at a glance, in one colour, like a cover painting. */
  _figure(ctx, cx, ground, h, t) {
    const raise = actPhase(t, 'RAISE');
    const rev = actPhase(t, 'REVEAL');
    const disc = actPhase(t, 'DISCHARGE');
    const unit = h * 0.0125;

    /* Arms go up over the RAISE and stay up. */
    const lift = raise < 0 ? 0 : easeOut(raise);
    const bodyH = unit * 22;
    const top = ground - bodyH;

    /* Before the discharge it is a black silhouette with a rim light. After, it
     * is lit from inside — the same pose, a different material. */
    const lit = disc >= 0;
    const rim = RAMPS.chrome[4];
    const body = lit ? RAMPS.violet[3] : '#06060c';

    ctx.save();
    /* The stance widens slightly at the reveal. Small, but it reads as power. */
    const spread = 1 + (rev >= 0 ? easeOut(rev) * 0.12 : 0);
    ctx.translate(cx, 0);
    ctx.scale(spread, 1);

    ctx.fillStyle = body;
    // legs
    ctx.fillRect(-unit * 3.2, ground - unit * 9, unit * 2.4, unit * 9);
    ctx.fillRect(unit * 0.8, ground - unit * 9, unit * 2.4, unit * 9);
    // torso, tapered
    ctx.beginPath();
    ctx.moveTo(-unit * 4.6, top + unit * 5);
    ctx.lineTo(unit * 4.6, top + unit * 5);
    ctx.lineTo(unit * 3.0, ground - unit * 8);
    ctx.lineTo(-unit * 3.0, ground - unit * 8);
    ctx.closePath();
    ctx.fill();
    // head
    ctx.fillRect(-unit * 1.6, top + unit * 1.4, unit * 3.2, unit * 3.6);
    // arms, raised by `lift`
    for (const side of [-1, 1]) {
      const shx = side * unit * 4.2;
      const shy = top + unit * 5.6;
      const hx = shx + side * unit * (2.2 + lift * 1.4);
      const hy = shy - lift * unit * 9;
      ctx.save();
      ctx.lineCap = 'butt';
      ctx.strokeStyle = body;
      ctx.lineWidth = unit * 2.1;
      ctx.beginPath();
      ctx.moveTo(shx, shy);
      ctx.lineTo(hx, hy);
      ctx.stroke();
      ctx.restore();
    }

    /* The rim light. One source, low and to the left, per §8. */
    ctx.strokeStyle = rim;
    ctx.lineWidth = Math.max(1.5, unit * 0.4);
    ctx.globalAlpha = lit ? 1 : 0.75;
    ctx.beginPath();
    ctx.moveTo(-unit * 4.6, top + unit * 5);
    ctx.lineTo(-unit * 3.0, ground - unit * 8);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /* --- the white-out on the discharge frame. */
  _flash(ctx, w, h, t) {
    const disc = actPhase(t, 'DISCHARGE');
    if (disc < 0 || disc >= 1) return;
    /* Peaks fast and falls, rather than fading linearly, so it reads as an
     * impact instead of a dissolve. */
    const a = disc < 0.25 ? disc / 0.25 : 1 - (disc - 0.25) / 0.75;
    ctx.fillStyle = `rgba(255,252,255,${a * 0.92})`;
    ctx.fillRect(0, 0, w, h);
  }

  /* --- the lettering: chrome bevel, hard drop shadow, an album sleeve. */
  _lettering(ctx, cx, w, h, t) {
    const raise = actPhase(t, 'RAISE');
    const rev = actPhase(t, 'REVEAL');
    const size = Math.max(18, Math.round(h * 0.062));

    if (raise >= 0 && rev < 0) {
      this._word(ctx, PHRASE, cx, h * 0.20, size, Math.min(1, raise * 2));
    }
    if (rev >= 0) {
      const a = Math.min(1, rev * 3);
      this._word(ctx, OATH, cx, h * 0.20, size * 1.25, a);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.font = `${Math.round(size * 0.42)}px "Press Start 2P", monospace`;
      ctx.textAlign = 'center';
      ctx.fillStyle = RAMPS.gold[4];
      ctx.fillText(this.title, cx, h * 0.30);
      ctx.restore();
    }
  }

  _word(ctx, text, cx, y, size, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.font = `${size}px "Press Start 2P", monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // hard shadow, offset down-right, the way sleeve lettering is drawn
    ctx.fillStyle = '#0a0410';
    ctx.fillText(text, cx + 4, y + 5);

    // the bevel: a light face over a dark face, one pixel apart
    ctx.fillStyle = RAMPS.chrome[1];
    ctx.fillText(text, cx, y + 2);
    ctx.fillStyle = RAMPS.chrome[4];
    ctx.fillText(text, cx, y);

    ctx.restore();
  }
}

export const TRANSFORM_SECONDS = TOTAL;
