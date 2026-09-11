/* Original chiptune, synthesised in the browser. No samples, no external files.
 *
 * Four voices: two pulse leads, a triangle bass and a noise channel, which is
 * roughly the palette a 16-bit era composer had to work within. Every melody
 * below was written for this project.
 */
const A4 = 440;
const NOTES = { C: 0, 'C#': 1, D: 2, 'D#': 3, E: 4, F: 5, 'F#': 6, G: 7, 'G#': 8, A: 9, 'A#': 10, B: 11 };

function freq(note) {
  if (note === '-') return 0;
  const m = /^([A-G]#?)(\d)$/.exec(note);
  if (!m) return 0;
  const semi = NOTES[m[1]] + (parseInt(m[2], 10) - 4) * 12 - 9;
  return A4 * Math.pow(2, semi / 12);
}

/* Tracks: [lead, harmony, bass] as space-separated note lists; '-' holds. */
const TRACKS = {
  town: {
    bpm: 104, feel: 'gentle',
    lead: 'E4 - G4 - A4 - G4 - C5 - A4 - G4 - E4 - D4 - E4 - G4 - E4 - - - - -',
    harm: 'C4 - E4 - F4 - E4 - A4 - F4 - E4 - C4 - B3 - C4 - E4 - C4 - - - - -',
    bass: 'C2 - - - F2 - - - G2 - - - C2 - - - A2 - - - F2 - - - G2 - - - C2 - - -',
  },
  overworld: {
    bpm: 128, feel: 'bright',
    lead: 'A4 B4 C5 E5 D5 C5 B4 A4 G4 A4 B4 D5 C5 B4 A4 G4 F4 G4 A4 C5 B4 A4 G4 F4 E4 - - - - - - -',
    harm: 'E4 - A4 - C5 - A4 - E4 - G4 - B4 - G4 - D4 - F4 - A4 - F4 - C4 - E4 - - -',
    bass: 'A2 - A2 - F2 - F2 - C2 - C2 - G2 - G2 - A2 - A2 - D2 - D2 - E2 - E2 - - -',
  },
  dungeon: {
    bpm: 96, feel: 'dark',
    lead: 'D4 - F4 - A4 - G4 - F4 - D4 - C4 - D4 - A3 - C4 - D4 - F4 - E4 - - - -',
    harm: 'A3 - D4 - F4 - E4 - D4 - A3 - G3 - A3 - F3 - A3 - A3 - D4 - C4 - - - -',
    bass: 'D2 - - - D2 - - - A1 - - - A1 - - - F2 - - - F2 - - - G2 - - - A2 - - -',
  },
  battle: {
    bpm: 152, feel: 'driving',
    lead: 'E5 E5 - E5 - C5 E5 - G5 - - - G4 - - - C5 - - G4 - - E4 - A4 - B4 - A#4 A4 - -',
    harm: 'C5 C5 - C5 - A4 C5 - E5 - - - E4 - - - A4 - - E4 - - C4 - F4 - G4 - F#4 F4 - -',
    bass: 'E2 - E2 - E2 - E2 - C2 - C2 - G1 - G1 - A1 - A1 - F2 - F2 - E2 - E2 - E2 - E2 -',
  },
  boss: {
    bpm: 164, feel: 'menace',
    lead: 'D5 - C5 - A#4 - A4 - D5 - F5 - E5 - D5 - A4 - A#4 - C5 - D5 - F4 - - - - -',
    harm: 'A4 - G4 - F4 - E4 - A4 - C5 - A#4 - A4 - F4 - G4 - A4 - A#4 - C4 - - - - -',
    bass: 'D2 D2 - D2 D2 - D2 - A#1 A#1 - A#1 A#1 - A#1 - F2 F2 - F2 F2 - F2 - A1 A1 - A1 A1 - A1 -',
  },
  victory: {
    bpm: 140, feel: 'bright',
    lead: 'C5 E5 G5 C6 - G5 C6 - - - - - - - - -',
    harm: 'E4 G4 C5 E5 - C5 E5 - - - - - - - - -',
    bass: 'C2 - G2 - C3 - - - - - - - - - - -',
  },
  camp: {
    bpm: 88, feel: 'gentle',
    lead: 'G4 - A4 - B4 - A4 - G4 - E4 - D4 - E4 - G4 - - - - - - -',
    harm: 'D4 - F4 - G4 - F4 - D4 - C4 - B3 - C4 - D4 - - - - - - -',
    bass: 'G2 - - - E2 - - - C2 - - - D2 - - - G2 - - - - - - -',
  },
  shrine: {
    bpm: 76, feel: 'gentle',
    lead: 'A4 - - E5 - - C5 - - A4 - - B4 - - - ',
    harm: 'E4 - - A4 - - E4 - - C4 - - D4 - - - ',
    bass: 'A2 - - - - - F2 - - - - - E2 - - -',
  },
  tower: {
    bpm: 116, feel: 'bright',
    lead: 'B4 - D5 - F#5 - D5 - B4 - A4 - F#4 - A4 - B4 - D5 - E5 - D5 - B4 - - - - -',
    harm: 'F#4 - B4 - D5 - B4 - F#4 - E4 - C#4 - E4 - F#4 - B4 - C#5 - B4 - F#4 - - - -',
    bass: 'B1 - - - G2 - - - E2 - - - F#2 - - - B1 - - - E2 - - - F#2 - - - B1 - - -',
  },
  final: {
    bpm: 156, feel: 'menace',
    lead: 'C5 - B4 - C5 - D#5 - C5 - G4 - G#4 - A#4 - C5 - D#5 - F5 - D#5 - C5 - - - - -',
    harm: 'G4 - F#4 - G4 - A#4 - G4 - D#4 - E4 - F#4 - G4 - A#4 - C5 - A#4 - G4 - - - -',
    bass: 'C2 C2 - C2 - G1 C2 - G#1 G#1 - G#1 - D#1 G#1 - A#1 A#1 - A#1 - F1 A#1 - C2 - - - - - - -',
  },
};

class Chip {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.enabled = true;
    this.current = null;
    this.timer = null;
    this.step = 0;
    this.intensity = 0;   // 0..1, raised when a timer is running out
    this.volume = 0.22;
  }

  _ensure() {
    if (this.ctx) return true;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return false;
    this.ctx = new Ctor();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.volume;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 7200;   // takes the glassy edge off raw square waves
    this.master.connect(filter);
    filter.connect(this.ctx.destination);
    return true;
  }

  resume() {
    if (this._ensure() && this.ctx.state === 'suspended') this.ctx.resume();
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on) this.stop();
  }

  _pulse(f, when, dur, gain, duty = 0.5, detune = 0) {
    if (!f) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const real = new Float32Array(16);
    const imag = new Float32Array(16);
    for (let n = 1; n < 16; n++) {
      imag[n] = (2 / (n * Math.PI)) * Math.sin(n * Math.PI * duty);
    }
    osc.setPeriodicWave(ctx.createPeriodicWave(real, imag));
    osc.frequency.value = f;
    osc.detune.value = detune;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, when);
    env.gain.linearRampToValueAtTime(gain, when + 0.008);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    osc.connect(env); env.connect(this.master);
    osc.start(when); osc.stop(when + dur + 0.02);
  }

  _tri(f, when, dur, gain) {
    if (!f) return;
    const osc = this.ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.value = f;
    const env = this.ctx.createGain();
    env.gain.setValueAtTime(0, when);
    env.gain.linearRampToValueAtTime(gain, when + 0.01);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    osc.connect(env); env.connect(this.master);
    osc.start(when); osc.stop(when + dur + 0.02);
  }

  _noise(when, dur, gain, hp = 900) {
    const frames = Math.max(1, Math.floor(this.ctx.sampleRate * dur));
    const buf = this.ctx.createBuffer(1, frames, this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const filt = this.ctx.createBiquadFilter();
    filt.type = 'highpass'; filt.frequency.value = hp;
    const env = this.ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    src.connect(filt); filt.connect(env); env.connect(this.master);
    src.start(when); src.stop(when + dur);
  }

  play(name) {
    if (!this.enabled || !this._ensure()) return;
    if (this.current === name && this.timer) return;
    this.stop();
    const track = TRACKS[name] || TRACKS.overworld;
    this.current = name;
    this.step = 0;
    const lead = track.lead.trim().split(/\s+/);
    const harm = track.harm.trim().split(/\s+/);
    const bass = track.bass.trim().split(/\s+/);
    const beat = 60 / track.bpm / 2;

    const tick = () => {
      if (!this.enabled || !this.ctx) return;
      const t = this.ctx.currentTime + 0.02;
      const i = this.step;
      const boost = 1 + this.intensity * 0.5;
      const l = lead[i % lead.length];
      const h = harm[i % harm.length];
      const b = bass[i % bass.length];
      const duty = track.feel === 'menace' ? 0.25 : track.feel === 'driving' ? 0.35 : 0.5;
      if (l !== '-') this._pulse(freq(l), t, beat * 1.7, 0.16 * boost, duty);
      if (h !== '-') this._pulse(freq(h), t, beat * 1.5, 0.085 * boost, 0.5, 6);
      if (b !== '-') this._tri(freq(b), t, beat * 1.9, 0.2 * boost);
      const percussive = track.feel === 'driving' || track.feel === 'menace';
      if (percussive && i % 4 === 0) this._noise(t, 0.05, 0.12 * boost, 400);
      if (percussive && i % 4 === 2) this._noise(t, 0.03, 0.07 * boost, 3000);
      if (this.intensity > 0.6 && i % 2 === 1) this._noise(t, 0.02, 0.05, 5000);
      this.step++;
      this.timer = setTimeout(tick, beat * 1000);
    };
    tick();
  }

  stop() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.current = null;
  }

  setIntensity(v) { this.intensity = Math.max(0, Math.min(1, v)); }

  /* ---- sound effects ---- */
  sfx(kind) {
    if (!this.enabled || !this._ensure()) return;
    const t = this.ctx.currentTime;
    switch (kind) {
      case 'hit':
        this._noise(t, 0.07, 0.28, 700);
        this._pulse(180, t, 0.09, 0.2, 0.25);
        break;
      case 'crit':
        this._noise(t, 0.1, 0.3, 500);
        [520, 660, 880].forEach((f, i) => this._pulse(f, t + i * 0.03, 0.1, 0.2, 0.25));
        break;
      case 'fail':
        [330, 260, 200].forEach((f, i) => this._pulse(f, t + i * 0.07, 0.13, 0.16, 0.5));
        break;
      case 'select':
        this._pulse(880, t, 0.05, 0.12, 0.25);
        break;
      case 'move':
        this._pulse(520, t, 0.03, 0.05, 0.25);
        break;
      case 'spell':
        for (let i = 0; i < 6; i++) this._pulse(440 + i * 110, t + i * 0.02, 0.1, 0.1, 0.5);
        break;
      case 'levelup':
        ['C5', 'E5', 'G5', 'C6', 'E6'].forEach((n, i) =>
          this._pulse(freq(n), t + i * 0.08, 0.22, 0.2, 0.35));
        break;
      case 'victory':
        ['C5', 'E5', 'G5', 'C6'].forEach((n, i) =>
          this._pulse(freq(n), t + i * 0.09, 0.28, 0.22, 0.4));
        this._tri(freq('C3'), t, 0.9, 0.2);
        break;
      case 'shrine':
        ['A4', 'C#5', 'E5', 'A5'].forEach((n, i) =>
          this._tri(freq(n), t + i * 0.1, 0.5, 0.14));
        break;
      case 'unlock':
        ['G4', 'B4', 'D5', 'G5'].forEach((n, i) =>
          this._pulse(freq(n), t + i * 0.06, 0.18, 0.16, 0.3));
        break;
      case 'armor':
        this._noise(t, 0.12, 0.2, 2200);
        this._tri(freq('E3'), t, 0.25, 0.18);
        this._pulse(freq('B4'), t + 0.1, 0.15, 0.14, 0.4);
        break;
      case 'tick':
        this._pulse(1200, t, 0.02, 0.06, 0.2);
        break;
      default:
        this._pulse(660, t, 0.05, 0.1, 0.3);
    }
  }
}

export const audio = new Chip();
