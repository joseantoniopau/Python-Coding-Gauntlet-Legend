#!/bin/bash
# Assemble the macOS application bundle.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Python Coding Gauntlet Legend"
APP="$REPO/dist/$APP_NAME.app"
CONTENTS="$APP/Contents"

echo "==> building $APP_NAME.app"
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"

# --- icon ---------------------------------------------------------------
python3 "$REPO/scripts/make_icon.py" "$CONTENTS/Resources/AppIcon.icns" >/dev/null

# --- payload ------------------------------------------------------------
# The bundle carries its own copy so moving or deleting the source checkout
# does not break a launcher the user has already put in their Dock.
mkdir -p "$CONTENTS/Resources/app"
/usr/bin/rsync -a --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
  --exclude 'dist' --exclude 'runtime' --exclude '.DS_Store' \
  "$REPO/gauntlet" "$REPO/web" "$CONTENTS/Resources/app/"

# --- Info.plist ---------------------------------------------------------
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>               <string>Gauntlet Legend</string>
  <key>CFBundleDisplayName</key>        <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>         <string>com.josea.gauntletlegend</string>
  <key>CFBundleVersion</key>            <string>1.0.0</string>
  <key>CFBundleShortVersionString</key> <string>1.0.0</string>
  <key>CFBundleExecutable</key>         <string>GauntletLegend</string>
  <key>CFBundleIconFile</key>           <string>AppIcon</string>
  <key>CFBundlePackageType</key>        <string>APPL</string>
  <key>LSMinimumSystemVersion</key>     <string>11.0</string>
  <key>NSHighResolutionCapable</key>    <true/>
  <key>LSApplicationCategoryType</key>  <string>public.app-category.educational-games</string>
  <key>NSHumanReadableCopyright</key>
  <string>Original work. No third-party game assets are used.</string>
</dict>
</plist>
PLIST

# --- launcher -----------------------------------------------------------
cat > "$CONTENTS/MacOS/GauntletLegend" <<'LAUNCH'
#!/bin/bash
# Resolve a usable python3 and hand off to the game launcher.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$HERE/../Resources/app" && pwd)"
LOG_DIR="$HOME/Library/Logs/GauntletLegend"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/launch.log"

note() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

note "starting from $APP_ROOT"

pick_python() {
  local best=""
  local best_minor=-1
  # Prefer a modern interpreter, but the system one is always an acceptable floor.
  for candidate in \
      /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 \
      /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3 \
      /usr/local/bin/python3 "$HOME/.local/bin/python3" \
      "$(command -v python3 2>/dev/null)" /usr/bin/python3; do
    [ -x "$candidate" ] || continue
    local minor
    minor="$("$candidate" -c 'import sys; print(sys.version_info[1] if sys.version_info[0]==3 else -1)' 2>/dev/null)" || continue
    [ -n "$minor" ] || continue
    if [ "$minor" -ge 9 ] && [ "$minor" -gt "$best_minor" ]; then
      best="$candidate"
      best_minor="$minor"
    fi
  done
  printf '%s' "$best"
}

PY="$(pick_python)"
if [ -z "$PY" ]; then
  note "no python3 found"
  /usr/bin/osascript -e 'display alert "Python 3 not found" message "Python Coding Gauntlet Legend needs Python 3.9 or newer.\n\nInstall the Xcode Command Line Tools with:\n\n    xcode-select --install\n\nthen open the app again." as critical'
  exit 1
fi
note "using $PY ($("$PY" -V 2>&1))"

cd "$APP_ROOT"
export PYTHONPATH="$APP_ROOT"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" -u -m gauntlet.launcher >> "$LOG" 2>&1
LAUNCH

chmod +x "$CONTENTS/MacOS/GauntletLegend"

# --- ad-hoc signature so Gatekeeper treats it as a stable local app -----
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP" 2>/dev/null \
    && echo "==> ad-hoc signed" \
    || echo "==> codesign unavailable; the app still runs"
fi

echo "==> built: $APP"

# ---------------------------------------------------------------- install
#
# THE BUG THIS EXISTS TO PREVENT, and it cost a player two days of testing a
# build that did not contain any of the fixes they were testing for:
#
# This script writes to dist/ inside the repo. The app a person actually
# double-clicks lives in ~/Applications. Nothing ever connected the two, so
# every rebuild landed somewhere the player never opened, and they reported the
# old music, the old battle screen and a refresh that "did nothing" — all three
# correct observations of a copy from two days earlier.
#
# So: if a copy is already installed, UPDATE IT. Only if one is already there —
# putting an app into someone's Applications folder uninvited is not this
# script's business, and a first-time build should not do it.
INSTALLED="$HOME/Applications/$(basename "$APP")"
if [ -d "$INSTALLED" ]; then
  # A running copy holds its own Python in memory and would keep serving the
  # old code from the new files, which looks exactly like the bug above.
  if pgrep -f "gauntlet.launcher" >/dev/null 2>&1; then
    echo "==> a copy is RUNNING; quit it before launching the new one"
  fi
  rm -rf "$INSTALLED"
  cp -R "$APP" "$INSTALLED"
  echo "==> installed: $INSTALLED"
else
  echo "==> not installed to ~/Applications (no copy there yet)"
  echo "    to install:  cp -R \"$APP\" ~/Applications/"
fi
