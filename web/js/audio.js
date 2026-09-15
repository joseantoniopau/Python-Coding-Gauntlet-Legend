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

/* ---------------------------------------------------------------- the heart
 *
 * gauntlet/upkeep.py owns these two numbers and asserts that its own
 * `pulse_hz` is literally `bpm / 60`, so the red pulse on the sprite and the
 * thump underneath it are the same rate. They are named here rather than left
 * as literals inside heartbeatInterval() because the death sequence below is
 * DERIVED from them, and a sequence derived from a magic number is a sequence
 * nobody can check. scripts/verify/death.mjs reads upkeep.py and fails if the
 * two files ever stop agreeing.
 */
export const BPM_ONSET = 72;          // upkeep.BPM_ONSET: a resting heart
export const BPM_MAX = 132;           // upkeep.BPM_MAX: at zero health

/* The alarm's own two spans, taken off heartbeat()'s body so the death beats
 * can continue them instead of guessing at a shape that sounds similar. */
const HEART_GAIN_MIN = 0.16;          // gain at severity 0
const HEART_GAIN_SPAN = 0.20;         // ... and how much severity 1 adds
const HEART_HZ_MAX = 58;              // pitch at severity 0
const HEART_HZ_SPAN = 12;             // ... and how far severity 1 drops it

/* DEATH. The alarm's ramp, run backwards and then off the end of it.
 *
 *   132  BPM_MAX      the rate the alarm is already at when health hits zero,
 *                     so the first death beat is the alarm's next beat and the
 *                     seam is inaudible
 *    72  BPM_ONSET    the floor of upkeep's ramp — the resting heart the alarm
 *                     has spent the whole fight climbing away from. The heart
 *                     comes back to rest
 *    39  72 x (72/132), the same geometric step continued once more, below
 *                     anything the alarm has a number for
 *
 * Which BANDS actually sound is upkeep.py's business and it moves — at the time
 * of writing only DIRE does, so the slowest beat the player can ever have heard
 * is 108 BPM, 556ms. The first death gap is 833ms. Whatever the bands do next,
 * the first thing that happens when you die is the heart missing.
 *
 * Periods 455ms, 833ms, 1538ms. The gaps are 833ms then 1538ms, 1.85x, and the
 * first gap is already 1.83x the 455ms the player has been hearing — the heart
 * does not ease off, it misses. That stumble is the moment the player
 * understands, and it is why the sequence starts slowing on beat one rather
 * than politely holding tempo for a bar first.
 */
export const DEATH_BEAT_BPM = Object.freeze([
  BPM_MAX,
  BPM_ONSET,
  Math.round((BPM_ONSET * BPM_ONSET) / BPM_MAX),
]);

/** Period of each death beat, milliseconds. [455, 833, 1538] */
export const DEATH_BEAT_MS = Object.freeze(
  DEATH_BEAT_BPM.map(bpm => Math.round(60000 / bpm)));

/** When each death beat sounds, milliseconds from the start. [0, 833, 2371]
 *
 * Beat n+1 falls one period of ITS OWN tempo after beat n, which is what makes
 * every gap longer than the last. */
export const DEATH_BEAT_AT = Object.freeze(DEATH_BEAT_MS.reduce(
  (at, ms, i) => (i === 0 ? [0] : at.concat(at[i - 1] + ms)), []));

/** The silence after the third beat: one more of the last interval it held.
 *
 * Not the next step of the geometric ramp — that is 2816ms and is far too long
 * to hold a black screen for. The ear extrapolates the most recent interval it
 * heard, so holding exactly 1538ms puts the end of the silence on the beat that
 * did not come. The player feels the absence land rather than merely waiting
 * through it. */
export const DEATH_SILENCE_MS = DEATH_BEAT_MS[DEATH_BEAT_MS.length - 1];

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

/* ------------------------------------------------------- effect vocabulary
 *
 * Everything below this line is the SFX side of the rig rather than the band.
 * Three tables, named rather than inlined, because each one is a claim the
 * measurement harness checks: scripts and scratchpad/sfxlab.mjs render every
 * entry through an OfflineAudioContext and assert the rows differ. A table a
 * reader can see is a table a reader can check against what they heard.
 */

/* One buffer of white noise, this long, shared by every noise voice in the
 * file. See _noiseBuffer(). */
const NOISE_SECONDS = 2.0;

/* FOOTSTEPS. Terrain is a MATERIAL, and a material is three numbers: what the
 * boot's impact sounds like (a transient), what the ground does afterwards (a
 * texture), and how much body is under it (a thud). Stone is a bright click
 * with no tail; ash is a dull puff with no click; water is the only one with a
 * pitched voice in it, because a droplet has a pitch and gravel does not.
 *
 *   band    [hp, lp] of the texture, Hz
 *   dur     texture length, seconds
 *   gain    texture level
 *   attack  a swell rather than a hit, seconds. Ash and sand have one.
 *   thud    [Hz, gain] of the body under the step, or null for none
 *   click   [Hz, gain] of the impact transient, or null
 *   ring    [Hz, Q] of a resonant body — wood only, and it is what wood IS
 *   squeak  the stick-slip chirp of dry snow, snow only
 *   wet     a pitched droplet and a tail, water only
 */
const FOOTSTEP = {
  stone: { band: [1200, 9000], dur: 0.045, gain: 0.30, thud: [150, 0.10], click: [3800, 0.26] },
  wood:  { band: [140, 1100],  dur: 0.075, gain: 0.30, thud: [330, 0.26], click: [900, 0.10], ring: [330, 9] },
  grass: { band: [500, 2400],  dur: 0.120, gain: 0.26, thud: null,        click: null, attack: 0.018 },
  sand:  { band: [180, 1100],  dur: 0.130, gain: 0.30, thud: [90, 0.06],  click: null, attack: 0.008 },
  ash:   { band: [50, 320],    dur: 0.220, gain: 0.46, thud: [58, 0.12],  click: null, attack: 0.030 },
  snow:  { band: [3800, 11000], dur: 0.070, gain: 0.26, thud: null,       click: [5600, 0.16], squeak: true },
  water: { band: [900, 5000],  dur: 0.210, gain: 0.24, thud: [70, 0.07],  click: null, wet: true },
};

/* What the overworld's own tile classes are called, mapped onto the seven
 * materials above. tiles.js GROUND_OF answers grass/path/water/cliff/stone/
 * lava/sand and biomeStyle().surf answers snow/ash/flag/gravel and the rest, so
 * the next agent can hand either one straight in. */
const FOOTSTEP_ALIAS = {
  path: 'stone', cliff: 'stone', flag: 'stone', brick: 'stone', gravel: 'stone',
  rubble: 'stone', glass: 'stone', basalt: 'stone', ore: 'stone', strata: 'stone',
  bridge: 'wood', plank: 'wood', floor: 'wood', deck: 'wood',
  meadow: 'grass', wild: 'grass', moss: 'grass', scrub: 'grass', rot: 'grass',
  dirt: 'sand', bone: 'sand', dune: 'sand',
  cinder: 'ash', ember: 'ash', soot: 'ash', lava: 'ash',
  ice: 'snow', frost: 'snow', drift: 'snow',
  tar: 'water', murk: 'water', blood: 'water', swamp: 'water', shallow: 'water',
};

/* tiles.js TERRAIN codes, so a caller holding a raw grid cell can hand it
 * straight over. These mirror that file's own GROUND_OF, which is module-
 * private there and cannot be imported: a tree, a chest and a shrine all STAND
 * on something, and what you hear is what they stand on. tiles.js is owned by
 * another pass and is not edited from here, so the mirror lives on this side
 * and is asserted by the callsite note in the report rather than by an import.
 *
 * INDEX 7 IS THE ONE THAT MATTERED. It said 'stone' against tiles.js:62's
 * 'grass', and SHRINE is NOT in that file's SOLID_CODES — so a player can and
 * does stand on a shrine tile, and in a grass region the step under their feet
 * came back stone. This table's whole claim is that it mirrors GROUND_OF, and
 * a mirror with one pane out is worse than no mirror: it is right everywhere a
 * reader would check it and wrong on the one tile a player can walk onto.
 *
 * TWO CODES STILL DIVERGE, AND BOTH ARE DELIBERATE. Named here rather than
 * left to be rediscovered as a bug, because the whole value of a hand-copied
 * mirror is that somebody can tell a copy error from a decision.
 *
 *   6  BUILDING  'wood' against GROUND_OF's 'grass'. BUILDING is in tiles.js
 *                SOLID_CODES, so no foot ever lands on it and no step is ever
 *                sounded from it. The entry is read only by callers asking
 *                what the OBJECT is made of, where a house is wood and the
 *                lawn it stands on is not the answer.
 *   10 BRIDGE    'wood' against GROUND_OF's 'path'. This one IS walked on, and
 *                'wood' is the right answer: tiles.js puts BRIDGE on 'path'
 *                so it fringes into the road network, which is a statement
 *                about autotiling and not about planks. This file's own
 *                FOOTSTEP_ALIAS already says `bridge: 'wood'`, so the two
 *                halves of audio.js agree with each other; it is tiles.js's
 *                GROUND_OF that is answering a different question.
 *
 * Everything else — every walkable code — matches GROUND_OF through
 * FOOTSTEP_ALIAS exactly.
 */
const FOOTSTEP_CODE = ['grass', 'stone', 'water', 'grass', 'stone', 'stone',
                       'wood', 'grass', 'grass', 'ash', 'wood', 'sand'];

/* What each biome's open ground is actually made of, mirroring tiles.js
 * BIOME_STYLE's `surf`. It applies to GRASS and to nothing else, because
 * surfaceRamp() in that file leaves stone, path, cliff and sand alone: a
 * mountain region's grass tile is drawn as snow and a wastes region's is drawn
 * as ash, but the flagstones are flagstones in both. */
const BIOME_SURFACE = {
  village: 'meadow', grass: 'wild', forest: 'moss', deepforest: 'moss',
  canopy: 'moss', swamp: 'rot', cave: 'gravel', mine: 'gravel',
  mountain: 'snow', highland: 'scrub', citadel: 'flag', ruins: 'scrub',
  wastes: 'ash', dungeon: 'flag', tower: 'glass', arena: 'bone', castle: 'flag',
};

/* THE SIX ELEMENTS, as bossart.js ELEMENT_IDS names them (plus its NEUTRAL).
 *
 * This is the guard for the `sfx('cast_*')` prefix and nothing more: the six
 * voices are ARCHITECTURES rather than table rows — they differ in which layers
 * exist at all, not in a pitch — so they live in castElement() where that can
 * be read. The list is here because `cast_ok` and `cast_fail` are older names
 * that start with the same five characters and must not be caught by it.
 */
const ELEMENT_CAST = new Set(['fire', 'cold', 'poison', 'brute',
                              'lightning', 'void', 'neutral']);

/* WAR CRIES. Not one per creature — there are fifty-nine of them and a
 * hand-authored cry each is a table nobody would keep true. A cry is a BODY
 * PLAN voiced through an ELEMENT, exactly the way monsterart.js draws one: that
 * file already stores `family` (the element) and a role in MONSTER_ROLES, and
 * those two fields are all this needs. Nine plans x seven families is
 * sixty-three voices out of sixteen rows of table.
 *
 * The plan is the vocal tract and it decides everything structural: a skeleton
 * has no lungs, so its cry is dry clacking with no pitch centre at all; a swarm
 * has no single throat, so its cry is wingbeat modulation with no transient; an
 * elemental has no body, so its cry is pure tone with no noise in it anywhere.
 * The family only TINTS what the plan built. That ordering is the design: a
 * FIRE skeleton and a COLD skeleton are both plainly skeletons, and neither is
 * ever mistakable for a dragon.
 */
const CRY_PLANS = ['skeletal', 'dragon', 'swarm', 'elemental',
                   'flyer', 'runner', 'creeper', 'legless', 'heavy'];

/* monsterart.js MONSTER_ROLES answers one of these six; the three plans it has
 * no word for are reached by name below. */
const CRY_ROLE = {
  flyer: 'flyer', runner: 'runner', creeper: 'creeper',
  legless: 'legless', heavy: 'heavy', bodiless: 'elemental',
};

/* What a creature is CALLED, when the caller has no role to hand. Ordered:
 * skullswarm is a swarm before it is a skull. */
const CRY_BY_NAME = [
  [/swarm|hive|locust|midge|mite|moth|scarab|gnat|fly\b/i, 'swarm'],
  [/wyrm|drake|dragon|serpent|hydra|behemoth|leviathan/i, 'dragon'],
  [/skull|bone|grave|wight|lich|skelet|crypt|tomb|ossu|marrow/i, 'skeletal'],
  [/wisp|shade|spirit|phantom|wraith|dervish|cairn|mote|glim|elemental|void|null/i, 'elemental'],
  [/worm|vine|adder|viper|snake|slither|coil|lash|grub|slag/i, 'legless'],
  [/wing|shrike|wren|bat|raven|crow|phoenix|flit/i, 'flyer'],
  [/hound|wolf|jackal|ram|stag|hog|boar|cat|lion|ling\b/i, 'runner'],
  [/spider|stalker|mantis|crab|scuttle|tick|roach|monkey/i, 'creeper'],
  [/ape|golem|titan|colossus|guard|walker|giant|troll|ogre|crown|lord/i, 'heavy'],
];

/* The family tint. `p` multiplies every pitch in the plan, `d` every duration,
 * and `over` names the one extra layer the element adds on top. */
const CRY_FAMILY = {
  /* FIRE used to be { p: 1.00, d: 1.00 } — numerically identical to NEUTRAL,
   * the only family with no deviation at all, so a FIRE cry WAS a NEUTRAL cry
   * with a faint overlay and measured inside the noise of one on seven of the
   * nine body plans. Hotter and faster is the right direction and it reads
   * correctly against COLD, which is the other way round on both axes. */
  FIRE:      { p: 1.30, d: 0.70, over: 'crackle' },
  COLD:      { p: 1.12, d: 1.15, over: 'shimmer' },
  POISON:    { p: 0.90, d: 1.22, over: 'wet' },
  BRUTE:     { p: 0.78, d: 0.95, over: 'thud' },
  LIGHTNING: { p: 1.22, d: 0.85, over: 'buzz' },
  VOID:      { p: 0.68, d: 1.48, over: 'detune' },
  NEUTRAL:   { p: 1.00, d: 1.00, over: '' },
};

/* The shipped music fader over the shipped effects fader. Anything MOVED from
 * the music bus to the effects bus is scaled by this so the move is audible as
 * a change of fader and not as a change of level. */
const SFX_TRIM = 0.55 / 0.80;

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
   * the difference between a valve amp and a fuzz pedal.
   *
   * ZERO MUST GO THROUGH ZERO, and it did not. A WaveShaper maps input x onto
   * the virtual index (n-1)*(x+1)/2 and interpolates, so silence reads the
   * curve at index (n-1)/2 = 1023.5 — BETWEEN two entries. The old sampling,
   * x = (i*2)/n - 1, put the curve's own zero at index 1024 exactly, which left
   * curve[1023] = -0.0344 (at drive 0.7) and made the interpolated output for
   * an input of 0.0 equal -0.0172. That is a DC offset on a silent channel.
   * The 80Hz highpass below turns the step into a click the moment the graph is
   * built, the lead slapback repeats it 190ms later, and every quiet sound
   * measured through the rig came back 190ms long because of it.
   *
   * Two changes, both needed: sample x SYMMETRICALLY about the midpoint so the
   * two entries either side of zero straddle it, and then subtract the value
   * the shaper will actually interpolate at x=0 so it is exactly 0. Subtracting
   * a constant from a transfer curve only moves DC, which the highpass removes
   * anyway, so the even-harmonic character is untouched. */
  _curve(drive) {
    const n = 2048;
    const curve = new Float32Array(n);
    const k = 1 + drive * 60;
    const half = (n - 1) / 2;
    for (let i = 0; i < n; i++) {
      const x = (i - half) / half;
      const bias = x > 0 ? 1 : 0.82;          // squash the negative half less
      curve[i] = Math.tanh(k * x * bias) / Math.tanh(k);
    }
    // what the shaper interpolates for an input of exactly 0.0
    const atZero = (curve[n / 2 - 1] + curve[n / 2]) / 2;
    if (atZero) for (let i = 0; i < n; i++) curve[i] -= atZero;
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

    /* The same clean guitar, landing on the SFX bus instead of the music bus.
     * A chest opening is an EFFECT and has to sit under the effects fader; the
     * existing clean-toned effects (shrine, unlock, pet) predate the split and
     * are left where they are rather than changed under the player. */
    this.cleanSfx = ctx.createGain();
    this.cleanSfx.gain.value = 0.40;
    const cleanSfxTone = ctx.createBiquadFilter();
    cleanSfxTone.type = 'lowpass'; cleanSfxTone.frequency.value = 4200;
    this.cleanSfx.connect(cleanSfxTone); cleanSfxTone.connect(this.sfxBus);

    /* AND A THIRD, for the clean effects that are being MOVED to this bus
     * rather than written for it — shrine, unlock and pet.
     *
     * The trim has to live on the CHANNEL and not on the gain passed to
     * _clean(), which is the mistake this comment exists to stop anyone
     * repeating. _clean()'s envelope is an exponentialRamp anchored at 0.0001,
     * so its span in dB — and therefore the note's whole decay shape — is a
     * function of the gain argument. Scaling 0.2 to 0.089 measured 6dB hotter
     * on PEAK while RMS moved 1.4dB, because the quieter note now decays
     * across 59dB instead of 66dB in the same half-second and simply rings
     * longer. A level change must be a level change. 0.26 * SFX_TRIM into
     * sfxBus is exactly what 0.26 into musicBus was. */
    this.cleanKept = ctx.createGain();
    this.cleanKept.gain.value = 0.26 * SFX_TRIM;
    const cleanKeptTone = ctx.createBiquadFilter();
    cleanKeptTone.type = 'lowpass'; cleanKeptTone.frequency.value = 4200;
    this.cleanKept.connect(cleanKeptTone); cleanKeptTone.connect(this.sfxBus);

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

    /* THE OTHER HALF OF THE SFX/MUSIC SPLIT.
     *
     * `rhythm`, `lead` and `drumCh` above are built onto musicBus, and FIFTEEN
     * effects — every chord, squeal, snare and crash in the battle — voiced
     * through them. Measured: with the EFFECTS fader at zero and music at 0.55,
     * `hit` still played at peak 0.2478 and `defeat` at 0.4516, while with the
     * MUSIC fader at zero `hit` fell to 0.0000. Turning effects off left a
     * whole battle audible; turning music off silenced the battle instead.
     *
     * These are the same three channels with the same settings, landing on
     * sfxBus. The music scheduler keeps rhythm/lead/drumCh; sfx() uses these,
     * so a chord in a song and a chord in a defeat are the same instrument on
     * different faders.
     *
     * AND IT MUST NOT BE A MIX CHANGE. The effects fader ships at 0.80 and the
     * music fader at 0.55, so simply re-pointing these sounds would make every
     * one of them 3.3dB louder than the player has been hearing it — a routing
     * fix that arrives as a remix. SFX_TRIM cancels exactly that, so at the
     * shipped faders nothing changes level and the only new behaviour is that
     * the right fader now moves them. Measured after the trim: all fifteen sit
     * within 0.5dB of where they were, and every one of them falls to an exact
     * 0.0000 when the effects fader reaches zero. */
    this.rhythmSfx = this._channel(ctx, this.sfxBus,
      { drive: 0.7, presence: 2200, level: 0.30 * SFX_TRIM, cut: 5600 });
    this.leadSfx = this._channel(ctx, this.sfxBus,
      { drive: 0.62, presence: 2800, level: 0.20 * SFX_TRIM, cut: 7000 });
    this.drumSfx = ctx.createGain();
    this.drumSfx.gain.value = 0.5 * SFX_TRIM;
    this.drumSfx.connect(this.sfxBus);

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

    // the same slapback for the effects lead, so a crit squeal keeps its tail
    // when the music fader is down
    this.delaySfx = ctx.createDelay(0.5);
    this.delaySfx.delayTime.value = 0.19;
    const fbS = ctx.createGain();
    fbS.gain.value = 0.22;
    const wetS = ctx.createGain();
    wetS.gain.value = 0.16;
    this.leadSfx.out.connect(this.delaySfx);
    this.delaySfx.connect(fbS); fbS.connect(this.delaySfx);
    this.delaySfx.connect(wetS); wetS.connect(this.sfxBus);

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

  _clean(f, when, dur, gain, { sfx = false, kept = false } = {}) {
    if (!f || !this.ctx) return;
    const ctx = this.ctx;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), when + 0.01);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    env.connect(kept ? this.cleanKept : sfx ? this.cleanSfx : this.cleanCh);
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
    // `sfx` picks the effects-bus rhythm channel. Same amp, same settings, the
    // other fader — see the block beside this.drumSfx in _build().
    const sfx = !!opts.sfx;
    if (opts.clean) {
      this._clean(root, when, dur, gain, { sfx, kept: !!opts.kept });
      this._clean(root * Math.pow(2, 7 / 12), when, dur, gain * 0.7,
                  { sfx, kept: !!opts.kept });
      return;
    }
    const o = { ...opts, channel: sfx ? this.rhythmSfx.input : this.rhythm.input };
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

  /* ONE buffer of noise, for the whole rig.
   *
   * The previous version of _noise built a fresh AudioBuffer on every call and
   * filled it with Math.random(): for a single footstep that is a 2.3 kB
   * allocation and a 2,400-iteration loop, on a sound that fires six times a
   * second for as long as the player holds a direction, and the garbage it
   * makes is a collector pause under a game that is trying to hold 60fps.
   *
   * White noise has no memory. A random offset into one long buffer is
   * indistinguishable from a fresh draw — the measured spectra of the drums are
   * unchanged — so the buffer is built once and every voice loops it from
   * somewhere different. This is the same discipline _string() already applies
   * to the guitar: build it once, then allocate nothing.
   */
  _noiseBuffer() {
    if (this._nbuf && this._nbufCtx === this.ctx) return this._nbuf;
    const ctx = this.ctx;
    const frames = Math.max(1, Math.ceil(ctx.sampleRate * NOISE_SECONDS));
    const buf = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
    this._nbuf = buf;
    this._nbufCtx = this.ctx;
    return buf;
  }

  /* The general noise voice. The defaults reproduce the drum kit's old
   * behaviour to the sample — instant attack, exponential decay, highpass into
   * lowpass — so _kick, _snare, _tom, _hat and _crash are untouched by the
   * options below, which exist for the world sounds.
   *
   *   bp/q             one resonant bandpass instead of the hp->lp pair. A
   *                    short burst through a high Q IS a struck body: that is
   *                    what makes a wooden bridge sound wooden.
   *   hpTo/lpTo/bpTo   sweep that filter across the sound. A whiff is noise
   *                    whose band falls; a cast is noise whose band opens.
   *   attack/hold      a swell rather than a hit. Ash needs it, stone must not
   *                    have it.
   *   am/amDepth       amplitude modulation. A swarm's wingbeat and a lava
   *                    churn are the same trick at 47 Hz and 6 Hz.
   */
  _noise(when, dur, gain, { hp = 200, lp = 16000, bp = 0, q = 0,
                            hpTo = 0, lpTo = 0, bpTo = 0,
                            attack = 0, hold = 0, am = 0, amDepth = 0.7,
                            dest } = {}) {
    const ctx = this.ctx;
    if (!ctx) return;
    const buf = this._noiseBuffer();
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    const peak = Math.max(0.0001, gain);
    const end = when + dur;

    let head, tail;
    if (bp) {
      const f = ctx.createBiquadFilter();
      f.type = 'bandpass'; f.frequency.value = bp; f.Q.value = q || 1;
      if (bpTo) f.frequency.exponentialRampToValueAtTime(Math.max(20, bpTo), end);
      head = tail = f;
    } else {
      const hpf = ctx.createBiquadFilter();
      hpf.type = 'highpass'; hpf.frequency.value = hp;
      if (q) hpf.Q.value = q;
      if (hpTo) hpf.frequency.exponentialRampToValueAtTime(Math.max(20, hpTo), end);
      const lpf = ctx.createBiquadFilter();
      lpf.type = 'lowpass'; lpf.frequency.value = lp;
      if (q) lpf.Q.value = q;
      if (lpTo) lpf.frequency.exponentialRampToValueAtTime(Math.max(20, lpTo), end);
      hpf.connect(lpf);
      head = hpf; tail = lpf;
    }

    const env = ctx.createGain();
    if (attack > 0) {
      env.gain.setValueAtTime(0.0001, when);
      env.gain.exponentialRampToValueAtTime(peak, when + attack);
    } else {
      env.gain.setValueAtTime(peak, when);
    }
    if (hold > 0) env.gain.setValueAtTime(peak, when + attack + hold);
    env.gain.exponentialRampToValueAtTime(0.0001, end);

    let out = env;
    if (am > 0) {
      const trem = ctx.createGain();
      trem.gain.value = Math.max(0, 1 - amDepth);
      const lfo = ctx.createOscillator();
      lfo.type = 'sine';
      lfo.frequency.value = am;
      const depth = ctx.createGain();
      depth.gain.value = amDepth;
      lfo.connect(depth); depth.connect(trem.gain);
      lfo.start(when); lfo.stop(end + 0.02);
      env.connect(trem);
      out = trem;
    }

    src.connect(head); tail.connect(env);
    out.connect(dest || this.drumCh);
    // Somewhere different every time, so two footsteps in a row are not the
    // same 2,000 samples of noise twice — which is audible as a machine gun.
    src.start(when, Math.random() * (NOISE_SECONDS - 0.35));
    src.stop(end + 0.01);
  }

  /* A struck body: a sine dropping in pitch, with an attack fast enough to be
   * an impact rather than a note. _tone() takes 18% of its duration to open,
   * which is right for an animal voice and wrong for a boot hitting stone. */
  _thump(when, { f = 140, to = 0, dur = 0.16, gain = 0.2,
                 type = 'sine', lp = 0, dest } = {}) {
    const ctx = this.ctx;
    if (!ctx) return;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(Math.max(20, f), when);
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, to || f * 0.42), when + dur);
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, when);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), when + 0.003);
    env.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    let node = env;
    if (lp) {
      const f2 = ctx.createBiquadFilter();
      f2.type = 'lowpass'; f2.frequency.value = lp;
      env.connect(f2); node = f2;
    }
    osc.connect(env);
    node.connect(dest || this.sfxBus);
    osc.start(when); osc.stop(when + dur + 0.02);
  }

  /* ---- drums ---- */

  _kick(when, gain = 0.9, dest) {
    const D = dest || this.drumCh;
    if (this._sample('kick', when, gain, { dest: D })) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(150, when);
    osc.frequency.exponentialRampToValueAtTime(45, when + 0.07);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.17);
    osc.connect(env); env.connect(D);
    osc.start(when); osc.stop(when + 0.2);
    this._noise(when, 0.012, gain * 0.5, { hp: 1800, dest: D });   // the beater click
  }

  _snare(when, gain = 0.75, rim = false, dest) {
    const D = dest || this.drumCh;
    if (!rim && this._sample('snare', when, gain, { dest: D })) return;
    const ctx = this.ctx;
    this._noise(when, rim ? 0.09 : 0.16, gain,
               { hp: rim ? 2600 : 1500, lp: 10000, dest: D });
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(rim ? 320 : 200, when);
    osc.frequency.exponentialRampToValueAtTime(rim ? 240 : 140, when + 0.07);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain * 0.55, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.1);
    osc.connect(env); env.connect(D);
    osc.start(when); osc.stop(when + 0.12);
  }

  _tom(when, gain = 0.6, dest) {
    const D = dest || this.drumCh;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(220, when);
    osc.frequency.exponentialRampToValueAtTime(110, when + 0.16);
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, when);
    env.gain.exponentialRampToValueAtTime(0.0001, when + 0.22);
    osc.connect(env); env.connect(D);
    osc.start(when); osc.stop(when + 0.25);
    this._noise(when, 0.05, gain * 0.3, { hp: 400, lp: 3000, dest: D });
  }

  _hat(when, gain = 0.22, open = false, dest) {
    this._noise(when, open ? 0.24 : 0.028, gain,
               { hp: 8000, lp: 15000, dest: dest || this.drumCh });
  }

  _crash(when, gain = 0.55, dest) {
    const D = dest || this.drumCh;
    if (this._sample('crash', when, gain, { dest: D })) return;
    this._noise(when, 1.3, gain, { hp: 2600, lp: 14000, dest: D });
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
    //
    // RETIRED ELEMENTS DO NOT GET TO RETRY, and this guard is the difference
    // between music and a stutter. Tearing a track down sets `el.src = ''`,
    // and an <audio> element treats an empty source as a LOAD FAILURE: it
    // fires `error`. Without the flag below, every crossfade ended with the
    // outgoing track begging to be restarted, which restarted it, which
    // crossfaded out the incoming one, which fired ITS error — two tracks
    // trading the same two seconds between them forever. Measured before the
    // fix: fifteen <audio> elements built in ten seconds and `currentTime`
    // advancing 0.06s per 2.5s of wall clock.
    el.addEventListener('error', () => {
      if (el.__retired) return;        // we did this to it, on purpose
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
    el.__retired = true;               // see the error listener in _playRecorded
    setTimeout(() => {
      try { el.pause(); el.removeAttribute('src'); el.load(); }
      catch (e) { /* already gone */ }
      try { gain.disconnect(); } catch (e) { /* already gone */ }
    }, CROSSFADE_SECONDS * 1000 + 120);
    this.musicEl = null;
    this.musicGain = null;
    this.musicKey = null;
  }

  _dropRecording() {
    try {
      if (this.musicEl) {
        this.musicEl.__retired = true;
        this.musicEl.pause();
        this.musicEl.removeAttribute('src');
        this.musicEl.load();
      }
    } catch (e) { /* */ }
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
    // intensity rises as a timed practical clock runs down: louder, and the lead bites
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
    const sev = Math.max(0, Math.min(1, severity));
    this._heart(this.ctx.currentTime + 0.005, {
      gain: HEART_GAIN_MIN + sev * HEART_GAIN_SPAN,
      f: HEART_HZ_MAX - sev * HEART_HZ_SPAN,   // lower and heavier the worse it gets
    });
    return true;
  }

  /** One beat, at a stated pitch, weight and stretch. Factored out of
   *  heartbeat() rather than written beside it, because the death sequence has
   *  to be audibly THE SAME HEART and the only way to guarantee that is for
   *  there to be one shaper. heartbeat()'s own defaults are the numbers it
   *  always used, so the alarm is unchanged to the sample.
   *
   *  `stretch` scales the whole envelope with the tempo: a slow heart has a
   *  long systole, so a beat at 39 BPM is not a beat at 132 BPM with more
   *  silence after it. `pair` is the DUB — the second, tighter thump that
   *  CLOSES the pair. A heart that is stopping does not close, so the last
   *  beat of the death sequence passes pair: false and is a lub alone.
   */
  _heart(when, { f = 46, gain = 0.36, stretch = 1, pair = true, dest } = {}) {
    const G = dest || this.sfxBus;
    const s = Math.max(0.25, stretch);
    // lub: the bigger, duller thump
    this._tone(when, 0.16 * s, gain,
               { from: f, to: f * 0.62, type: 'sine', lp: 240, dest: G });
    if (!pair) return;
    // DUB: tighter, a beat behind, and it closes the pair
    this._tone(when + 0.17 * s, 0.13 * s, gain * 0.82,
               { from: f * 1.12, to: f * 0.66, type: 'sine', lp: 260, dest: G });
  }

  /* ------------------------------------------------- the heart, stopping
   *
   * THE INVERSION. The alarm above has spent the whole fight speeding this
   * heart UP, from BPM_ONSET 72 to BPM_MAX 132. Death is the same heart going
   * the other way, and the player who has been listening to it climb hears it
   * fall. That is the entire effect: three beats, each slower, quieter and
   * lower than the one before, and then nothing.
   *
   * NOT ONE OF THESE NUMBERS IS INVENTED. Every one is upkeep.py's own two
   * constants, continued:
   *
   *   TEMPO   132 -> 72 -> 39. The first is BPM_MAX, exactly the rate the alarm
   *           is running at when health hits zero, so beat one is literally the
   *           alarm's next beat and the seam is inaudible. The second is
   *           BPM_ONSET, the FLOOR of upkeep's ramp — the resting heart it has
   *           spent the whole fight climbing away from. The heart comes back to
   *           rest. The third continues the same geometric step once more,
   *           72 x (72/132) = 39, below anything the alarm has a number for.
   *           Which BANDS actually sound is upkeep's business and it moves; at
   *           the time of writing the slowest beat a player can ever have heard
   *           is 108 BPM, 556ms, and the first death gap is 833ms. Whatever the
   *           bands do next, the first thing that happens when you die is the
   *           heart missing.
   *   PITCH   46 -> 40 -> 34 Hz. The alarm's pitch runs 58 Hz at onset down to
   *           46 Hz on the floor, a span of 12. 46 is where it ends, and death
   *           carries on down the same slope at half a span a beat. Half,
   *           because a full span per beat lands the third at 22 Hz, which is
   *           under hearing and arrives as a click rather than a heart.
   *   WEIGHT  0.36 -> 0.26 -> 0.16. The alarm's gain runs 0.16 to 0.36. Death
   *           walks it back down at half a span a beat, so the last beat of a
   *           life is exactly as loud as the first beat of the warning was.
   *   STRETCH each beat's envelope scales with its own period, 1x, 1.83x,
   *           3.38x. The third beat is more than half a second of low sine,
   *           alone, unclosed.
   *
   * Scheduled against the AUDIO clock in one call, not from a timer. The three
   * intervals are the whole point of this beat and setTimeout drifts four to
   * fifteen milliseconds a tick and is throttled outright in a background tab —
   * the same reason the music scheduler at the top of this file exists.
   */
  deathBeatShape(index) {
    const i = Math.max(0, Math.min(DEATH_BEAT_BPM.length - 1, index | 0));
    return {
      f: HEART_HZ_MAX - HEART_HZ_SPAN - i * (HEART_HZ_SPAN / 2),
      gain: HEART_GAIN_MIN + HEART_GAIN_SPAN - i * (HEART_GAIN_SPAN / 2),
      stretch: DEATH_BEAT_MS[i] / DEATH_BEAT_MS[0],
      pair: i < DEATH_BEAT_BPM.length - 1,
    };
  }

  /** The three beats and the silence after them, scheduled in one go.
   *
   * Returns a handle whose `times` are milliseconds from the call — the SAME
   * table web/js/deathfx.js draws its fade against, so picture and sound are
   * one clock the way upkeep.py's pulse and thump are one clock. The handle is
   * returned even when audio is off or unavailable (`silent: true`), because a
   * player with the sound muted still has to get the timing of the screen.
   */
  heartbeatStop({ delay = 0 } = {}) {
    const times = DEATH_BEAT_AT.slice();
    const total = DEATH_BEAT_AT[DEATH_BEAT_AT.length - 1] + DEATH_SILENCE_MS;
    if (!this.enabled || !this._build()) {
      return { times, total, silent: true, cancel() {} };
    }
    // A gate of our own, so cancel() has something to close. Scheduled Web
    // Audio nodes cannot be un-scheduled; they can be turned down.
    const gate = this.ctx.createGain();
    gate.gain.value = 1;
    gate.connect(this.sfxBus);
    const t0 = this.ctx.currentTime + 0.005 + Math.max(0, delay) / 1000;
    for (let i = 0; i < DEATH_BEAT_BPM.length; i++) {
      this._heart(t0 + DEATH_BEAT_AT[i] / 1000,
                  { ...this.deathBeatShape(i), dest: gate });
    }
    const ctx = this.ctx;
    let closed = false;
    return {
      times, total, silent: false,
      cancel() {
        if (closed) return;
        closed = true;
        const now = ctx.currentTime;
        try {
          gate.gain.cancelScheduledValues(now);
          gate.gain.setValueAtTime(gate.gain.value, now);
          gate.gain.linearRampToValueAtTime(0.0001, now + 0.06);
        } catch (e) { /* a context torn down under us is not an error here */ }
        setTimeout(() => { try { gate.disconnect(); } catch (e) {} }, 200);
      },
    };
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
    const bpm = BPM_ONSET + sev * (BPM_MAX - BPM_ONSET);
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
        this._tone(t, 0.13 * d, 0.16, { from: 420 * p, to: 900 * p, type: 'sine',
                                        lp: 2400 * p, dest: G });
        this._noise(t + 0.10 * d, 0.08 * d, 0.05, { hp: 900 * p, lp: 3000 * p, dest: G });
        break;
      case 'boar': case 'boar_great': case 'hog': case 'wolf': case 'dog':
        /* THE STARTER. A boar does not howl and does not roar — it GRUNTS:
         * two short nasal pulses with a snort of air on the front of each, and
         * nothing sustained anywhere. The nasal formant at 420Hz is what keeps
         * it off the jaguar, which is the other low voice in the roster and is
         * a flat 90Hz buzz under broadband noise. */
        this._noise(t, 0.045, 0.20, { bp: 1500, bpTo: 700, q: 1.6, dest: G });
        this._tone(t, 0.15 * d, 0.24, { from: 150 * p, to: 96 * p, type: 'square',
                                        bp: 420 * p, q: 5, dest: G });
        this._thump(t, { f: 120 * p, to: 70 * p, dur: 0.10 * d, gain: 0.22,
                         lp: 600, dest: G });
        this._noise(t + 0.21 * d, 0.040, 0.16, { bp: 1400, bpTo: 640, q: 1.6, dest: G });
        this._tone(t + 0.21 * d, 0.19 * d, 0.20, { from: 136 * p, to: 84 * p,
                                                   type: 'square', bp: 380 * p, q: 5, dest: G });
        break;
      case 'octopus': case 'squid': case 'cuttlefish':
        /* Wet, but not the axolotl's bubble: a jet. A band of water falling
         * from 700Hz to 240Hz with a slow pulse in it, and one soft body tone
         * under it. Nothing in it is bright, which is what separates it from
         * every other small animal here. */
        this._noise(t, 0.34 * d, 0.16, { bp: 700, bpTo: 240, q: 3,
                                         am: 17, amDepth: 0.55, attack: 0.05, dest: G });
        this._tone(t + 0.02, 0.26 * d, 0.13, { from: 300 * p, to: 140 * p,
                                               type: 'sine', lp: 1100, dest: G });
        this._noise(t + 0.30 * d, 0.07, 0.06, { hp: 600, lp: 2200, dest: G });
        break;
      default:
        // An animal the art and the audio have not met yet still answers.
        this._tone(t, 0.24 * d, 0.18, { from: 340 * p, to: 240 * p, type: 'triangle', lp: 2200, dest: G });
        this._noise(t, 0.12, 0.06, { hp: 900, dest: G });
    }
    return true;
  }

  /* ==================================================================
   * THE WORLD
   *
   * Everything under this heading answers a thing the PLAYER DID to the world,
   * which is the governing rule for this whole section: if you can do it, you
   * can hear it. They all voice through the SFX bus so the effects fader owns
   * them, and none of them allocates a buffer — the noise is the shared one.
   * ================================================================== */

  /** A step, on a named material.
   *
   * Terrain is not a pitch, it is an ARCHITECTURE: which of the four layers
   * exist at all. Stone is a bright transient with nothing after it; ash is a
   * dull puff with no transient at all; wood is the only one with a resonant
   * body; water is the only one with a pitched voice, because a droplet has a
   * pitch and gravel does not. See the FOOTSTEP table above for the numbers —
   * they are laid out so the seven land far apart in (brightness, length),
   * which is the only reason a player can tell snow from sand without looking.
   *
   * `terrain` takes tiles.js's own words: the ground classes GROUND_OF answers
   * (grass/path/water/cliff/stone/lava/sand) and the surfaces biomeStyle()
   * answers (snow/ash/flag/gravel/moss/...) both resolve through FOOTSTEP_ALIAS,
   * so the overworld can hand over whatever it already has.
   *
   * Throttled at 55ms. The overworld already gates on its own animation frame,
   * but a footstep is the one effect in the game that fires from a held key and
   * the rate has to be bounded HERE, where the cost is.
   */
  footstep(terrain = 'grass', { running = false, heavy = false, gain = 1,
                                biome = '' } = {}) {
    if (!this.enabled || !this._build()) return false;
    const now = this.ctx.currentTime;
    if (this._lastStep === undefined) this._lastStep = -Infinity;
    if (now - this._lastStep < 0.055) return false;
    this._lastStep = now;

    const name = this.footstepMaterial(terrain, biome);
    const m = FOOTSTEP[name];
    const t = now + 0.005;
    const G = this.sfxBus;

    // No two steps identical. Six a second of the same 2,000 samples is a
    // machine gun, and the ear locks onto the repeat long before it tires of
    // the sound itself.
    const v = 0.88 + Math.random() * 0.24;
    const lvl = gain * (running ? 1.15 : 1) * (heavy ? 1.35 : 1) * (0.9 + Math.random() * 0.2);
    const dur = m.dur * (running ? 0.85 : 1);

    this._noise(t, dur, m.gain * lvl, {
      hp: m.band[0] * v, lp: m.band[1], attack: m.attack || 0, dest: G,
    });
    if (m.click) {
      this._noise(t, 0.014, m.click[1] * lvl, { bp: m.click[0] * v, q: 1.4, dest: G });
    }
    if (m.thud) {
      this._thump(t, { f: m.thud[0] * v, to: m.thud[0] * 0.42, dur: 0.09,
                       gain: m.thud[1] * lvl, lp: 420, dest: G });
    }
    if (m.ring) {
      // a plank is a box with air in it, which is a high-Q bandpass and nothing
      // else. This one layer is the whole difference between wood and stone.
      this._noise(t, 0.17, 0.20 * lvl, { bp: m.ring[0] * v, q: m.ring[1], dest: G });
    }
    if (m.squeak) {
      // dry snow squeaks because the crystals stick and slip. High, short, and
      // falling — it is the only footstep with a pitch contour above 3kHz.
      this._noise(t + 0.012, 0.055, 0.07 * lvl,
                  { bp: 4300 * v, bpTo: 2900 * v, q: 9, dest: G });
    }
    if (m.wet) {
      this._tone(t + 0.025, 0.11, 0.11 * lvl,
                 { from: 360 * v, to: 880 * v, type: 'sine', lp: 2600, dest: G });
      this._noise(t + 0.05, 0.19, 0.07 * lvl,
                  { hp: 1800, lp: 8000, attack: 0.02, dest: G });
    }
    return true;
  }

  /** Which of the seven materials a tile is, from anything the caller has.
   *
   * Takes a tiles.js TERRAIN code (a number, straight out of `scene.grid`), a
   * ground class, or a biome surface name, and optionally the region's biome.
   * Exposed rather than kept private because the caller may want to know what
   * it is walking on for reasons other than the sound, and because a mapping
   * two files have to agree on should be readable from both.
   */
  footstepMaterial(terrain, biome = '') {
    let name;
    if (typeof terrain === 'number' && FOOTSTEP_CODE[terrain]) {
      name = FOOTSTEP_CODE[terrain];
    } else {
      const key = String(terrain || '').toLowerCase();
      name = FOOTSTEP[key] ? key : (FOOTSTEP_ALIAS[key] || 'grass');
    }
    // The biome's surface governs open ground and nothing else -- tiles.js
    // paints snow and ash over GRASS, and leaves stone, path and sand alone.
    if (name === 'grass' && biome) {
      const surf = BIOME_SURFACE[String(biome).toLowerCase()];
      if (surf) name = FOOTSTEP[surf] ? surf : (FOOTSTEP_ALIAS[surf] || name);
    }
    return name;
  }

  /** A door. Opening and closing are not the same sound played backwards.
   *
   * Opening is a CREAK that rises and a latch that lets go; the sound ends
   * brighter than it started and nothing in it is loud. Closing is the reverse
   * creak cut short by a SLAM, and the slam is four times the peak of anything
   * in the open. That asymmetry is the point: a player who hears the low thud
   * knows they are outside again without reading the screen.
   */
  door(closing = false, { heavy = false } = {}) {
    if (!this.enabled || !this._build()) return false;
    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;
    const p = heavy ? 0.72 : 1;

    if (!closing) {
      this._noise(t, 0.025, 0.16, { bp: 2500, q: 2.2, dest: G });        // the latch
      this._thump(t + 0.01, { f: 120 * p, to: 70 * p, dur: 0.17, gain: 0.11, lp: 620, dest: G });
      // stick-slip: a bandpass climbing, amplitude-modulated by the judder
      this._noise(t + 0.04, 0.44, 0.11, { bp: 430 * p, bpTo: 940 * p, q: 7,
                                          am: 23, amDepth: 0.55, attack: 0.03, dest: G });
      this._tone(t + 0.07, 0.36, 0.055, { from: 610 * p, to: 1010 * p,
                                          type: 'sawtooth', bp: 1400, q: 5, dest: G });
      return true;
    }
    this._noise(t, 0.19, 0.09, { bp: 900 * p, bpTo: 440 * p, q: 7, am: 19, amDepth: 0.5, dest: G });
    const slam = t + 0.21;
    this._thump(slam, { f: 155 * p, to: 48 * p, dur: 0.28, gain: 0.46, lp: 480, dest: G });
    this._noise(slam, 0.13, 0.26, { hp: 110, lp: 1900, dest: G });
    this._noise(slam + 0.02, 0.035, 0.13, { bp: 2700, q: 3, dest: G });  // the latch catching
    return true;
  }

  /** A chest. The two outcomes share a lid, on purpose.
   *
   * `chest(true)` is the chest that was already empty, and it is the SAME latch
   * and the SAME hinge as the full one — the player has to recognise the chest
   * — with the reward figure replaced by a hollow knock and a two-note fall.
   * Nothing is added to say "empty"; something is taken away, which is what
   * empty means.
   */
  chest(empty = false) {
    if (!this.enabled || !this._build()) return false;
    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;

    this._noise(t, 0.028, 0.24, { bp: 2600, q: 2, dest: G });            // latch
    this._thump(t + 0.01, { f: 180, to: 82, dur: 0.11, gain: 0.17, lp: 700, dest: G });
    this._noise(t + 0.06, 0.30, 0.09, { bp: 520, bpTo: 1080, q: 8,      // hinge
                                        am: 17, amDepth: 0.5, dest: G });
    if (!empty) {
      this._thump(t + 0.36, { f: 124, to: 62, dur: 0.16, gain: 0.20, lp: 520, dest: G });
      ['B5', 'E6', 'F#6'].forEach((n, i) =>
        this._clean(freq(n), t + 0.42 + i * 0.07, 0.55, 0.17, { sfx: true }));
      this._noise(t + 0.42, 0.018, 0.12, { bp: 5200, q: 2, dest: G });
      return true;
    }
    // the lid hits the stop and that is all that happens
    this._thump(t + 0.36, { f: 96, to: 50, dur: 0.24, gain: 0.26, lp: 330, dest: G });
    this._tone(t + 0.40, 0.20, 0.13, { from: 330, to: 262, type: 'triangle', lp: 900, dest: G });
    this._tone(t + 0.56, 0.26, 0.10, { from: 262, to: 196, type: 'triangle', lp: 760, dest: G });
    this._noise(t + 0.36, 0.14, 0.05, { hp: 200, lp: 1100, dest: G });
    return true;
  }

  /* ==================================================================
   * THE ZONES
   * ================================================================== */

  /** A continuous sound, held until something stops it.
   *
   * Ice sliding is not an event, it is a STATE — the player is sliding for as
   * long as the ice says so — and a one-shot retriggered every frame is the
   * single most recognisable "programmer did the audio" sound there is. This
   * returns a handle instead:
   *
   *     const s = audio.sfxLoop('ice_slide');
   *     s.set(0.6);        // how hard, 0..1, ramped not stepped
   *     s.stop();          // fades out over 180ms and disconnects
   *
   * Asking twice for the same loop returns the SAME handle rather than stacking
   * a second copy, because the caller is a game loop and a game loop will ask
   * twice. Everything steady-state here is allocated once at start: after that
   * the loop costs nothing per frame, which is the whole reason it is a loop.
   */
  sfxLoop(kind, { gain = 1 } = {}) {
    const dead = { set() {}, stop() {}, kind, silent: true };
    if (!this.enabled || !this._build()) return dead;
    if (!this._loops) this._loops = new Map();
    const live = this._loops.get(kind);
    if (live && !live.closed) { live.handle.set(gain); return live.handle; }

    const ctx = this.ctx;
    const t = ctx.currentTime;
    const out = ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.connect(this.sfxBus);
    const parts = [];
    const src = () => {
      const s = ctx.createBufferSource();
      s.buffer = this._noiseBuffer();
      s.loop = true;
      s.start(t, Math.random() * (NOISE_SECONDS - 0.35));
      parts.push(s);
      return s;
    };

    let level = 0.25;
    if (kind === 'ice_slide') {
      /* Ice is a hiss with a pitch hiding in it. The bandpass IS the pitch and
       * an LFO on its frequency is the wobble a skate makes; the ring on top is
       * the note the surface sings back. */
      const band = ctx.createBiquadFilter();
      band.type = 'bandpass'; band.frequency.value = 2600; band.Q.value = 1.3;
      const lfo = ctx.createOscillator();
      lfo.type = 'sine'; lfo.frequency.value = 3.1;
      const lfoAmt = ctx.createGain(); lfoAmt.gain.value = 620;
      lfo.connect(lfoAmt); lfoAmt.connect(band.frequency);
      lfo.start(t); parts.push(lfo);
      src().connect(band); band.connect(out);

      const body = ctx.createBiquadFilter();
      body.type = 'lowpass'; body.frequency.value = 520;
      const bodyGain = ctx.createGain(); bodyGain.gain.value = 0.5;
      src().connect(body); body.connect(bodyGain); bodyGain.connect(out);

      const ring = ctx.createOscillator();
      ring.type = 'sine'; ring.frequency.value = 1840;
      const ringGain = ctx.createGain(); ringGain.gain.value = 0.035;
      ring.connect(ringGain); ringGain.connect(out);
      ring.start(t); parts.push(ring);
      level = 0.30;
    } else if (kind === 'lava_flow') {
      /* Molten rock has no top end at all. Everything above 400Hz is removed
       * and what is left is made to breathe at 5.5Hz, which is the churn. */
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 340;
      const hp = ctx.createBiquadFilter();
      hp.type = 'highpass'; hp.frequency.value = 38;
      const churn = ctx.createGain(); churn.gain.value = 0.45;
      const lfo = ctx.createOscillator();
      lfo.type = 'sine'; lfo.frequency.value = 5.5;
      const amt = ctx.createGain(); amt.gain.value = 0.4;
      lfo.connect(amt); amt.connect(churn.gain);
      lfo.start(t); parts.push(lfo);
      src().connect(lp); lp.connect(hp); hp.connect(churn); churn.connect(out);

      const sub = ctx.createOscillator();
      sub.type = 'sine'; sub.frequency.value = 46;
      const subGain = ctx.createGain(); subGain.gain.value = 0.22;
      sub.connect(subGain); subGain.connect(out);
      sub.start(t); parts.push(sub);
      level = 0.55;
    } else {
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 2000;
      src().connect(lp); lp.connect(out);
    }

    const entry = { closed: false, handle: null };
    const handle = {
      kind, silent: false,
      set(v) {
        if (entry.closed) return;
        const g = Math.max(0.0001, level * Math.max(0, Math.min(1, v)));
        const now = ctx.currentTime;
        out.gain.cancelScheduledValues(now);
        out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), now);
        out.gain.exponentialRampToValueAtTime(g, now + 0.07);
      },
      stop(fade = 0.18) {
        if (entry.closed) return;
        entry.closed = true;
        const now = ctx.currentTime;
        try {
          out.gain.cancelScheduledValues(now);
          out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), now);
          out.gain.exponentialRampToValueAtTime(0.0001, now + fade);
          for (const n of parts) { try { n.stop(now + fade + 0.02); } catch (e) {} }
        } catch (e) { /* a context torn down under us is not an error here */ }
        setTimeout(() => { try { out.disconnect(); } catch (e) {} }, (fade + 0.1) * 1000);
      },
    };
    entry.handle = handle;
    this._loops.set(kind, entry);
    handle.set(gain);
    return handle;
  }

  /** Stop one loop, or all of them. Called on scene changes, where the sliding
   *  stops because the map did. */
  stopLoops(kind) {
    if (!this._loops) return;
    for (const [k, e] of this._loops) {
      if (kind && k !== kind) continue;
      e.handle.stop();
      this._loops.delete(k);
    }
  }

  /* ==================================================================
   * BATTLE
   * ================================================================== */

  /** A cast, by ELEMENT. Six architectures, not six transpositions.
   *
   * The requirement is that a player with the screen off can name the element,
   * and six sine sweeps at six pitches would not do it — pitch is the one
   * dimension a listener reliably forgets. So each element differs in WHAT
   * LAYERS EXIST and in the SHAPE of the envelope:
   *
   *   FIRE       a lowpass opening across a roar. Noisy, mid, no transient.
   *   COLD       tone only. Three high partials and a shimmer; almost no noise.
   *   POISON     a wet bandpass wobbling down, with bubbles rising through it.
   *   BRUTE      an impact. The shortest, the loudest, and the lowest.
   *   LIGHTNING  a crack, then a 62Hz-modulated buzz, then distant rumble.
   *   VOID       a swell inward, 550ms of attack, cut off. The longest.
   *
   * The measured numbers for these six are the distinctness matrix this pass
   * exists to produce; centroid alone separates them by more than 4kHz.
   */
  castElement(element = 'neutral', { power = 1 } = {}) {
    if (!this.enabled || !this._build()) return false;
    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;
    const g = Math.max(0.3, Math.min(1.6, power));
    const el = String(element || '').toLowerCase();

    switch (el) {
      case 'fire': {
        this._noise(t, 0.55, 0.34 * g, { hp: 180, lp: 900, lpTo: 5400,
                                         attack: 0.05, dest: G });
        this._noise(t + 0.02, 0.46, 0.17 * g, { bp: 2400, bpTo: 5200, q: 1.2, dest: G });
        this._tone(t, 0.50, 0.16 * g, { from: 96, to: 60, type: 'sawtooth', lp: 700, dest: G });
        for (let i = 0; i < 5; i++) {
          this._noise(t + 0.08 + Math.random() * 0.42, 0.02, 0.07 * g,
                      { bp: 2400 + Math.random() * 2600, q: 3, dest: G });
        }
        break;
      }
      case 'cold': {
        // glass has no noise floor. Three partials, a fifth apart, falling
        // barely at all, and a shimmer far above anything else in the game.
        [[2100, 0.11], [3150, 0.075], [4200, 0.05]].forEach(([f, a]) =>
          this._tone(t, 0.80, a * g, { from: f, to: f * 0.94, type: 'sine',
                                       lp: 14000, dest: G }));
        this._noise(t + 0.04, 0.70, 0.075 * g, { hp: 6800, lp: 15000,
                                                 attack: 0.14, dest: G });
        this._noise(t, 0.02, 0.16 * g, { bp: 7200, q: 2, dest: G });
        break;
      }
      case 'poison': {
        this._tone(t, 0.62, 0.22 * g, { from: 330, to: 165, type: 'sawtooth',
                                        bp: 900, q: 8, dest: G });
        this._noise(t, 0.56, 0.11 * g, { bp: 760, bpTo: 420, q: 3,
                                         am: 9.5, amDepth: 0.6, dest: G });
        for (let i = 0; i < 5; i++) {
          this._tone(t + 0.06 + i * 0.105 + Math.random() * 0.04, 0.10, 0.15 * g,
                     { from: 420 + Math.random() * 220, to: 1500, type: 'sine',
                       lp: 3000, dest: G });
        }
        break;
      }
      case 'brute': {
        this._thump(t, { f: 160, to: 44, dur: 0.34, gain: 0.52 * g, lp: 420, dest: G });
        this._tone(t, 0.28, 0.24 * g, { from: 110, to: 50, type: 'sawtooth',
                                        lp: 380, dest: G });
        this._noise(t, 0.18, 0.30 * g, { hp: 55, lp: 820, dest: G });
        this._noise(t + 0.02, 0.30, 0.10 * g, { bp: 300, bpTo: 130, q: 2, dest: G });
        break;
      }
      case 'lightning': {
        this._noise(t, 0.013, 0.55 * g, { hp: 2200, lp: 16000, dest: G });
        this._noise(t + 0.012, 0.30, 0.22 * g, { bp: 3300, bpTo: 1500, q: 1.1,
                                                 am: 62, amDepth: 0.55, dest: G });
        this._tone(t + 0.01, 0.26, 0.12 * g, { from: 1800, to: 520, type: 'square',
                                               lp: 7000, dest: G });
        this._noise(t + 0.10, 0.36, 0.10 * g, { hp: 48, lp: 380, attack: 0.08, dest: G });
        break;
      }
      case 'void': {
        // played inward. 550ms of attack, then it is taken away rather than
        // allowed to decay, which is the only envelope in the rig that does this.
        this._noise(t, 0.88, 0.22 * g, { hp: 90, lp: 1600, lpTo: 180,
                                         attack: 0.55, dest: G });
        [[110, 0.15], [155.6, 0.11], [73.4, 0.09]].forEach(([f, a]) =>
          this._tone(t, 0.90, a * g, { from: f, to: f * 0.72, type: 'triangle',
                                       lp: 300, dest: G }));
        this._noise(t + 0.86, 0.05, 0.17 * g, { hp: 150, lp: 1400, dest: G });
        break;
      }
      default:
        this._noise(t, 0.30, 0.16 * g, { hp: 300, lp: 1400, lpTo: 3400,
                                         attack: 0.04, dest: G });
        this._tone(t, 0.30, 0.14 * g, { from: 220, to: 660, type: 'triangle',
                                        lp: 3000, dest: G });
    }
    return true;
  }

  /** Which cry a creature has, from what the creature IS.
   *
   * Name first, then monsterart.js's role. Name first because the four the
   * brief names — a skeleton, a dragon, a swarm, an elemental — are all
   * name-recognisable and MONSTER_ROLES has no word for three of them: a
   * skullswarm and a shade are both `bodiless` in that table and must not come
   * out of here as the same voice. Pass `plan` to override both.
   */
  cryPlan(name, role = '') {
    const n = String(name || '');
    for (const [re, plan] of CRY_BY_NAME) if (re.test(n)) return plan;
    const r = CRY_ROLE[String(role || '').toLowerCase()];
    return r || 'runner';
  }

  /** A war cry, built rather than authored.
   *
   * Fifty-nine creatures and a hand-written cry each is a table that goes stale
   * the first time somebody adds a monster. This is petSound()'s idea taken to
   * the bestiary: a cry is a BODY PLAN voiced through an ELEMENT, and
   * monsterart.js already stores both — `family` on every monster spec and a
   * role in MONSTER_ROLES. Nine plans times seven families is sixty-three
   * voices, every one of them derived.
   *
   *     audio.warCry('skullswarm', { family: 'VOID', role: 'bodiless' })
   *     audio.warCry(name, { family, role, tier: 'elite' })
   *
   * The plan owns everything structural, the family only tints — which is the
   * whole reason a FIRE skeleton still reads as a skeleton. A skeleton has no
   * lungs and so has no sustained pitch at all; a swarm has no throat and so
   * has no transient; an elemental has no body and so has no noise in it
   * anywhere. Those three absences are what make them unmistakable, and they
   * are absences, so they cost nothing.
   */
  warCry(name, { family = 'NEUTRAL', role = '', plan = '', tier = '',
                 power = 1 } = {}) {
    if (!this.enabled || !this._build()) return false;
    const now = this.ctx.currentTime;
    if (this._lastCry === undefined) this._lastCry = -Infinity;
    if (now - this._lastCry < 0.12) return false;
    this._lastCry = now;

    const t = now + 0.005;
    const G = this.sfxBus;
    const kind = CRY_PLANS.includes(plan) ? plan : this.cryPlan(name, role);
    const fam = CRY_FAMILY[String(family || '').toUpperCase()] || CRY_FAMILY.NEUTRAL;
    const big = /ELITE|APEX|BOSS|LEGENDARY/i.test(String(tier));
    const p = fam.p * (big ? 0.78 : 1);          // bigger throat, lower voice
    const d = fam.d * (big ? 1.30 : 1);          // and a longer one
    const g = Math.max(0.3, Math.min(1.6, power));
    const rnd = () => Math.random();

    switch (kind) {
      case 'skeletal':
        // no lungs: no sustained pitch anywhere in it, only dry bone on bone
        for (let i = 0; i < 7; i++) {
          this._noise(t + i * 0.055 + rnd() * 0.03, 0.022, 0.30 * g * (1 - i * 0.08),
                      { bp: 1700 * p * (0.8 + rnd() * 0.5), q: 7, dest: G });
        }
        this._tone(t + 0.05, 0.50 * d, 0.09 * g,
                   { from: 128 * p, to: 96 * p, type: 'triangle', lp: 420, dest: G });
        this._noise(t, 0.45 * d, 0.06 * g,
                    { bp: 2600 * p, q: 2, am: 26, amDepth: 0.8, dest: G });
        break;
      case 'dragon':
        this._tone(t, 1.30 * d, 0.32 * g,
                   { from: 72 * p, to: 46 * p, type: 'sawtooth', bp: 210 * p, q: 4, dest: G });
        this._tone(t + 0.05, 1.15 * d, 0.17 * g,
                   { from: 108 * p, to: 62 * p, type: 'square', lp: 620 * p, dest: G });
        this._noise(t, 1.30 * d, 0.30 * g,
                    { hp: 70 * p, lp: 900 * p, lpTo: 340 * p, attack: 0.15,
                      am: 24, amDepth: 0.45, dest: G });
        this._thump(t, { f: 70 * p, to: 42 * p, dur: 0.50 * d, gain: 0.34 * g,
                         lp: 260 * p, dest: G });
        break;
      case 'swarm':
        // no throat: no transient. It arrives by getting louder, and the only
        // rhythm in it is wingbeat.
        this._noise(t, 0.95 * d, 0.44 * g, { hp: 1000 * p, lp: 2400 * p, am: 47 * p,
                                             amDepth: 0.85, attack: 0.22, dest: G });
        this._noise(t + 0.05, 0.85 * d, 0.13 * g, { hp: 2200 * p, lp: 3800 * p, am: 61 * p,
                                                    amDepth: 0.7, attack: 0.30, dest: G });
        this._noise(t, 0.90 * d, 0.16 * g, { hp: 260, lp: 1200, am: 11,
                                             amDepth: 0.5, attack: 0.25, dest: G });
        break;
      case 'elemental':
        // no body: no noise. Every layer here is a pure tone, which is why it
        // measures with a rolloff almost on top of its own centroid.
        this._tone(t, 1.00 * d, 0.17 * g,
                   { from: 620 * p, to: 930 * p, type: 'sine', lp: 5000, dest: G });
        this._tone(t + 0.08, 0.90 * d, 0.14 * g,
                   { from: 930 * p, to: 1395 * p, type: 'sine', lp: 5000, dest: G });
        this._tone(t + 0.16, 0.80 * d, 0.08 * g,
                   { from: 1240 * p, to: 1860 * p, type: 'sine', lp: 5000, dest: G });
        break;
      case 'flyer':
        this._tone(t, 0.10, 0.26 * g,
                   { from: 900 * p, to: 2300 * p, type: 'sawtooth', bp: 2200 * p, q: 3, dest: G });
        this._tone(t + 0.10, 0.32 * d, 0.22 * g,
                   { from: 2300 * p, to: 700 * p, type: 'sawtooth', lp: 6000, dest: G });
        this._noise(t + 0.05, 0.40 * d, 0.10 * g,
                    { hp: 900, lp: 5200, am: 17, amDepth: 0.7, dest: G });
        break;
      case 'creeper':
        for (let i = 0; i < 11; i++) {
          this._noise(t + i * (0.05 - i * 0.002) * d, 0.012 * d, 0.60 * g,
                      { bp: 1500 * p * (1 + i * 0.06), q: 5, dest: G });
        }
        this._noise(t, 0.40 * d, 0.09 * g, { hp: 2600 * p, lp: 9000 * p, dest: G });
        this._tone(t + 0.42 * d, 0.12 * d, 0.10 * g,
                   { from: 1400 * p, to: 2100 * p, type: 'square', bp: 2000 * p, q: 4, dest: G });
        break;
      case 'legless':
        /* `p` used to reach only the 74Hz triangle, which sat at 0.07 gain under
         * 300Hz under two broadband hiss layers at 0.22 and 0.10 — so no
         * family's pitch tint could move a legless cry at all and the seven
         * tints collapsed onto each other. The hiss is what carries this plan,
         * so the hiss is what the family has to be allowed to move. */
        this._noise(t, 0.75 * d, 0.22 * g,
                    { hp: 3800 * p, lp: 12000 * p, attack: 0.10, dest: G });
        this._noise(t + 0.20, 0.50 * d, 0.10 * g,
                    { hp: 5500 * p, lp: 14000 * p, attack: 0.15, dest: G });
        this._tone(t, 0.60 * d, 0.17 * g,
                   { from: 74 * p, to: 58 * p, type: 'triangle', lp: 420 * p, dest: G });
        break;
      case 'heavy':
        this._thump(t, { f: 62 * p, to: 34 * p, dur: 0.34, gain: 0.50 * g, lp: 220, dest: G });
        this._tone(t + 0.12, 0.70 * d, 0.28 * g,
                   { from: 104 * p, to: 82 * p, type: 'sawtooth', bp: 200 * p, q: 5, dest: G });
        this._noise(t, 0.30, 0.16 * g, { hp: 50, lp: 480, dest: G });
        this._noise(t + 0.12, 0.60 * d, 0.07 * g,
                    { bp: 440, q: 2, am: 14, amDepth: 0.4, dest: G });
        break;
      default:               // runner
        this._tone(t, 0.09, 0.26 * g,
                   { from: 300 * p, to: 200 * p, type: 'square', lp: 2400, dest: G });
        this._noise(t, 0.05, 0.22 * g, { hp: 900, lp: 6000, dest: G });
        this._tone(t + 0.14, 0.09, 0.22 * g,
                   { from: 280 * p, to: 186 * p, type: 'square', lp: 2200, dest: G });
        this._tone(t + 0.30, 0.50 * d, 0.20 * g,
                   { from: 240 * p, to: 330 * p, type: 'sawtooth', lp: 2600, dest: G });
    }

    /* The family tint. One layer, on top of a plan that is already finished —
     * so it colours the cry without ever being able to restructure it. */
    switch (fam.over) {
      case 'crackle':
        /* 2200-3800Hz is exactly where swarm runs 0.44-gain noise, creeper runs
         * 0.60-gain bursts and legless runs 0.22 hiss, so four 0.065-gain
         * bursts up there were 5-9x under the layer they sat inside and
         * contributed nothing measurable. Fire is a LOW crackle with an ember
         * bed under it: down at 620-1140Hz there is nothing else competing,
         * and 33Hz AM on the bed is the flutter that says combustion. */
        for (let i = 0; i < 9; i++) {
          this._noise(t + rnd() * 0.45 * d, 0.03, 0.20 * g,
                      { bp: 620 + rnd() * 520, q: 6, dest: G });
        }
        this._noise(t, 0.55 * d, 0.10 * g,
                    { bp: 420, bpTo: 260, q: 3, am: 33, amDepth: 0.7, dest: G });
        break;
      case 'shimmer':
        this._noise(t + 0.05, 0.50 * d, 0.010 * g, { hp: 8500, lp: 11000, attack: 0.15, dest: G });
        this._tone(t, 0.60 * d, 0.026 * g,
                   { from: 4200, to: 3900, type: 'sine', bp: 4200, q: 12, dest: G });
        break;
      case 'wet':
        this._noise(t, 0.45 * d, 0.18 * g,
                    { bp: 500, bpTo: 260, q: 4, am: 9, amDepth: 0.6, dest: G });
        for (let i = 0; i < 3; i++) {
          this._tone(t + 0.12 + i * 0.22, 0.09, 0.16 * g,
                     { from: 320, to: 700, type: 'sine', lp: 1800, dest: G });
        }
        break;
      case 'thud':
        this._thump(t, { f: 78, to: 40, dur: 0.28, gain: 0.24 * g, lp: 300, dest: G });
        break;
      case 'buzz':
        this._noise(t, 0.30 * d, 0.20 * g,
                    { bp: 5200, q: 4, am: 58, amDepth: 0.85, dest: G });
        this._noise(t, 0.26 * d, 0.075 * g,
                    { bp: 2600, q: 1.2, am: 58, amDepth: 0.7, dest: G });
        this._noise(t, 0.010, 0.22 * g, { hp: 2600, lp: 16000, dest: G });
        break;
      case 'detune':
        this._tone(t, 1.10 * d, 0.18 * g,
                   { from: 96 * p * 1.414, to: 72 * p * 1.414, type: 'triangle',
                     lp: 500, dest: G });
        this._tone(t + 0.06, 0.95 * d, 0.10 * g,
                   { from: 96 * p * 1.414 * 1.03, to: 72 * p * 1.414 * 0.97,
                     type: 'triangle', lp: 500, dest: G });
        break;
      default: break;
    }
    return true;
  }

  /** One name, one sound. The prefixes below are a convenience for callers that
   *  already hold a string — `sfx('step_snow')` and `footstep('snow')` are the
   *  same call, and `sfx('cast_fire')` and `castElement('fire')` are too, so a
   *  call site with a terrain or an element in a variable does not have to
   *  branch. `cast_ok` and `cast_fail` are NOT elements and keep their old
   *  meanings, which is why the element table is consulted rather than assumed.
   */
  sfx(kind) {
    if (!this.enabled || !this._build()) return;
    const name = String(kind || '');
    if (name.startsWith('step_')) { this.footstep(name.slice(5)); return; }
    if (name.startsWith('cast_') && ELEMENT_CAST.has(name.slice(5))) {
      this.castElement(name.slice(5)); return;
    }
    if (name.startsWith('cry_')) { this.warCry('', { plan: name.slice(4) }); return; }

    const t = this.ctx.currentTime + 0.005;
    const G = this.sfxBus;
    /* leadSfx, not lead: this helper voices EFFECTS, and `lead` is built onto
     * musicBus. Every note below therefore obeys the effects fader. */
    const guitar = (f, when, dur, gain, opts = {}) =>
      this._guitar(f, when, dur, gain, { channel: this.leadSfx.input, ...opts });
    const D = this.drumSfx;

    switch (kind) {
      /* ---- the four that used to fall through to a guitar note ---- */

      case 'type': {
        /* Fires on EVERY KEYSTROKE, which makes it the only sound in the game
         * whose first requirement is that it must not be noticed. A typewriter
         * key is a click with a small wooden body under it and no pitch to
         * speak of; a guitar note at E5 forty times a sentence is torture.
         * Throttled at 22ms because a held key repeats faster than that, and
         * varied +-6% because forty identical clicks is a rattle. */
        const now = this.ctx.currentTime;
        if (this._lastType === undefined) this._lastType = -Infinity;
        if (now - this._lastType < 0.022) return;
        this._lastType = now;
        const v = 0.94 + Math.random() * 0.12;
        this._noise(t, 0.010, 0.42, { bp: 1900 * v, q: 2.4, dest: G });
        this._thump(t, { f: 300 * v, to: 180 * v, dur: 0.020, gain: 0.022,
                         lp: 1400, dest: G });
        break;
      }
      case 'error':
        /* Refusal. Low, square, two notes falling — the shape of "no" in every
         * machine that has ever said it. Nothing bright in it at all, which is
         * what separates it from `miss` and from `cast_fail`. */
        this._tone(t, 0.16, 0.26, { from: 196, to: 190, type: 'square', lp: 1200, dest: G });
        this._tone(t + 0.17, 0.26, 0.24, { from: 147, to: 138, type: 'square', lp: 1000, dest: G });
        this._noise(t, 0.05, 0.10, { hp: 120, lp: 900, dest: G });
        this._thump(t + 0.17, { f: 92, to: 62, dur: 0.20, gain: 0.14, lp: 400, dest: G });
        break;
      case 'miss':
        /* A whiff is air, and air has no pitch. A bandpass falling from 1.9kHz
         * to 420Hz is something passing the ear and going away. */
        this._noise(t, 0.24, 0.40, { hp: 600, hpTo: 150, lp: 1800, lpTo: 380,
                                     attack: 0.012, dest: G });
        this._noise(t + 0.02, 0.16, 0.10, { bp: 900, bpTo: 320, q: 2.2, dest: G });
        break;
      case 'cast':
        /* A release: everything in it opens. The lowpass climbs, the tone
         * climbs, and a small tick at the end is the moment it leaves the hand.
         * `cast_ok` is the answer that comes back; this is the throw. */
        this._noise(t, 0.30, 0.22, { hp: 260, lp: 1100, lpTo: 5200, attack: 0.06, dest: G });
        this._tone(t, 0.28, 0.16, { from: 220, to: 660, type: 'triangle', lp: 4000, dest: G });
        this._noise(t + 0.27, 0.05, 0.14, { bp: 3200, q: 2, dest: G });
        break;

      /* ---- the world ---- */

      case 'door_open':   this.door(false); break;
      case 'door_close':  this.door(true); break;
      case 'chest_open':  this.chest(false); break;
      case 'chest_empty': this.chest(true); break;
      case 'pickup':
        this._noise(t, 0.014, 0.16, { bp: 3400, q: 2, dest: G });
        ['E6', 'B6'].forEach((n, i) =>
          this._clean(freq(n), t + 0.01 + i * 0.055, 0.34, 0.62, { sfx: true }));
        break;

      /* ---- the zones ---- */

      case 'ice_crack':
        this._noise(t, 0.022, 0.32, { bp: 3200, q: 1.5, dest: G });
        this._tone(t, 0.36, 0.10, { from: 3400, to: 3080, type: 'sine', bp: 3400, q: 14, dest: G });
        this._tone(t + 0.02, 0.50, 0.09, { from: 150, to: 94, type: 'triangle', lp: 500, dest: G });
        break;
      case 'lava_divert':
        /* The player asked for a screen shake on this one. A sound that
         * deserves a screen shake is not a loud sound, it is a LOW one that
         * lasts: everything here is under 400Hz, it runs for nearly two
         * seconds, and it breathes at 6Hz so the weight arrives in waves
         * rather than all at once. It measures as the lowest centroid and the
         * highest sustained level of anything in the game. */
        this._thump(t, { f: 90, to: 34, dur: 0.50, gain: 0.50, lp: 260, dest: G });
        this._tone(t, 1.70, 0.30, { from: 44, to: 30, type: 'sine', lp: 120, dest: G });
        this._noise(t, 1.70, 0.40, { hp: 40, lp: 420, lpTo: 200, attack: 0.12,
                                     hold: 0.50, am: 6.2, amDepth: 0.5, dest: G });
        this._noise(t + 0.05, 1.20, 0.14, { bp: 180, bpTo: 90, q: 2.5,
                                            am: 3.1, amDepth: 0.35, dest: G });
        this._tone(t, 1.20, 0.16, { from: 62, to: 40, type: 'sawtooth', lp: 300, dest: G });
        this._noise(t + 0.50, 1.00, 0.014, { hp: 1400, lp: 3400, attack: 0.30, dest: G });
        break;
      case 'lantern':
        this._noise(t, 0.030, 0.30, { bp: 4200, bpTo: 2600, q: 2, dest: G });   // flint
        this._noise(t + 0.13, 0.035, 0.34, { bp: 4600, bpTo: 2800, q: 2, dest: G });
        this._noise(t + 0.28, 0.34, 0.30, { hp: 180, lp: 1800, lpTo: 600,       // catch
                                            attack: 0.05, dest: G });
        this._tone(t + 0.28, 0.50, 0.16, { from: 180, to: 120, type: 'triangle',
                                           lp: 800, dest: G });
        this._noise(t + 0.60, 0.60, 0.07, { hp: 400, lp: 2600, am: 7.3,         // flicker
                                            amDepth: 0.6, attack: 0.10, dest: G });
        break;
      case 'snowball':
        this._thump(t, { f: 320, to: 120, dur: 0.12, gain: 0.26, lp: 900, dest: G });
        this._noise(t, 0.16, 0.24, { hp: 1500, lp: 6000, lpTo: 2600, dest: G });
        this._noise(t + 0.06, 0.22, 0.07, { hp: 2600, lp: 7000, attack: 0.04, dest: G });
        break;
      case 'firework':
        this._tone(t, 0.50, 0.14, { from: 420, to: 1750, type: 'sine', lp: 4000, dest: G });
        this._noise(t, 0.50, 0.05, { bp: 900, bpTo: 2600, q: 3, dest: G });
        this._noise(t + 0.52, 0.28, 0.50, { hp: 200, lp: 12000, lpTo: 2000, dest: G });
        this._thump(t + 0.52, { f: 120, to: 45, dur: 0.30, gain: 0.30, lp: 400, dest: G });
        for (let i = 0; i < 9; i++) {
          this._noise(t + 0.66 + Math.random() * 0.80, 0.02,
                      0.06 + Math.random() * 0.07,
                      { bp: 2400 + Math.random() * 3000, q: 3, dest: G });
        }
        break;

      /* ---- battle ---- */

      case 'defeat':
        /* Not a bigger `hit`. A hit is 100ms of muted chug; this is the shape
         * of something ending — three chords walking down, the body landing,
         * and a tail that disperses instead of decaying. */
        this._power('A2', t, 0.30, 0.34, { mute: true, sfx: true });
        this._power('F2', t + 0.10, 0.30, 0.32, { mute: true, sfx: true });
        this._power('D2', t + 0.20, 0.85, 0.38, { sfx: true });
        this._thump(t + 0.34, { f: 130, to: 40, dur: 0.40, gain: 0.40, lp: 320, dest: G });
        this._noise(t + 0.34, 0.70, 0.14, { hp: 300, lp: 5200, lpTo: 700,
                                            attack: 0.05, dest: G });
        break;

      case 'hit':
        this._power('E2', t, 0.16, 0.34, { mute: true, sfx: true });
        this._snare(t, 0.5, false, D);
        break;
      case 'crit':
        // a pinch harmonic squealing over a chord stab
        this._power('A2', t, 0.55, 0.4, { sfx: true });
        guitar(freq('A5') * 2, t + 0.02, 0.55, 0.3, { bend: 2 });
        this._crash(t, 0.4, D);
        break;
      case 'fail':
        // the dive bomb: whammy bar to the floor
        guitar(freq('E4'), t, 0.85, 0.32, { bend: -28 });
        this._kick(t, 0.7, D);
        break;
      case 'select':
        this._noise(t, 0.02, 0.18, { hp: 3000, dest: G });
        break;
      case 'move':
        this._noise(t, 0.022, 0.16, { bp: 1250, q: 3, dest: G });
        this._thump(t, { f: 520, to: 380, dur: 0.03, gain: 0.05, lp: 2200, dest: G });
        break;
      case 'spell':
        /* The arpeggio alone measured 2.2 sigma from `cast_ok`, which is the
         * other rising guitar figure in the rig. A spell moves AIR: a band
         * opening from 300Hz to 6kHz underneath is the part that says something
         * left the hand, and it is the part cast_ok's confirmation must not
         * have. */
        ['A4', 'C5', 'E5', 'A5', 'C6', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.032, 0.3, 0.2));
        this._noise(t, 0.34, 0.20, { hp: 300, hpTo: 1800, lp: 1200, lpTo: 6400,
                                     attack: 0.10, dest: G });
        this._noise(t + 0.30, 0.22, 0.07, { hp: 3000, lp: 11000, attack: 0.06, dest: G });
        break;
      case 'cast_ok':
        ['E4', 'B4', 'E5'].forEach((n, i) => guitar(freq(n), t + i * 0.04, 0.35, 0.24));
        this._snare(t, 0.4, true, D);
        break;
      case 'cast_fail':
        guitar(freq('C4'), t, 0.3, 0.2, { bend: -3 });
        this._noise(t, 0.1, 0.2, { hp: 400, lp: 2000, dest: G });
        break;
      case 'levelup':
        ['C3', 'F3', 'G3', 'C4'].forEach((n, i) =>
          this._power(n, t + i * 0.12, 0.6, 0.34, { sfx: true }));
        ['C5', 'E5', 'G5', 'C6', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.1, 0.45, 0.26));
        this._crash(t, 0.5, D);
        break;
      case 'victory':
        ['C3', 'G2', 'A2', 'F2'].forEach((n, i) =>
          this._power(n, t + i * 0.17, 0.8, 0.4, { sfx: true }));
        ['C5', 'E5', 'G5', 'C6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.17, 0.6, 0.28));
        this._crash(t, 0.55, D);
        this._kick(t, 0.95, D);
        break;
      case 'shrine':
        ['A5', 'E6', 'A6'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.15, 1.0, 0.18, { kept: true }));
        break;
      case 'unlock':
        ['G3', 'B3', 'D4', 'G4'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.06, 0.4, 0.2, { kept: true }));
        break;
      case 'armor':
        this._noise(t, 0.2, 0.4, { hp: 2400, lp: 12000, dest: G });
        this._kick(t, 0.7, D);
        guitar(freq('B4'), t + 0.06, 0.3, 0.2);
        break;
      case 'loot':
        /* This was a fourth rising guitar arpeggio and measured 1.3 sigma from
         * `spell` and 2.8 from `cast_ok` — three different events on one sound.
         * What separates treasure from a spell is not the notes, it is the
         * METAL: coins are a scatter of short high transients with no pitch,
         * and nothing else in the rig has that. */
        ['E5', 'G#5', 'B5', 'E6'].forEach((n, i) =>
          guitar(freq(n), t + i * 0.055, 0.4, 0.22));
        for (let i = 0; i < 7; i++) {
          this._noise(t + 0.02 + Math.random() * 0.34, 0.012, 0.20,
                      { bp: 5200 + Math.random() * 3600, q: 5, dest: G });
        }
        this._noise(t + 0.01, 0.30, 0.05, { hp: 6000, lp: 14000, attack: 0.06, dest: G });
        break;
      case 'boss':
        // the tritone. Nothing announces a boss like a diabolus in musica.
        this._power('C2', t, 1.6, 0.42, { sfx: true });
        this._power('F#2', t + 0.18, 1.6, 0.42, { sfx: true });
        this._crash(t, 0.6, D);
        this._kick(t, 0.95, D); this._kick(t + 0.11, 0.95, D);
        break;
      case 'pet':
        ['D5', 'F#5', 'A5', 'D6'].forEach((n, i) =>
          this._clean(freq(n), t + i * 0.05, 0.5, 0.2, { kept: true }));
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
