/* Original 80s heavy metal, synthesised live. No samples, no external files.
 *
 * The previous version sounded wrong for two reasons, and tone was the smaller
 * of them.
 *
 * 1. SCHEDULING. It sequenced with setTimeout, which drifts four to fifteen
 *    milliseconds a tick and is throttled in a background tab. Metal is built on
 *    rhythmic tightness — a gallop that wobbles reads as "not metal" long before
 *    anyone questions the guitar tone. This version uses the standard lookahead
 *    scheduler: a coarse timer wakes up every 25ms and schedules every event due
 *    in the next 120ms against the audio clock, which is sample-accurate.
 *
 * 2. ONE SHARED AMP. Every voice ran into a single waveshaper, so the rhythm
 *    chords, the lead and the harmony intermodulated into mush. A real rig has
 *    separate channels. This one has four: rhythm guitar, lead guitar, bass and
 *    drums, each with its own gain staging, and a master bus with a compressor
 *    doing the glue a mix engineer would.
 *
 * Signal chain per guitar channel:
 *   2-3 detuned sawtooth -> pre-gain -> waveshaper (asymmetric soft clip)
 *     -> highpass 80Hz  (strip the flub a distorted saw makes)
 *     -> peaking 700Hz -6dB  (the scooped mid)
 *     -> peaking 2.4kHz +6dB (the bite that cuts through a mix)
 *     -> lowpass 6kHz Q0.9   (the 4x12 cabinet rolloff)
 *     -> channel gain -> master compressor -> out
 */

const A4 = 440;
const NOTES = { C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, F: 5, 'F#': 6,
                Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11 };

function freq(note) {
  if (!note || note === '-' || note === '.') return 0;
  const m = /^([A-G][#b]?)(-?\d)$/.exec(note);
  if (!m) return 0;
  const semi = NOTES[m[1]] + (parseInt(m[2], 10) - 4) * 12 - 9;
  return A4 * Math.pow(2, semi / 12);
}

const up = (note, semis) => freq(note) * Math.pow(2, semis / 12);

/* ------------------------------------------------------------------ songs
 *
 * Lanes are read one sixteenth at a time.
 *   riff   rhythm guitar. A note plays a POWER CHORD (root + fifth + octave).
 *          'x' is a palm-muted chug on the last root — the gallop engine.
 *          '>' is an accented open chord that rings.
 *   lead   single-note lead, harmonised when `harmony` is set.
 *   bass   bass guitar.
 *   drums  k kick · K hard kick · s snare · S rimshot · h hat · H open hat
 *          c crash · t tom · d double-kick pair · - rest
 *
 * Every note of this was written for this project.
 */
const TRACKS = {
  /* Mid-tempo gallop in E minor. The overworld of a 1987 record. */
  overworld: {
    bpm: 148, drive: 0.62, harmony: 4, lead_duty: 0.32, rhythm_duty: 0.42,
    riff:  'E2 x x E2 x x G2 x  E2 x x D2 x x A2 x  E2 x x E2 x x G2 x  B2 x A2 x G2 x E2 x',
    lead:  '-  -  -  B4 - D5 -  -  G5 - E5 - D5 - B4 -  -  -  -  D5 - E5 - G5  A5 - G5 - E5 - D5 -',
    bass:  'E1 -  E1 E1 -  E1 G1 -  E1 -  E1 E1 D1 -  A1 -  E1 -  E1 E1 -  E1 G1 -  B1 -  A1 -  G1 -  E1 -',
    drums: 'K h s h k h s h  K h s h d d s h  K h s h k h s h  K h s h d d s c',
  },

  /* Clean channel. The ballad intro every one of these records has. */
  town: {
    bpm: 92, drive: 0, clean: true, harmony: 0,
    riff:  'A3 -  -  E4 -  -  A4 -  -  E4 -  -  C5 -  -  -  F3 -  -  C4 -  -  F4 -  -  C4 -  -  A4 -  -  -',
    lead:  '-  -  -  -  -  -  -  -  E5 -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  A4 -  -  -  C5 -  -  -',
    bass:  'A1 -  -  -  -  -  -  -  A1 -  -  -  -  -  -  -  F1 -  -  -  -  -  -  -  F1 -  -  -  -  -  -  -',
    drums: '-  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -',
  },

  /* Doom. Slow, crushing, let it ring. */
  dungeon: {
    bpm: 84, drive: 0.78, harmony: 3, rhythm_duty: 0.46,
    riff:  '>D2 -  -  -  -  -  -  -  >F2 -  -  -  >C2 -  -  -  >D2 -  -  -  -  -  -  -  >A#1 - - - >C2 - - -',
    lead:  '-  -  -  -  D4 -  F4 -  -  -  -  -  A4 -  G4 -  -  -  -  -  F4 -  D4 -  -  -  -  -  C4 -  D4 -',
    bass:  'D1 -  -  -  D1 -  -  -  F1 -  -  -  C1 -  -  -  D1 -  -  -  D1 -  -  -  A#0 - - - C1 -  -  -',
    drums: 'K -  -  -  s -  -  t  K -  -  -  s -  -  c  K -  -  -  s -  -  t  K -  K -  s -  t c',
  },

  /* Thrash. Downpicked sixteenths, a frantic lead over the top. */
  battle: {
    bpm: 176, drive: 0.86, harmony: 4, lead_duty: 0.3, rhythm_duty: 0.38,
    riff:  'E2 x x x E2 x G2 x  E2 x x x F2 x E2 x  E2 x x x E2 x A2 x  G2 x F2 x E2 x E2 x',
    lead:  'E5 G5 B5 G5 E5 D5 B4 D5  E5 G5 A5 G5 F5 E5 D5 B4  E5 G5 B5 E6 D6 B5 G5 E5  D5 C5 B4 A4 G4 F4 E4 -',
    bass:  'E1 E1 E1 E1 E1 E1 G1 G1  E1 E1 E1 E1 F1 F1 E1 E1  E1 E1 E1 E1 E1 E1 A1 A1  G1 G1 F1 F1 E1 E1 E1 E1',
    drums: 'd h s h d h s h  d h s h d h s h  d h s h d h s h  d d s h d d s c',
  },

  /* Neoclassical. A harmonic minor, every diminished interval it owns. */
  boss: {
    bpm: 184, drive: 0.9, harmony: 3, lead_duty: 0.28, rhythm_duty: 0.36,
    riff:  'A2 x x A2 x x A2 x  F2 x x F2 x G2 x x  A2 x x A2 x x C3 x  E3 x x F2 x E2 x x',
    lead:  'A4 B4 C5 D5 E5 F5 G#5 A5  G#5 F5 E5 D5 C5 B4 A4 G#4  A4 C5 E5 A5 G#5 E5 C5 A4  B4 C5 D5 E5 F5 E5 D5 C5',
    bass:  'A1 A1 A1 A1 A1 A1 A1 A1  F1 F1 F1 F1 G1 G1 G1 G1  A1 A1 A1 A1 C2 C2 C2 C2  E2 E2 E2 E2 F1 F1 E1 E1',
    drums: 'd h S h d h s h  d h S h d h s h  d h S h d h s h  d d s t d d s c',
  },

  /* The lap of honour. */
  victory: {
    bpm: 148, drive: 0.72, harmony: 4,
    riff:  '>C3 -  -  -  >G2 -  -  -  >A2 -  -  -  >F2 -  -  -  >C3 -  -  -  -  -  -  -  -  -  -  -  -  -  -  -',
    lead:  'C5 E5 G5 C6 -  B5 C6 -  A5 -  G5 -  F5 -  E5 -  G5 -  -  -  C6 -  -  -  -  -  -  -  -  -  -  -',
    bass:  'C2 -  C2 -  G1 -  G1 -  A1 -  A1 -  F1 -  F1 -  C2 -  -  -  C2 -  -  -  -  -  -  -  -  -  -  -',
    drums: 'c h s h c h s h  c h s h c h s h  c d s d c -  -  -  -  -  -  -  -  -  -  -',
  },

  /* Training camp. Clean, unhurried, no drums. Learning is not a fight. */
  camp: {
    bpm: 80, drive: 0, clean: true, harmony: 0,
    riff:  'G3 -  D4 -  G4 -  D4 -  E3 -  B3 -  E4 -  B3 -  C4 -  G4 -  C5 -  G4 -  D4 -  A4 -  D5 -  A4 -',
    lead:  '-  -  -  -  -  -  -  -  -  -  -  -  G4 -  -  -  -  -  -  -  -  -  -  -  -  -  A4 -  B4 -  -  -',
    bass:  'G1 -  -  -  -  -  -  -  E1 -  -  -  -  -  -  -  C2 -  -  -  -  -  -  -  D2 -  -  -  -  -  -  -',
    drums: '-  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -',
  },

  /* Memory shrine. Natural harmonics, very sparse. */
  shrine: {
    bpm: 70, drive: 0, clean: true, harmony: 7,
    riff:  'A3 -  -  -  E4 -  -  -  C4 -  -  -  A3 -  -  -',
    lead:  '-  -  -  -  -  -  A5 -  -  -  -  -  E5 -  -  -',
    bass:  'A1 -  -  -  -  -  -  -  F1 -  -  -  E1 -  -  -',
    drums: '-  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -',
  },

  /* Complexity Tower. An ascending sequence that climbs a floor per bar. */
  tower: {
    bpm: 160, drive: 0.68, harmony: 3, rhythm_duty: 0.4,
    riff:  'B2 x x B2 x x D3 x  F#2 x x F#2 x A2 x x  B2 x x D3 x x F#3 x  E3 x x D3 x B2 x x',
    lead:  'B4 C#5 D5 E5 F#5 G5 A5 B5  A5 G5 F#5 E5 D5 C#5 B4 A4  B4 D5 F#5 B5 A5 F#5 D5 B4  C#5 D5 E5 F#5 G5 F#5 E5 D5',
    bass:  'B1 -  B1 -  B1 -  D2 -  F#1 -  F#1 -  A1 -  A1 -  B1 -  B1 -  D2 -  F#2 -  E2 -  E2 -  D2 -  B1 -',
    drums: 'K h s h k h s h  K h s h d d s h  K h s h k h s h  d h s h d d s c',
  },

  /* The castle. Tritones, double kick throughout, no relief. */
  final: {
    bpm: 190, drive: 0.95, harmony: 3, lead_duty: 0.26, rhythm_duty: 0.34,
    riff:  'C2 x C2 x C2 x F#2 x  C2 x C2 x G#2 x G2 x  C2 x C2 x C2 x D#3 x  F3 x D#3 x C3 x B2 x',
    lead:  'C5 D#5 F5 G5 G#5 G5 F5 D#5  C5 D#5 G5 C6 B5 G5 D#5 C5  G#5 G5 F5 D#5 D5 C5 B4 C5  D#5 F5 G5 G#5 A#5 C6 -  -',
    bass:  'C1 C1 C1 C1 C1 C1 F#1 F#1  C1 C1 C1 C1 G#1 G#1 G1 G1  C1 C1 C1 C1 C1 C1 D#2 D#2  F2 F2 D#2 D#2 C2 C2 B1 B1',
    drums: 'd h S h d h s h  d h S h d h s c  d h S h d h s h  d d S d d d s c',
  },
};

/* ------------------------------------------------------------------ engine */

const LOOKAHEAD_MS = 25;      // how often the scheduler wakes
const SCHEDULE_AHEAD = 0.12;  // how far ahead it writes, in seconds

class MetalRig {
  constructor() {
    this.ctx = null;
    this.ready = false;
    this.enabled = true;
    this.masterVol = 0.7;
    this.musicVol = 0.55;
    this.sfxVol = 0.8;
    this.current = null;
    this.track = null;
    this.step = 0;
    this.nextNoteTime = 0;
    this.timer = null;
    this.intensity = 0;
    this.lastRoot = 'E2';
  }

  /* Asymmetric soft clip. Asymmetry is what puts even harmonics in, which is
   * the difference between a valve amp and a fuzz pedal. */
  _curve(drive) {
    const n = 2048;
    const curve = new Float32Array(n);
    const k = 1 + drive * 60;
    for (let i = 0; i < n; i++) {
      const x = (i * 2) / n - 1;
      const bias = x > 0 ? 1 : 0.82;          // squash the negative half less
      curve[i] = Math.tanh(k * x * bias) / Math.tanh(k);
    }
    return curve;
  }

  /* One guitar channel: gain staging, distortion, cabinet. */
  _channel(ctx, dest, { drive, presence, level, cut }) {
    const input = ctx.createGain();
    input.gain.value = 1;

    const pre = ctx.createGain();
    pre.gain.value = 1.2 + drive * 2.6;

    const shaper = ctx.createWaveShaper();
    shaper.curve = this._curve(drive);
    shaper.oversample = '4x';

    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass'; hp.frequency.value = 80;

    const scoop = ctx.createBiquadFilter();
    scoop.type = 'peaking'; scoop.frequency.value = 700;
    scoop.Q.value = 1.0; scoop.gain.value = -6;

    const bite = ctx.createBiquadFilter();
    bite.type = 'peaking'; bite.frequency.value = presence;
    bite.Q.value = 1.1; bite.gain.value = 6;

    const cab = ctx.createBiquadFilter();
    cab.type = 'lowpass'; cab.frequency.value = cut;
    cab.Q.value = 0.9;

    const out = ctx.createGain();
    out.gain.value = level;

    input.connect(pre); pre.connect(shaper); shaper.connect(hp);
    hp.connect(scoop); scoop.connect(bite); bite.connect(cab);
    cab.connect(out); out.connect(dest);
    return { input, out, shaper, pre };
  }

  _build() {
    if (this.ready) return true;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return false;
    const ctx = new Ctor();
    this.ctx = ctx;

    // --- master bus: compressor for glue, then the master fader
    this.master = ctx.createGain();
    this.master.gain.value = this.masterVol;

    this.glue = ctx.createDynamicsCompressor();
    this.glue.threshold.value = -14;
    this.glue.knee.value = 8;
    this.glue.ratio.value = 4;
    this.glue.attack.value = 0.004;
    this.glue.release.value = 0.18;

    this.glue.connect(this.master);
    this.master.connect(ctx.destination);

    // --- two submixes so the player can balance them independently
    this.musicBus = ctx.createGain();
    this.musicBus.gain.value = this.musicVol;
    this.musicBus.connect(this.glue);

    this.sfxBus = ctx.createGain();
    this.sfxBus.gain.value = this.sfxVol;
    this.sfxBus.connect(this.glue);

    // --- channels
    this.rhythm = this._channel(ctx, this.musicBus,
      { drive: 0.7, presence: 2200, level: 0.30, cut: 5600 });
    this.lead = this._channel(ctx, this.musicBus,
      { drive: 0.62, presence: 2800, level: 0.20, cut: 7000 });
    this.cleanCh = ctx.createGain();
    this.cleanCh.gain.value = 0.26;
    const cleanTone = ctx.createBiquadFilter();
    cleanTone.type = 'lowpass'; cleanTone.frequency.value = 4200;
    this.cleanCh.connect(cleanTone); cleanTone.connect(this.musicBus);

    this.bassCh = ctx.createGain();
    this.bassCh.gain.value = 0.42;
    const bassShaper = ctx.createWaveShaper();
    bassShaper.curve = this._curve(0.25);           // a little grit, not fuzz
    const bassLp = ctx.createBiquadFilter();
    bassLp.type = 'lowpass'; bassLp.frequency.value = 900;
    const bassHp = ctx.createBiquadFilter();
    bassHp.type = 'highpass'; bassHp.frequency.value = 38;
    this.bassCh.connect(bassShaper); bassShaper.connect(bassLp);
    bassLp.connect(bassHp); bassHp.connect(this.musicBus);

    this.drumCh = ctx.createGain();
    this.drumCh.gain.value = 0.5;
    this.drumCh.connect(this.musicBus);

    // --- a short slapback on the lead, the way every one of these records has
    this.delay = ctx.createDelay(0.5);
    this.delay.delayTime.value = 0.19;
    const fb = ctx.createGain();
    fb.gain.value = 0.22;
    const wet = ctx.createGain();
    wet.gain.value = 0.16;
    this.lead.out.connect(this.delay);
    this.delay.connect(fb); fb.connect(this.delay);
    this.delay.connect(wet); wet.connect(this.musicBus);

    this.ready = true;
    return true;
  }

  resume() {
    if (this._build() && this.ctx.state === 'suspended') this.ctx.resume();
  }

  /* ------------------------------------------------------- sample layer
   *
   * Entirely optional. The rig synthesises everything, so the game ships with no
   * audio files and works offline. If web/audio/manifest.json declares samples,
   * they are preferred for the entries they cover and synthesis fills the rest.
   *
   * The loader REFUSES any entry that does not record a licence and a source.
   * Audio whose provenance cannot be stated is the one thing here that would be
   * genuinely expensive to get wrong, so the check is in the code rather than in
   * a README nobody reads.
   */
  async loadSamples(base = '/audio/') {
    if (!this._build()) return { loaded: 0, refused: [] };
    this.samples = this.samples || new Map();
    let manifest;
    try {
      const res = await fetch(base + 'manifest.json', { cache: 'no-cache' });
      if (!res.ok) return { loaded: 0, refused: [] };
      manifest = await res.json();
    } catch (err) {
      return { loaded: 0, refused: [] };      // no manifest is a normal state
    }

    const refused = [];
    let loaded = 0;
    for (const entry of (manifest.samples || [])) {
      if (!entry || !entry.file) continue;
      if (!entry.licence || !entry.source) {
        refused.push(`${entry.file}: no ${!entry.licence ? 'licence' : 'source'} recorded`);
        continue;
      }
      try {
        const res = await fetch(base + entry.file);
        if (!res.ok) { refused.push(`${entry.file}: HTTP ${res.status}`); continue; }
        const bytes = await res.arrayBuffer();
        const buffer = await this.ctx.decodeAudioData(bytes);
        this.samples.set(entry.id || entry.file.replace(/\.[^.]+$/, ''), {
          buffer, licence: entry.licence, source: entry.source,
          root: entry.root_note ? freq(entry.root_note) : null,
        });
        loaded++;
      } catch (err) {
        refused.push(`${entry.file}: ${err.message}`);
      }
    }
    this.sampleReport = { loaded, refused, total: (manifest.samples || []).length };
    return this.sampleReport;
  }

  /** Play a loaded sample, pitch-shifted from its recorded root if it has one.
   *  Returns false when the sample is absent, which is the caller's cue to
   *  synthesise instead. */
  _sample(id, when, gain, { pitch = null, dest = null, dur = null } = {}) {
    const entry = this.samples && this.samples.get(id);
    if (!entry) return false;
    const src = this.ctx.createBufferSource();
    src.buffer = entry.buffer;
    if (pitch && entry.root) src.playbackRate.value = pitch / entry.root;
    const env = this.ctx.createGain();
    env.gain.setValueAtTime(Math.max(0.0001, gain), when);
    if (dur) env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    src.connect(env);
    env.connect(dest || this.musicBus);
    src.start(when);
    if (dur) src.stop(when + dur + 0.05);
    return true;
  }

  sampleCredits() {
    if (!this.samples || !this.samples.size) return [];
    return [...this.samples.entries()].map(([id, s]) =>
      ({ id, licence: s.licence, source: s.source }));
  }

  /* ---- mixer, which the settings panel drives ---- */
  setMaster(v) {
    this.masterVol = Math.max(0, Math.min(1, v));
    if (this.master) this.master.gain.value = this.masterVol;
  }

  setMusic(v) {
    this.musicVol = Math.max(0, Math.min(1, v));
    if (this.musicBus) this.musicBus.gain.value = this.musicVol;
  }

  setSfx(v) {
    this.sfxVol = Math.max(0, Math.min(1, v));
    if (this.sfxBus) this.sfxBus.gain.value = this.sfxVol;
  }

  levels() {
    return { master: this.masterVol, music: this.musicVol, sfx: this.sfxVol };
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on) this.stop();
  }

  setIntensity(v) { this.intensity = Math.max(0, Math.min(1, v)); }

  /* --------------------------------------------------- the string model
   *
   * Karplus-Strong: excite a delay line one period long with a noise burst,
   * then feed it back through a one-pole lowpass. The noise decorrelates into a
   * harmonic series, the lowpass rolls the highs off faster than the
   * fundamental, and what comes out has a pick attack and a decay envelope that
   * no oscillator produces. This is the single biggest thing separating "guitar"
   * from "buzzy synth", and it costs a few thousand samples of arithmetic.
   *
   * Buffers are cached by rounded pitch and character, so a whole song builds
   * perhaps forty of them and then allocates nothing.
   */
  _string(f, seconds, { damping = 0.5, brightness = 0.5, pick = 0.5 } = {}) {
    const ctx = this.ctx;
    const key = `${Math.round(f * 4)}:${Math.round(seconds * 40)}:` +
                `${Math.round(damping * 20)}:${Math.round(brightness * 20)}`;
    if (!this._strings) this._strings = new Map();
    const hit = this._strings.get(key);
    if (hit) return hit;

    const rate = ctx.sampleRate;
    const n = Math.max(1, Math.ceil(rate * seconds));
    const period = Math.max(2, Math.floor(rate / Math.max(20, f)));
    const buf = ctx.createBuffer(1, n, rate);
    const out = buf.getChannelData(0);

    // The excitation. A pure noise burst is a banjo; low-passing it toward the
    // pick position is what makes it a plucked steel string.
    const line = new Float32Array(period);
    let smooth = 0;
    const pickTone = 0.25 + brightness * 0.6;
    for (let i = 0; i < period; i++) {
      const white = Math.random() * 2 - 1;
      smooth += (white - smooth) * pickTone;
      line[i] = smooth;
    }
    // a little DC removal, or the string thumps
    let mean = 0;
    for (let i = 0; i < period; i++) mean += line[i];
    mean /= period;
    for (let i = 0; i < period; i++) line[i] -= mean;

    // The loop. `decay` under 1 is what makes a note end; higher pitches damp
    // faster in a real string, which the period-relative term below models.
    const decay = 1 - (0.0009 + damping * 0.010) * (rate / 44100);
    const bright = 0.5 - brightness * 0.22;     // one-pole coefficient
    let idx = 0, prev = 0;
    for (let i = 0; i < n; i++) {
      const current = line[idx];
      const filtered = (current * (1 - bright)) + (prev * bright);
      prev = filtered;
      line[idx] = filtered * decay;
      out[i] = current;
      idx = (idx + 1) % period;
    }

    // a short fade so a truncated buffer does not click
    const fade = Math.min(400, Math.floor(n * 0.05));
    for (let i = 0; i < fade; i++) out[n - 1 - i] *= i / fade;

    if (this._strings.size > 220) this._strings.clear();
    this._strings.set(key, buf);
    return buf;
  }

  /* ---- voices. Every one takes an absolute `when` from the audio clock. ---- */

  _guitar(f, when, dur, gain, { channel, duty = 0.4, mute = false, bend = 0,
                                voices = 2 } = {}) {
    if (!f || !this.ctx) return;
    const ctx = this.ctx;
    const env = ctx.createGain();
    const peak = Math.max(0.0001, gain);
    // A bend needs a continuously variable pitch, so those notes stay on
    // oscillators; everything else gets the string model.
    const useString = !bend;

    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(peak, when + 0.004);
    if (mute) {
      // a palm mute is a fast decay and a darker tone, not silence
      env.gain.exponentialRampToValueAtTime(peak * 0.25, when + 0.035);
      env.gain.exponentialRampToValueAtTime(0.0001, when + Math.min(dur, 0.12));
    } else {
      env.gain.setValueAtTime(peak, when + 0.02);
      env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    }

    let node = env;
    if (mute) {
      const damp = ctx.createBiquadFilter();
      damp.type = 'lowpass';
      damp.frequency.setValueAtTime(3200, when);
      damp.frequency.exponentialRampToValueAtTime(900, when + 0.09);
      env.connect(damp);
      node = damp;
    }
    node.connect(channel);

    const spread = mute ? 5 : 11;
    for (let v = 0; v < voices; v++) {
      const detune = (v - (voices - 1) / 2) * spread * 2;
      if (useString) {
        const src = ctx.createBufferSource();
        src.buffer = this._string(f, Math.min(2.2, dur + 0.25), {
          damping: mute ? 0.85 : 0.28,
          brightness: mute ? 0.3 : 0.62,
        });
        src.detune.value = detune;
        src.connect(env);
        src.start(when);
        src.stop(when + dur + 0.05);
      } else {
        const osc = ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(f, when);
        osc.frequency.exponentialRampToValueAtTime(
          Math.max(20, f * Math.pow(2, bend / 12)), when + dur);
        osc.detune.value = detune;
        osc.connect(env);
        osc.start(when);
        osc.stop(when + dur + 0.05);
      }
    }
  }

  _clean(f, when, dur, gain) {
    if (!f || !this.ctx) return;
    const ctx = this.ctx;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), when + 0.01);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    env.connect(this.cleanCh);
    for (const detune of [-7, 7]) {
      const src = ctx.createBufferSource();
      src.buffer = this._string(f, Math.min(3.0, dur + 0.4),
                                { damping: 0.14, brightness: 0.48 });
      src.detune.value = detune;
      src.connect(env);
      src.start(when); src.stop(when + dur + 0.03);
    }
  }

  /* Root, fifth, octave. No third, which is why a power chord sits under
   * anything without committing to major or minor. */
  _power(note, when, dur, gain, opts = {}) {
    const root = freq(note);
    if (!root) return;
    if (opts.clean) {
      this._clean(root, when, dur, gain);
      this._clean(root * Math.pow(2, 7 / 12), when, dur, gain * 0.7);
      return;
    }
    const o = { ...opts, channel: this.rhythm.input };
    this._guitar(root, when, dur, gain, o);
    this._guitar(root * Math.pow(2, 7 / 12), when, dur, gain * 0.8, o);
    this._guitar(root * 2, when, dur, gain * 0.45, { ...o, voices: 1 });
  }

  _bass(f, when, dur, gain) {
    if (!f || !this.ctx) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sawtooth';
    osc.frequency.value = f;
    const sub = ctx.createOscillator();
    sub.type = 'sine';
    sub.frequency.value = f / 2;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), when + 0.008);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    osc.connect(env); sub.connect(env); env.connect(this.bassCh);
    osc.start(when); osc.stop(when + dur + 0.02);
    sub.start(when); sub.stop(when + dur + 0.02);
  }

  _noise(when, dur, gain, { hp = 200, lp = 16000, dest } = {}) {
    const ctx = this.ctx;
    const frames = Math.max(1, Math.floor(ctx.sampleRate * dur));
    const buf = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const hpf = ctx.createBiquadFilter();
    hpf.type = 'highpass'; hpf.frequency.value = hp;
    const lpf = ctx.createBiquadFilter();
    lpf.type = 'lowpass'; lpf.frequency.value = lp;
    const env = ctx.createGain();
    env.gain.setValueAtTime(Math.max(0.0001, gain), when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    src.connect(hpf); hpf.connect(lpf); lpf.connect(env);
    env.connect(dest || this.drumCh);
    src.start(when); src.stop(when + dur);
  }

  /* ---- drums ---- */

  _kick(when, gain = 0.9) {
    if (this._sample('kick', when, gain, { dest: this.drumCh })) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(150, when);
    osc.frequency.exponentialRampToValueAtTime(45, when + 0.07);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.17);
    osc.connect(env); env.connect(this.drumCh);
    osc.start(when); osc.stop(when + 0.2);
    this._noise(when, 0.012, gain * 0.5, { hp: 1800 });   // the beater click
  }

  _snare(when, gain = 0.75, rim = false) {
    if (!rim && this._sample('snare', when, gain, { dest: this.drumCh })) return;
    const ctx = this.ctx;
    this._noise(when, rim ? 0.09 : 0.16, gain, { hp: rim ? 2600 : 1500, lp: 10000 });
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(rim ? 320 : 200, when);
    osc.frequency.exponentialRampToValueAtTime(rim ? 240 : 140, when + 0.07);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain * 0.55, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.1);
    osc.connect(env); env.connect(this.drumCh);
    osc.start(when); osc.stop(when + 0.12);
  }

  _tom(when, gain = 0.6) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(220, when);
    osc.frequency.exponentialRampToValueAtTime(110, when + 0.16);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.22);
    osc.connect(env); env.connect(this.drumCh);
    osc.start(when); osc.stop(when + 0.25);
    this._noise(when, 0.05, gain * 0.3, { hp: 400, lp: 3000 });
  }

  _hat(when, gain = 0.22, open = false) {
    this._noise(when, open ? 0.24 : 0.028, gain, { hp: 8000, lp: 15000 });
  }

  _crash(when, gain = 0.55) {
    if (this._sample('crash', when, gain, { dest: this.drumCh })) return;
    this._noise(when, 1.3, gain, { hp: 2600, lp: 14000 });
  }

  /* ------------------------------------------------------ the scheduler
   *
   * "A tale of two clocks": a coarse timer wakes often enough to never miss a
   * window, and every event it finds due is scheduled against the SAMPLE CLOCK.
   * The result is a gallop that does not wobble, which is the whole point.
   */
  play(name) {
    if (!this.enabled || !this._build()) return;
    if (this.current === name && this.timer) return;
    this.stop();
    const track = TRACKS[name] || TRACKS.overworld;
    this.current = name;
    this.track = track;
    this.step = 0;
    this.lastRoot = (track.riff.trim().split(/\s+/)
      .find(t => t !== 'x' && t !== '-' && t !== '.') || 'E2').replace('>', '');

    this.rhythm.shaper.curve = this._curve(track.drive || 0.7);
    this.lead.shaper.curve = this._curve(Math.max(0.4, (track.drive || 0.7) - 0.08));

    this.lanes = {
      riff: track.riff.trim().split(/\s+/),
      lead: track.lead.trim().split(/\s+/),
      bass: track.bass.trim().split(/\s+/),
      drums: track.drums.trim().split(/\s+/),
    };
    this.sixteenth = 60 / track.bpm / 4;
    this.nextNoteTime = this.ctx.currentTime + 0.06;
    this.timer = setInterval(() => this._scheduler(), LOOKAHEAD_MS);
    this._scheduler();
  }

  _scheduler() {
    if (!this.ctx || !this.track) return;
    while (this.nextNoteTime < this.ctx.currentTime + SCHEDULE_AHEAD) {
      this._scheduleStep(this.step, this.nextNoteTime);
      this.nextNoteTime += this.sixteenth;
      this.step++;
    }
  }

  _scheduleStep(i, when) {
    const t = this.track;
    const L = this.lanes;
    const six = this.sixteenth;
    const clean = !!t.clean;
    // intensity rises as an interview clock runs down: louder, and the lead bites
    const push = 1 + this.intensity * 0.4;

    let r = L.riff[i % L.riff.length];
    if (r && r !== '-' && r !== '.') {
      const accent = r.startsWith('>');
      if (accent) r = r.slice(1);
      if (r === 'x') {
        const rootHz = freq(this.lastRoot);
        const played = !clean && this._sample('chug', when, 0.34 * push, {
          pitch: rootHz, dest: this.rhythm.input, dur: six * 1.05 });
        if (!played) {
          this._power(this.lastRoot, when, six * 1.05, 0.34 * push,
                      { mute: true, clean, duty: t.rhythm_duty });
        }
      } else {
        this.lastRoot = r;
        const dur = six * (accent ? 7 : 3.2);
        const g = (accent ? 0.42 : 0.36) * push;
        const played = !clean && this._sample('open', when, g,
          { pitch: freq(r), dest: this.rhythm.input, dur });
        if (!played) this._power(r, when, dur, g, { clean, duty: t.rhythm_duty });
      }
    }

    const l = L.lead[i % L.lead.length];
    if (l && l !== '-' && l !== '.') {
      const dur = six * 2.4;
      if (clean) {
        this._clean(freq(l), when, dur, 0.22 * push);
      } else {
        this._guitar(freq(l), when, dur, 0.26 * push,
                     { channel: this.lead.input, duty: t.lead_duty, voices: 2 });
        if (t.harmony) {
          // the twin lead: a second guitar a third or a fifth above
          this._guitar(up(l, t.harmony), when, dur, 0.16 * push,
                       { channel: this.lead.input, duty: t.lead_duty, voices: 1 });
        }
      }
    }

    const b = L.bass[i % L.bass.length];
    if (b && b !== '-' && b !== '.') this._bass(freq(b), when, six * 2.2, 0.5 * push);

    const d = L.drums[i % L.drums.length];
    switch (d) {
      case 'k': this._kick(when, 0.85 * push); break;
      case 'K': this._kick(when, 1.0 * push); break;
      case 'd': this._kick(when, 0.8 * push); this._kick(when + six / 2, 0.72 * push); break;
      case 's': this._snare(when, 0.78 * push); this._hat(when, 0.12); break;
      case 'S': this._snare(when, 0.85 * push, true); break;
      case 'h': this._hat(when, 0.2 * push); break;
      case 'H': this._hat(when, 0.26 * push, true); break;
      case 't': this._tom(when, 0.62 * push); break;
      case 'c': this._crash(when, 0.55 * push); this._kick(when, 0.9 * push); break;
      default: break;
    }
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.current = null;
    this.track = null;
  }

  /* ---------------------------------------------------------- sound effects
   * All routed to the SFX bus so they balance against the music independently. */

  sfx(kind) {
    if (!this.enabled || !this._build()) return;
    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;
    const guitar = (f, when, dur, gain, opts = {}) =>
      this._guitar(f, when, dur, gain, { channel: this.lead.input, ...opts });

    switch (kind) {
      case 'hit':
        this._power('E2', t, 0.16, 0.34, { mute: true });
        this._snare(t, 0.5);
        break;
      case 'crit':
        // a pinch harmonic squealing over a chord stab
        this._power('A2', t, 0.55, 0.4);
        guitar(freq('A5') * 2, t + 0.02, 0.55, 0.3, { bend: 2 });
        this._crash(t, 0.4);
        break;
      case 'fail':
        // the dive bomb: whammy bar to the floor
        guitar(freq('E4'), t, 0.85, 0.32, { bend: -28 });
        this._kick(t, 0.7);
        break;
      case 'select':
        this._noise(t, 0.02, 0.18, { hp: 3000, dest: G });
        break;
      case 'move':
        this._noise(t, 0.012, 0.06, { hp: 6000, dest: G });
        break;
      case 'spell':
        ['A4', 'C5', 'E5', 'A5', 'C6', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.032, 0.3, 0.2));
        break;
      case 'cast_ok':
        ['E4', 'B4', 'E5'].forEach((n, i) => guitar(freq(n), t + i * 0.04, 0.35, 0.24));
        this._snare(t, 0.4, true);
        break;
      case 'cast_fail':
        guitar(freq('C4'), t, 0.3, 0.2, { bend: -3 });
        this._noise(t, 0.1, 0.2, { hp: 400, lp: 2000, dest: G });
        break;
      case 'levelup':
        ['C3', 'F3', 'G3', 'C4'].forEach((n, i) =>
          this._power(n, t + i * 0.12, 0.6, 0.34));
        ['C5', 'E5', 'G5', 'C6', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.1, 0.45, 0.26));
        this._crash(t, 0.5);
        break;
      case 'victory':
        ['C3', 'G2', 'A2', 'F2'].forEach((n, i) =>
          this._power(n, t + i * 0.17, 0.8, 0.4));
        ['C5', 'E5', 'G5', 'C6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.17, 0.6, 0.28));
        this._crash(t, 0.55);
        this._kick(t, 0.95);
        break;
      case 'shrine':
        ['A5', 'E6', 'A6'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.15, 1.0, 0.18));
        break;
      case 'unlock':
        ['G3', 'B3', 'D4', 'G4'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.06, 0.4, 0.2));
        break;
      case 'armor':
        this._noise(t, 0.2, 0.4, { hp: 2400, lp: 12000, dest: G });
        this._kick(t, 0.7);
        guitar(freq('B4'), t + 0.06, 0.3, 0.2);
        break;
      case 'loot':
        ['E5', 'G#5', 'B5', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.055, 0.4, 0.22));
        break;
      case 'boss':
        // the tritone. Nothing announces a boss like a diabolus in musica.
        this._power('C2', t, 1.6, 0.42);
        this._power('F#2', t + 0.18, 1.6, 0.42);
        this._crash(t, 0.6);
        this._kick(t, 0.95); this._kick(t + 0.11, 0.95);
        break;
      case 'pet':
        ['D5', 'F#5', 'A5', 'D6'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.05, 0.5, 0.2));
        break;
      case 'tick':
        this._noise(t, 0.01, 0.08, { hp: 7000, dest: G });
        break;
      default:
        guitar(freq('E5'), t, 0.12, 0.18);
    }
  }
}

export const audio = new MetalRig();
export const TRACK_NAMES = Object.keys(TRACKS);
