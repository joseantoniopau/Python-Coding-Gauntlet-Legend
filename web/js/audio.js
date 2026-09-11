/* Original 80s metal soundtrack, synthesised live in the browser.
 *
 * No samples and no external files — every sound here is built from oscillators,
 * a waveshaper and filtered noise. The goal is the sound of a 1987 cassette: a
 * distorted guitar through a 4x12 cabinet, a galloping rhythm section, harmonised
 * twin leads, and double kick when it matters.
 *
 * Signal chain, which is most of the battle:
 *
 *   sawtooth pair (slightly detuned)
 *        -> pre-gain            drive amount
 *        -> waveshaper          tanh soft clip = valve-ish distortion
 *        -> highpass 90Hz       kill the mud
 *        -> peaking ~1.8kHz     the mid honk a Marshall has
 *        -> lowpass 5.2kHz      speaker cabinet rolloff
 *        -> envelope -> master
 *
 * Palm mutes are the same chain with a fast decay and the lowpass pulled down,
 * which is what a muted string actually does.
 */

const A4 = 440;
const NOTES = { C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, F: 5, 'F#': 6,
                Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11 };

function freq(note) {
  if (!note || note === '-' || note === '.') return 0;
  const m = /^([A-G][#b]?)(\d)$/.exec(note);
  if (!m) return 0;
  const semi = NOTES[m[1]] + (parseInt(m[2], 10) - 4) * 12 - 9;
  return A4 * Math.pow(2, semi / 12);
}

const interval = (note, semitones) => freq(note) * Math.pow(2, semitones / 12);

/* ---------------------------------------------------------------- tracks
 *
 * Each track is a set of parallel lanes read one step at a time. A step is a
 * sixteenth note.
 *
 *   riff   rhythm guitar. A note name plays a POWER CHORD (root+fifth+octave).
 *          'x' is a palm-muted chug on the previous root — the gallop engine.
 *   lead   single-note lead line, harmonised a third above when `harmony` is set.
 *   bass   bass guitar, one octave below the riff root.
 *   drums  k kick · s snare · h closed hat · o open hat · c crash · d double kick
 *
 * All of this is written for this project. Nothing is transcribed from anything.
 */
const TRACKS = {
  // Mid-tempo NWOBHM gallop. E minor, the home key of most of this soundtrack.
  overworld: {
    bpm: 152, drive: 0.55, harmony: 4, feel: 'gallop',
    riff:  'E2 x x E2 x x G2 x  E2 x x D2 x x A2 x  E2 x x E2 x x G2 x  B2 x x A2 x G2 x x',
    lead:  'B4 - - D5 - E5 - -  G5 - E5 - D5 - B4 -  B4 - - D5 - E5 - G5  A5 - G5 - E5 - D5 -',
    bass:  'E1 - E1 - E1 - G1 -  E1 - E1 - D1 - A1 -  E1 - E1 - E1 - G1 -  B1 - B1 - A1 - G1 -',
    drums: 'k h s h k h s h  k h s h k k s h  k h s h k h s h  k h s h k k s c',
  },

  // Clean-channel arpeggios with chorus-style detune. The 1987 power-ballad intro.
  town: {
    bpm: 96, drive: 0.0, clean: true, harmony: 0, feel: 'arpeggio',
    riff:  'A3 - E4 - A4 - E4 -  F3 - C4 - F4 - C4 -  C4 - G4 - C5 - G4 -  G3 - D4 - G4 - D4 -',
    lead:  '- - - - E5 - - -  - - - - A4 - - -  - - - - G5 - - -  - - - - B4 - - -',
    bass:  'A1 - - - - - - -  F1 - - - - - - -  C2 - - - - - - -  G1 - - - - - - -',
    drums: '- - - - - - - -  - - - - - - - -  - - - - - - - -  - - - - - - - -',
  },

  // Doom. Slow, heavy, let the chords ring.
  dungeon: {
    bpm: 88, drive: 0.72, harmony: 3, feel: 'doom',
    riff:  'D2 - - - - - - -  F2 - - - C2 - - -  D2 - - - - - - -  A#1 - - - C2 - - -',
    lead:  '- - - - D4 - F4 -  - - - - A4 - G4 -  - - - - F4 - D4 -  - - - - C4 - D4 -',
    bass:  'D1 - - - D1 - - -  F1 - - - C1 - - -  D1 - - - D1 - - -  A#0 - - - C1 - - -',
    drums: 'k - - - s - - -  k - - - s - - c  k - - - s - - -  k - k - s - - c',
  },

  // Thrash. Downpicked eighths under a frantic lead.
  battle: {
    bpm: 178, drive: 0.82, harmony: 4, feel: 'thrash',
    riff:  'E2 x E2 x E2 x G2 x  E2 x E2 x F2 x E2 x  E2 x E2 x E2 x A2 x  G2 x F2 x E2 x E2 x',
    lead:  'E5 G5 B5 G5 E5 D5 B4 D5  E5 G5 A5 G5 F5 E5 D5 B4  E5 G5 B5 E6 D6 B5 G5 E5  D5 C5 B4 A4 G4 F4 E4 -',
    bass:  'E1 E1 E1 E1 E1 E1 G1 G1  E1 E1 E1 E1 F1 F1 E1 E1  E1 E1 E1 E1 E1 E1 A1 A1  G1 G1 F1 F1 E1 E1 E1 E1',
    drums: 'k h s h k h s h  k h s h k h s h  d h s h d h s h  k h s h k k s c',
  },

  // Neoclassical shred. A harmonic minor, the Malmsteen scale, all diminished menace.
  boss: {
    bpm: 186, drive: 0.9, harmony: 3, feel: 'neoclassical',
    riff:  'A2 x x A2 x x A2 x  F2 x x F2 x G2 x x  A2 x x A2 x x C3 x  E3 x x F2 x E2 x x',
    lead:  'A4 B4 C5 D5 E5 F5 G#5 A5  G#5 F5 E5 D5 C5 B4 A4 G#4  A4 C5 E5 A5 G#5 E5 C5 A4  B4 C5 D5 E5 F5 E5 D5 C5',
    bass:  'A1 A1 A1 A1 A1 A1 A1 A1  F1 F1 F1 F1 G1 G1 G1 G1  A1 A1 A1 A1 C2 C2 C2 C2  E2 E2 E2 E2 F1 F1 E1 E1',
    drums: 'd h s h d h s h  d h s h d h s h  d h s h d h s h  d d s h d d s c',
  },

  // The lap of honour. Big open chords, a triumphant lead, crash on every downbeat.
  victory: {
    bpm: 150, drive: 0.7, harmony: 4, feel: 'anthem',
    riff:  'C3 - - - G2 - - -  A2 - - - F2 - - -  C3 - - - - - - -  - - - - - - - -',
    lead:  'C5 E5 G5 C6 - B5 C6 -  A5 - G5 - F5 - E5 -  G5 - - - C6 - - -  - - - - - - - -',
    bass:  'C2 - C2 - G1 - G1 -  A1 - A1 - F1 - F1 -  C2 - - - C2 - - -  - - - - - - - -',
    drums: 'c h s h c h s h  c h s h c h s h  c d s d c - - -  - - - - - - - -',
  },

  // Training camp. Clean, unhurried, no percussion. Learning should not feel like a fight.
  camp: {
    bpm: 84, drive: 0.0, clean: true, harmony: 0, feel: 'arpeggio',
    riff:  'G3 - D4 - G4 - D4 -  E3 - B3 - E4 - B3 -  C4 - G4 - C5 - G4 -  D4 - A4 - D5 - A4 -',
    lead:  '- - - - - - - -  - - - - G4 - - -  - - - - - - - -  - - - - A4 - B4 -',
    bass:  'G1 - - - - - - -  E1 - - - - - - -  C2 - - - - - - -  D2 - - - - - - -',
    drums: '- - - - - - - -  - - - - - - - -  - - - - - - - -  - - - - - - - -',
  },

  // Memory shrine. Clean harmonics, very sparse.
  shrine: {
    bpm: 72, drive: 0.0, clean: true, harmony: 7, feel: 'arpeggio',
    riff:  'A3 - - E4 - - C4 - - A3 - - - - - -',
    lead:  '- - - - - - A5 - - - E5 - - - - -',
    bass:  'A1 - - - - - F1 - - - - - E1 - - -',
    drums: '- - - - - - - -  - - - - - - - -',
  },

  // Complexity Tower. An ascending sequence that climbs a floor every bar.
  tower: {
    bpm: 164, drive: 0.66, harmony: 3, feel: 'neoclassical',
    riff:  'B2 x x B2 x x D3 x  F#2 x x F#2 x A2 x x  B2 x x D3 x x F#3 x  E3 x x D3 x B2 x x',
    lead:  'B4 C#5 D5 E5 F#5 G5 A5 B5  A5 G5 F#5 E5 D5 C#5 B4 A4  B4 D5 F#5 B5 A5 F#5 D5 B4  C#5 D5 E5 F#5 G5 F#5 E5 D5',
    bass:  'B1 - B1 - B1 - D2 -  F#1 - F#1 - A1 - A1 -  B1 - B1 - D2 - F#2 -  E2 - E2 - D2 - B1 -',
    drums: 'k h s h k h s h  k h s h k d s h  k h s h k h s h  d h s h d d s c',
  },

  // The Null King's castle. Tritones, double kick throughout, no relief.
  final: {
    bpm: 192, drive: 0.95, harmony: 3, feel: 'epic',
    riff:  'C2 x C2 x C2 x F#2 x  C2 x C2 x G#2 x G2 x  C2 x C2 x C2 x D#3 x  F3 x D#3 x C3 x B2 x',
    lead:  'C5 D#5 F5 G5 G#5 G5 F5 D#5  C5 D#5 G5 C6 B5 G5 D#5 C5  G#5 G5 F5 D#5 D5 C5 B4 C5  D#5 F5 G5 G#5 A#5 C6 - -',
    bass:  'C1 C1 C1 C1 C1 C1 F#1 F#1  C1 C1 C1 C1 G#1 G#1 G1 G1  C1 C1 C1 C1 C1 C1 D#2 D#2  F2 F2 D#2 D#2 C2 C2 B1 B1',
    drums: 'd h s h d h s h  d h s h d h s c  d h s h d h s h  d d s d d d s c',
  },
};

/* ---------------------------------------------------------------- engine */

class MetalRig {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.cab = null;          // the shared cabinet chain guitars run through
    this.shaper = null;
    this.preGain = null;
    this.enabled = true;
    this.current = null;
    this.timer = null;
    this.step = 0;
    this.intensity = 0;
    this.volume = 0.2;
    this.lastRoot = 'E2';
  }

  /* A tanh-ish soft clip. Higher `drive` is more gain before the valves give up. */
  _curve(drive) {
    const n = 1024;
    const curve = new Float32Array(n);
    const k = 1 + drive * 40;
    for (let i = 0; i < n; i++) {
      const x = (i * 2) / n - 1;
      curve[i] = Math.tanh(k * x) / Math.tanh(k);
    }
    return curve;
  }

  _ensure() {
    if (this.ctx) return true;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return false;
    const ctx = new Ctor();
    this.ctx = ctx;

    this.master = ctx.createGain();
    this.master.gain.value = this.volume;
    this.master.connect(ctx.destination);

    // --- the cabinet. Everything distorted goes through this.
    this.preGain = ctx.createGain();
    this.preGain.gain.value = 1;

    this.shaper = ctx.createWaveShaper();
    this.shaper.curve = this._curve(0.6);
    this.shaper.oversample = '4x';

    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = 90;          // strip the mud a distorted saw produces

    const mid = ctx.createBiquadFilter();
    mid.type = 'peaking';
    mid.frequency.value = 1800;       // the mid honk of a 4x12
    mid.Q.value = 0.9;
    mid.gain.value = 7;

    const scoop = ctx.createBiquadFilter();
    scoop.type = 'peaking';
    scoop.frequency.value = 500;
    scoop.Q.value = 1.1;
    scoop.gain.value = -4;            // the classic scooped-mid metal EQ

    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 5200;        // speakers simply do not pass much above this
    lp.Q.value = 0.7;

    this.cabIn = this.preGain;
    this.preGain.connect(this.shaper);
    this.shaper.connect(hp);
    hp.connect(scoop);
    scoop.connect(mid);
    mid.connect(lp);
    lp.connect(this.master);

    // --- a clean channel for the arpeggiated tracks
    this.cleanIn = ctx.createGain();
    this.cleanIn.gain.value = 1;
    const cleanLp = ctx.createBiquadFilter();
    cleanLp.type = 'lowpass';
    cleanLp.frequency.value = 3600;
    this.cleanIn.connect(cleanLp);
    cleanLp.connect(this.master);

    return true;
  }

  resume() {
    if (this._ensure() && this.ctx.state === 'suspended') this.ctx.resume();
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on) this.stop();
  }

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.master) this.master.gain.value = this.volume;
  }

  /* ---- voices ---- */

  /** One distorted guitar note. Two detuned saws is what makes it sound like a
   *  guitar rather than a synth. */
  _guitarNote(f, when, dur, gain, { clean = false, mute = false, bend = 0 } = {}) {
    if (!f) return;
    const ctx = this.ctx;
    const dest = clean ? this.cleanIn : this.cabIn;
    const env = ctx.createGain();

    const attack = mute ? 0.002 : 0.006;
    const peak = mute ? gain * 0.8 : gain;
    env.gain.setValueAtTime(0, when);
    env.gain.linearRampToValueAtTime(peak, when + attack);
    if (mute) {
      env.gain.exponentialRampToValueAtTime(0.0001, when + Math.min(dur, 0.09));
    } else {
      env.gain.setValueAtTime(peak, when + attack);
      env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    }

    let tone = env;
    if (mute) {
      // a palm mute is literally a lowpass plus a fast decay
      const muteLp = ctx.createBiquadFilter();
      muteLp.type = 'lowpass';
      muteLp.frequency.value = 900;
      env.connect(muteLp);
      muteLp.connect(dest);
    } else {
      env.connect(dest);
    }

    for (const detune of clean ? [-6, 6] : [-9, 9]) {
      const osc = ctx.createOscillator();
      osc.type = clean ? 'triangle' : 'sawtooth';
      osc.frequency.setValueAtTime(f, when);
      if (bend) {
        osc.frequency.exponentialRampToValueAtTime(
          Math.max(20, f * Math.pow(2, bend / 12)), when + dur);
      }
      osc.detune.value = detune;
      osc.connect(env);
      osc.start(when);
      osc.stop(when + dur + 0.03);
    }
    return tone;
  }

  /** Root + fifth + octave. The power chord: no third, so it is neither major nor
   *  minor, which is exactly why it sits under anything. */
  _powerChord(note, when, dur, gain, opts = {}) {
    const root = freq(note);
    if (!root) return;
    this._guitarNote(root, when, dur, gain, opts);
    this._guitarNote(root * Math.pow(2, 7 / 12), when, dur, gain * 0.75, opts);
    this._guitarNote(root * 2, when, dur, gain * 0.5, opts);
  }

  _bassNote(f, when, dur, gain) {
    if (!f) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sawtooth';
    osc.frequency.value = f;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 420;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, when);
    env.gain.linearRampToValueAtTime(gain, when + 0.012);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    osc.connect(lp); lp.connect(env); env.connect(this.master);
    osc.start(when); osc.stop(when + dur + 0.02);
  }

  _noise(when, dur, gain, { hp = 200, lp = 16000, type = 'white' } = {}) {
    const ctx = this.ctx;
    const frames = Math.max(1, Math.floor(ctx.sampleRate * dur));
    const buf = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < frames; i++) {
      const w = Math.random() * 2 - 1;
      if (type === 'pink') { last = (last + 0.02 * w) / 1.02; data[i] = last * 3.5; }
      else data[i] = w;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const hpf = ctx.createBiquadFilter();
    hpf.type = 'highpass'; hpf.frequency.value = hp;
    const lpf = ctx.createBiquadFilter();
    lpf.type = 'lowpass'; lpf.frequency.value = lp;
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    src.connect(hpf); hpf.connect(lpf); lpf.connect(env); env.connect(this.master);
    src.start(when); src.stop(when + dur);
  }

  /* ---- drums ---- */

  _kick(when, gain = 0.5) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(140, when);
    osc.frequency.exponentialRampToValueAtTime(42, when + 0.09);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.16);
    osc.connect(env); env.connect(this.master);
    osc.start(when); osc.stop(when + 0.18);
    this._noise(when, 0.02, gain * 0.35, { hp: 1200 });   // beater click
  }

  _snare(when, gain = 0.4) {
    this._noise(when, 0.14, gain, { hp: 1400, lp: 9000 });
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(210, when);
    osc.frequency.exponentialRampToValueAtTime(150, when + 0.08);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain * 0.5, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.1);
    osc.connect(env); env.connect(this.master);
    osc.start(when); osc.stop(when + 0.12);
  }

  _hat(when, gain = 0.11, open = false) {
    this._noise(when, open ? 0.2 : 0.035, gain, { hp: 7000, lp: 15000 });
  }

  _crash(when, gain = 0.3) {
    this._noise(when, 1.1, gain, { hp: 3000, lp: 14000, type: 'pink' });
  }

  /* ---- transport ---- */

  play(name) {
    if (!this.enabled || !this._ensure()) return;
    if (this.current === name && this.timer) return;
    this.stop();

    const track = TRACKS[name] || TRACKS.overworld;
    this.current = name;
    this.step = 0;
    this.shaper.curve = this._curve(track.drive || 0.6);
    this.preGain.gain.value = 0.6 + (track.drive || 0.6) * 1.1;

    const riff = track.riff.trim().split(/\s+/);
    const lead = track.lead.trim().split(/\s+/);
    const bass = track.bass.trim().split(/\s+/);
    const drums = track.drums.trim().split(/\s+/);
    const sixteenth = 60 / track.bpm / 4;
    const clean = !!track.clean;
    this.lastRoot = riff.find(t => t !== 'x' && t !== '-') || 'E2';

    const tick = () => {
      if (!this.enabled || !this.ctx) return;
      const t = this.ctx.currentTime + 0.03;
      const i = this.step;
      // intensity is raised as an interview timer runs down: everything gets
      // louder and the lead cuts through harder
      const push = 1 + this.intensity * 0.45;

      const r = riff[i % riff.length];
      if (r === 'x') {
        this._powerChord(this.lastRoot, t, sixteenth * 1.1, 0.12 * push,
                         { mute: true, clean });
      } else if (r !== '-' && r !== '.') {
        this.lastRoot = r;
        this._powerChord(r, t, sixteenth * 3.4, 0.15 * push, { clean });
      }

      const l = lead[i % lead.length];
      if (l !== '-' && l !== '.') {
        const dur = sixteenth * 2.2;
        this._guitarNote(freq(l), t, dur, 0.115 * push, { clean });
        if (track.harmony) {
          // the twin-lead harmony: a second guitar a third or fifth above
          this._guitarNote(interval(l, track.harmony), t, dur, 0.07 * push, { clean });
        }
      }

      const b = bass[i % bass.length];
      if (b !== '-' && b !== '.') {
        this._bassNote(freq(b), t, sixteenth * 2.6, 0.24 * push);
      }

      const d = drums[i % drums.length];
      if (d === 'k') this._kick(t, 0.5 * push);
      else if (d === 'd') { this._kick(t, 0.46 * push); this._kick(t + sixteenth / 2, 0.42 * push); }
      else if (d === 's') { this._snare(t, 0.4 * push); this._hat(t, 0.07); }
      else if (d === 'h') this._hat(t, 0.1 * push);
      else if (d === 'o') this._hat(t, 0.13 * push, true);
      else if (d === 'c') { this._crash(t, 0.3 * push); this._kick(t, 0.45 * push); }

      this.step++;
      this.timer = setTimeout(tick, sixteenth * 1000);
    };
    tick();
  }

  stop() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.current = null;
  }

  setIntensity(v) { this.intensity = Math.max(0, Math.min(1, v)); }

  /* ---- sound effects, in the same idiom ---- */

  sfx(kind) {
    if (!this.enabled || !this._ensure()) return;
    const t = this.ctx.currentTime;
    switch (kind) {
      case 'hit':
        // a muted chug: the sound of a test passing
        this._powerChord('E2', t, 0.12, 0.3, { mute: true });
        this._snare(t, 0.3);
        break;
      case 'crit':
        // pinch harmonic: a squealing high note over a chord stab
        this._powerChord('A2', t, 0.5, 0.32);
        this._guitarNote(freq('A5') * 2, t + 0.02, 0.5, 0.22, { bend: 2 });
        this._crash(t, 0.25);
        break;
      case 'fail':
        // the dive bomb. Whammy bar to the floor.
        this._guitarNote(freq('E4'), t, 0.75, 0.28, { bend: -26 });
        this._kick(t, 0.4);
        break;
      case 'select':
        this._guitarNote(freq('E5'), t, 0.09, 0.14, { clean: true });
        break;
      case 'move':
        this._hat(t, 0.045);
        break;
      case 'spell':
        // an ascending sweep-picked arpeggio
        ['A4', 'C5', 'E5', 'A5', 'C6', 'E6'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.035, 0.28, 0.16));
        break;
      case 'levelup':
        ['C4', 'E4', 'G4', 'C5'].forEach((n, i) =>
          this._powerChord(n.replace(/\d/, m => String(+m - 1)), t + i * 0.11, 0.5, 0.2));
        ['C5', 'E5', 'G5', 'C6', 'E6'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.09, 0.4, 0.18));
        this._crash(t, 0.3);
        break;
      case 'victory':
        ['C3', 'G2', 'A2', 'F2'].forEach((n, i) =>
          this._powerChord(n, t + i * 0.16, 0.7, 0.24));
        ['C5', 'E5', 'G5', 'C6'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.16, 0.5, 0.2));
        this._crash(t, 0.34);
        this._kick(t, 0.5);
        break;
      case 'shrine':
        // natural harmonics, clean channel
        ['A5', 'E6', 'A6'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.14, 0.9, 0.11, { clean: true }));
        break;
      case 'unlock':
        ['G3', 'B3', 'D4', 'G4'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.06, 0.35, 0.16, { clean: true }));
        break;
      case 'armor':
        // an anvil: bright metallic noise over a low thud
        this._noise(t, 0.18, 0.26, { hp: 2500, lp: 12000 });
        this._kick(t, 0.42);
        this._guitarNote(freq('B4'), t + 0.06, 0.3, 0.14);
        break;
      case 'loot':
        ['E5', 'G#5', 'B5', 'E6'].forEach((n, i) =>
          this._guitarNote(freq(n), t + i * 0.055, 0.4, 0.15));
        break;
      case 'boss':
        // the tritone. Nothing announces a boss like a diabolus in musica.
        this._powerChord('C2', t, 1.4, 0.3);
        this._powerChord('F#2', t + 0.16, 1.4, 0.3);
        this._crash(t, 0.36);
        this._kick(t, 0.5); this._kick(t + 0.1, 0.5);
        break;
      case 'tick':
        this._hat(t, 0.06);
        break;
      default:
        this._guitarNote(freq('E5'), t, 0.1, 0.12);
    }
  }
}

export const audio = new MetalRig();
export const TRACK_NAMES = Object.keys(TRACKS);
