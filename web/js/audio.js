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
/* Recorded music.
 *
 * Five licence-clear tracks, one per situation. These SHADOW the synthesised
 * tracks below rather than replacing them: if a file is missing, fails to load,
 * or the browser refuses the codec, the rig falls straight back to synthesis and
 * the game still has music. That ordering matters — audio files are the one part
 * of this project that can be absent at runtime for reasons outside our control.
 *
 * Streamed through an <audio> element rather than decoded into an AudioBuffer:
 * twenty-seven megabytes of MP3 becomes several hundred megabytes of PCM once
 * decoded, and a game that teaches Python should not spend that to loop a riff.
 *
 * Licences and credits: web/audio/music/CREDITS.md
 */
const MUSIC = {
  overworld: {
    file: 'nickpanek-epic-symphonic-metal-instrumental-263322.mp3',
    artist: 'nickpanek', title: 'Epic Symphonic Metal Instrumental',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
  battle: {
    file: 'alec_koff-melodic-metal-heavy-metal-music-484511.mp3',
    artist: 'alec_koff', title: 'Melodic Metal / Heavy Metal Music',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
  boss: {
    file: 'alex-morgan-thrash-metal-591343.mp3',
    artist: 'Alex Morgan', title: 'Thrash Metal',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
  dungeon: {
    file: 'myshoun-metal-guardian-391820.mp3',
    artist: 'myshoun', title: 'Metal Guardian',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
  newarea: {
    file: 'myshoun-metal-queen-392333.mp3',
    artist: 'myshoun', title: 'Metal Queen',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
  title: {
    file: 'nickpanek-80s-style-surf-thrash-instrumental-252511.mp3',
    artist: 'nickpanek', title: '80s Style Surf Thrash Instrumental',
    licence: 'Pixabay Content License', source: 'https://pixabay.com/music/',
  },
};

/* Situations with no recording of their own borrow the nearest one, so the
 * whole game is covered by five files instead of feeling half-scored. */
const MUSIC_ALIAS = {
  town: 'overworld', camp: 'overworld', shrine: 'dungeon',
  tower: 'newarea', final: 'boss', victory: 'newarea',
};

const MUSIC_BASE = '/audio/music/';
const CROSSFADE_SECONDS = 1.1;

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
    // A browser that blocked autoplay leaves the track pending; this is the
    // gesture it was waiting for.
    if (this._pendingTrack) {
      const name = this._pendingTrack;
      this._pendingTrack = null;
      if (this.musicEl) { this.musicEl.play().catch(() => {}); this.current = name; }
      else this.play(name);
    } else if (this.musicEl && this.musicEl.paused) {
      this.musicEl.play().catch(() => {});
    }
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
    if (!on) this.silence();   // turning music off must stop the recording too
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
  /* ----------------------------------------------------- recorded music
   *
   * Returns true when a recording is playing, which is the caller's signal that
   * the synthesised rig is not needed. Anything that goes wrong here returns
   * false and the synth takes over, so a missing file is a quieter game rather
   * than a broken one.
   */
  _musicKey(name) {
    if (MUSIC[name]) return name;
    const alias = MUSIC_ALIAS[name];
    return MUSIC[alias] ? alias : null;
  }

  hasRecording(name) {
    return this.useRecordings !== false && !!this._musicKey(name);
  }

  _playRecorded(name) {
    const key = this._musicKey(name);
    if (!key || this.useRecordings === false) return false;
    if (typeof Audio === 'undefined') return false;

    // Already on it: a region change that resolves to the same recording should
    // not restart the track, or walking a border rewinds the music every step.
    if (this.musicKey === key && this.musicEl && !this.musicEl.paused) {
      this.current = name;
      return true;
    }

    let el;
    try {
      el = new Audio(MUSIC_BASE + MUSIC[key].file);
    } catch (err) {
      return false;
    }
    el.loop = true;
    el.preload = 'auto';
    el.crossOrigin = 'anonymous';

    let node;
    try {
      node = this.ctx.createMediaElementSource(el);
    } catch (err) {
      return false;   // some browsers refuse this for a file: origin
    }
    const gain = this.ctx.createGain();
    gain.gain.value = 0;
    node.connect(gain);
    gain.connect(this.musicBus);

    // If it cannot actually play — codec, autoplay policy, a 404 — undo the
    // whole thing and let the synth rig have the track.
    el.addEventListener('error', () => {
      if (this.musicEl === el) this._dropRecording();
      this.play(name);
    }, { once: true });

    const started = el.play();
    if (started && typeof started.catch === 'function') {
      started.catch(() => {
        // Autoplay was blocked. The first real gesture calls resume(), which
        // retries, so this is a pause rather than a failure.
        this._pendingTrack = name;
      });
    }

    this.stop();                       // silence the synthesised scheduler
    this._fadeOutRecording();          // and crossfade out whatever was playing
    const now = this.ctx.currentTime;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(1, now + CROSSFADE_SECONDS);

    this.musicEl = el;
    this.musicGain = gain;
    this.musicKey = key;
    this.current = name;
    return true;
  }

  _fadeOutRecording() {
    const el = this.musicEl;
    const gain = this.musicGain;
    if (!el || !gain) return;
    const now = this.ctx.currentTime;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    gain.gain.linearRampToValueAtTime(0, now + CROSSFADE_SECONDS);
    // Let the ramp finish before tearing the element down, or the fade is a cut.
    setTimeout(() => {
      try { el.pause(); el.src = ''; } catch (e) { /* already gone */ }
      try { gain.disconnect(); } catch (e) { /* already gone */ }
    }, CROSSFADE_SECONDS * 1000 + 120);
    this.musicEl = null;
    this.musicGain = null;
    this.musicKey = null;
  }

  _dropRecording() {
    try { if (this.musicEl) { this.musicEl.pause(); this.musicEl.src = ''; } } catch (e) { /* */ }
    try { if (this.musicGain) this.musicGain.disconnect(); } catch (e) { /* */ }
    this.musicEl = null;
    this.musicGain = null;
    this.musicKey = null;
  }

  /** Credits for whatever is currently playing, for the settings screen. */
  nowPlaying() {
    const entry = this.musicKey && MUSIC[this.musicKey];
    if (!entry) return null;
    return { title: entry.title, artist: entry.artist,
             licence: entry.licence, source: entry.source };
  }

  play(name) {
    if (!this.enabled || !this._build()) return;
    if (this.current === name && (this.timer || this.musicEl)) return;
    if (this._playRecorded(name)) return;
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
    // The synthesised rig only. _playRecorded() calls this while the outgoing
    // recording is still fading, so tearing recordings down here would turn
    // every crossfade into a cut.
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.current = null;
    this.track = null;
  }

  /** Everything: the scheduler and any recording. Used when music is turned off. */
  silence() {
    this.stop();
    this._pendingTrack = null;
    this._fadeOutRecording();
  }

  /* ---------------------------------------------------------- sound effects
   * All routed to the SFX bus so they balance against the music independently. */

  /* ------------------------------------------------------- the heartbeat
   *
   * A low-health alarm, because a player reading a problem is not watching a
   * bar. Two thumps and a rest, the way a real one goes — lub-DUB, pause — and
   * it gets faster and louder as things get worse, so the player feels the
   * change without having to look up and read a number.
   *
   * Driven by the client calling heartbeat() once per beat rather than run from
   * a timer in here: the audio rig has no idea how much health anybody has, and
   * giving it one would be the wrong thing in the wrong file.
   */
  heartbeat(severity = 1) {
    if (!this.enabled || !this._build()) return false;
    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;
    const sev = Math.max(0, Math.min(1, severity));
    const gain = 0.16 + sev * 0.20;
    const f = 58 - sev * 12;            // lower and heavier the worse it gets

    // lub: the bigger, duller thump
    this._tone(t, 0.16, gain, { from: f, to: f * 0.62, type: 'sine', lp: 240, dest: G });
    // DUB: tighter, a beat behind, and it closes the pair
    this._tone(t + 0.17, 0.13, gain * 0.82,
               { from: f * 1.12, to: f * 0.66, type: 'sine', lp: 260, dest: G });
    return true;
  }

  /** Milliseconds between beats for a given severity.
   *
   * These are gauntlet/upkeep.py's BPM_ONSET (72) and BPM_MAX (132), not a
   * tempo invented here. That module asserts pulse_hz == bpm/60 so the red
   * pulse on the sprite and the thump underneath it are the SAME rate — two
   * warnings running at different speeds read as noise and get tuned out. If
   * those constants move, move these with them.
   */
  heartbeatInterval(severity = 1) {
    const sev = Math.max(0, Math.min(1, severity));
    const bpm = 72 + sev * (132 - 72);
    return Math.round(60000 / bpm);
  }

  /* ------------------------------------------------------ companion voices
   *
   * Every companion answers when you click it, and no two answer alike. These
   * are synthesised rather than sampled, like the rest of the rig, which is not
   * purity for its own sake: an animal voice is a pitch contour plus a noise
   * texture, and both are things we can shape per-call, so a jaguar can growl
   * lower when it is a legendary than when you first met it.
   *
   * Voiced through the SFX bus so the player's effects fader controls them, and
   * throttled, because a clickable animal is a thing people will click.
   */
  _tone(when, dur, gain, { from, to, type = 'sawtooth', lp = 6000, q = 1,
                           bp = 0, dest } = {}) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(Math.max(20, from), when);
    // exponentialRamp refuses to touch zero, and a voice that slides to silence
    // is the most common shape here, so the floor is 20Hz rather than 0.
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, to), when + dur);

    const filt = ctx.createBiquadFilter();
    if (bp) { filt.type = 'bandpass'; filt.frequency.value = bp; filt.Q.value = q; }
    else { filt.type = 'lowpass'; filt.frequency.value = lp; filt.Q.value = q; }

    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), when + dur * 0.18);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);

    osc.connect(filt); filt.connect(env); env.connect(dest || this.sfxBus);
    osc.start(when); osc.stop(when + dur + 0.02);
  }

  /** Click a companion and it answers. `tier` deepens and lengthens the voice,
   *  so the returned starter sounds like what it grew into. */
  petSound(animal, { tier = '', dead = false } = {}) {
    if (!this.enabled || !this._build()) return false;
    if (this._lastPet === undefined) this._lastPet = -Infinity;

    // People click animals. Two hundred milliseconds is enough to stop a click
    // storm turning into a wall of noise without making the pet feel unresponsive.
    const now = this.ctx.currentTime;
    // -Infinity rather than a falsy 0: a context whose clock is legitimately at
    // zero would otherwise read as "never clicked" and let the throttle through
    // on every call, which is exactly what it looks like before the first
    // gesture resumes the context.
    if (now - this._lastPet < 0.2) return false;
    this._lastPet = now;

    const t = now + 0.005;
    const G = this.sfxBus;
    const big = /LEGENDARY|MASTER|HIDDEN/i.test(String(tier));
    const d = big ? 1.25 : 1;          // bigger animal, lower and longer
    const p = big ? 0.72 : 1;

    if (dead) {
      // Not a voice. The absence of one.
      this._noise(t, 0.5, 0.05, { hp: 200, lp: 900, dest: G });
      return true;
    }

    switch (String(animal || '').toLowerCase()) {
      case 'jaguar': case 'cat': case 'panther':
        // a growl: low buzz under a body of filtered noise
        this._tone(t, 0.42 * d, 0.22, { from: 90 * p, to: 62 * p, type: 'sawtooth', lp: 700, dest: G });
        this._noise(t, 0.40 * d, 0.10, { hp: 120, lp: 1100, dest: G });
        break;
      case 'python': case 'snake': case 'serpent':
        // a hiss has no pitch at all — it is band-limited noise that opens and closes
        this._noise(t, 0.55 * d, 0.16, { hp: 3500, lp: 11000, dest: G });
        this._noise(t + 0.06, 0.34 * d, 0.09, { hp: 5200, lp: 13000, dest: G });
        break;
      case 'llama': case 'alpaca':
        // a nasal hum, flat and unbothered, with a small drop at the end
        this._tone(t, 0.34 * d, 0.20, { from: 300 * p, to: 286 * p, type: 'square', bp: 900, q: 6, dest: G });
        this._tone(t + 0.30 * d, 0.16 * d, 0.14, { from: 286 * p, to: 208 * p, type: 'square', bp: 780, q: 6, dest: G });
        break;
      case 'penguin': case 'auk':
        // a bray: two hard barks, pitch up then down, with grit on the front
        this._tone(t, 0.13, 0.24, { from: 380 * p, to: 620 * p, type: 'square', lp: 3200, dest: G });
        this._noise(t, 0.05, 0.12, { hp: 1800, dest: G });
        this._tone(t + 0.17, 0.15, 0.20, { from: 600 * p, to: 300 * p, type: 'square', lp: 2800, dest: G });
        break;
      case 'velociraptor': case 'raptor': case 'dinosaur':
        // a shriek that rises fast and falls faster, which is why it alarms
        this._tone(t, 0.10, 0.26, { from: 700 * p, to: 1500 * p, type: 'sawtooth', lp: 7000, dest: G });
        this._tone(t + 0.10, 0.22, 0.22, { from: 1500 * p, to: 420 * p, type: 'sawtooth', lp: 6000, dest: G });
        this._noise(t + 0.02, 0.16, 0.08, { hp: 2500, dest: G });
        break;
      case 'crow': case 'raven': case 'bird':
        this._tone(t, 0.09, 0.22, { from: 820 * p, to: 560 * p, type: 'sawtooth', bp: 1600, q: 3, dest: G });
        this._tone(t + 0.14, 0.09, 0.18, { from: 780 * p, to: 520 * p, type: 'sawtooth', bp: 1500, q: 3, dest: G });
        break;
      case 'tortoise': case 'turtle':
        // almost nothing, slowly. The joke is the timing.
        this._tone(t, 0.7 * d, 0.13, { from: 150 * p, to: 120 * p, type: 'triangle', lp: 520, dest: G });
        break;
      case 'axolotl': case 'nautilus': case 'fish':
        // wet and small: a bubble, not a call
        this._tone(t, 0.13, 0.16, { from: 420 * p, to: 900 * p, type: 'sine', lp: 2400, dest: G });
        this._noise(t + 0.10, 0.08, 0.05, { hp: 900, lp: 3000, dest: G });
        break;
      case 'wolf': case 'dog': case 'fox':
        this._tone(t, 0.5 * d, 0.20, { from: 260 * p, to: 340 * p, type: 'sawtooth', lp: 1800, dest: G });
        this._tone(t + 0.45 * d, 0.35 * d, 0.14, { from: 330 * p, to: 210 * p, type: 'sawtooth', lp: 1500, dest: G });
        break;
      case 'moth': case 'beetle': case 'insect':
        this._noise(t, 0.30, 0.07, { hp: 1400, lp: 5200, dest: G });
        this._tone(t, 0.30, 0.09, { from: 62, to: 58, type: 'square', bp: 240, q: 9, dest: G });
        break;
      default:
        // An animal the art and the audio have not met yet still answers.
        this._tone(t, 0.24 * d, 0.18, { from: 340 * p, to: 240 * p, type: 'triangle', lp: 2200, dest: G });
        this._noise(t, 0.12, 0.06, { hp: 900, dest: G });
    }
    return true;
  }

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
