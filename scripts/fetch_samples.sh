#!/bin/bash
# Optional: populate the sample layer with licence-clear audio.
#
# The game ships with NO audio files and needs none — every sound is synthesised
# at runtime, which is why it is a 2.5MB app that works offline. This script is
# for anyone who would rather hear real recorded guitar than a physical model.
#
# The rule this script enforces: nothing is installed without a recorded licence
# and source URL. Shipping audio whose provenance you cannot state is the one
# mistake here that is genuinely expensive, so the loader refuses entries that
# lack either field.
#
# WHERE TO GET LICENCE-CLEAR AUDIO
#   freesound.org      filter by "Creative Commons 0". Needs a free account and
#                      an API token for programmatic download; the web UI does
#                      not. https://freesound.org/browse/tags/cc0/
#   opengameart.org    filter licence to CC0. Files download directly.
#                      https://opengameart.org/art-search-advanced
#   Sonatina / VSCO 2  CC0 orchestral libraries, if you want the score orchestral
#   Your own playing   the only source with no paperwork at all
#
# WHAT THE ENGINE WILL USE, if present. Anything missing falls back to synthesis,
# so a partial set is fine:
#   chug_e2.wav  chug_f2.wav  chug_g2.wav  chug_a2.wav   palm-muted power chords
#   open_e2.wav  open_a2.wav                             ringing power chords
#   lead_a4.wav                                          a single sustained note
#   kick.wav  snare.wav  hat.wav  crash.wav  tom.wav     drums
#
# Mono or stereo, any sample rate, .wav or .ogg. Pitched samples are resampled,
# so one well-recorded chord per string covers a lot of ground.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HERE/web/audio"
MANIFEST="$DEST/manifest.json"

echo "sample directory: $DEST"
echo
found=$(find "$DEST" -maxdepth 1 \( -name '*.wav' -o -name '*.ogg' \) 2>/dev/null | wc -l | tr -d ' ')
echo "audio files present: $found"

if [ "$found" -eq 0 ]; then
  cat <<'MSG'

No samples installed, which is a perfectly good state to be in — the game
synthesises a full metal rig at runtime: Karplus-Strong plucked strings through
an asymmetric waveshaper, a scooped-mid cabinet EQ, separate rhythm and lead
channels, and a sample-accurate lookahead scheduler.

To add samples:
  1. Download CC0 audio from one of the sources listed at the top of this file.
  2. Drop the files into web/audio/ using the names listed above.
  3. Record each one in web/audio/manifest.json with its licence and source URL.
  4. Re-run this script to verify.

MSG
  exit 0
fi

echo
echo "verifying every file is declared with a licence and a source..."
python3 - "$DEST" <<'PY'
import json, os, sys
dest = sys.argv[1]
manifest_path = os.path.join(dest, 'manifest.json')
manifest = json.load(open(manifest_path))
declared = {s.get('file'): s for s in manifest.get('samples', [])}
present = [f for f in os.listdir(dest) if f.endswith(('.wav', '.ogg'))]

problems = []
for name in present:
    entry = declared.get(name)
    if not entry:
        problems.append(f'{name}: present but not declared in manifest.json')
        continue
    if not entry.get('licence'):
        problems.append(f'{name}: no licence recorded')
    if not entry.get('source'):
        problems.append(f'{name}: no source URL recorded')
for name in declared:
    if name not in present:
        problems.append(f'{name}: declared but the file is missing')

if problems:
    print('  REFUSED:')
    for p in problems:
        print('   -', p)
    sys.exit(1)
print(f'  ok: {len(present)} file(s), every one declared with a licence and a source')
for name, entry in declared.items():
    print(f'   {name:<16} {entry["licence"]:<10} {entry["source"]}')
PY
