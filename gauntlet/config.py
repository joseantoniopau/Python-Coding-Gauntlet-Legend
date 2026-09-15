"""Global configuration and path resolution for Python Coding Gauntlet Legend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Python Coding Gauntlet Legend"
APP_SUBTITLE = "The Algorithm Realms"
APP_ID = "com.josea.gauntletlegend"
VERSION = "1.1.0"

PKG_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PKG_ROOT.parent
WEB_ROOT = REPO_ROOT / "web"


def data_dir() -> Path:
    """Per-user writable directory (save games, generated corpus, logs)."""
    override = os.environ.get("GAUNTLET_DATA_DIR")
    if override:
        p = Path(override).expanduser()
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "GauntletLegend"
    elif os.name == "nt":
        # %APPDATA% is the roaming profile, which is where a save game belongs.
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        p = Path(base) / "GauntletLegend"
    else:
        p = Path.home() / ".local" / "share" / "gauntlet-legend"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "save.sqlite3"


def corpus_path() -> Path:
    return data_dir() / "corpus.json"


def log_path() -> Path:
    return data_dir() / "gauntlet.log"


# --- Execution sandbox tuning -------------------------------------------------
SANDBOX_CPU_SECONDS = 6          # hard CPU ceiling per submission
SANDBOX_WALL_SECONDS = 12        # wall-clock ceiling for the whole test batch
SANDBOX_MEMORY_MB = 512
PER_TEST_TIMEOUT_MS = 3000       # correctness tests
PERF_TEST_TIMEOUT_MS = 5000      # performance / complexity tests

# --- Learning engine tuning ---------------------------------------------------
SRS_INTERVALS_DAYS = [1, 3, 7, 14, 30, 60]
STAMINA_MAX = 20
STAMINA_LOSS_FAILED_SUBMIT = 2
STAMINA_LOSS_SYNTAX = 1
MANA_MAX = 30

# Adventure = teach, Timed Practical = measure. Never blur these.
MODE_ADVENTURE = "adventure"
MODE_INTERVIEW = "interview"

INTERVIEW_PROFILES = ("GENERAL_SWE", "PRACTICAL", "SECURITY_ENGINEERING", "CUSTOM")
DEFAULT_PROFILE = "PRACTICAL"

def normalise_profile(name: str | None) -> str:
    """Resolve a stored profile id, however old, to one we still serve.

    The profile id is written into saves, and this build renamed one, so a save
    from an older build carries an id that no longer exists. Falling back to the
    default is the whole migration: there is nothing to preserve beyond "keep
    the game playable", and an unknown id should never strand a run.
    """
    name = (name or "").strip().upper()
    return name if name in INTERVIEW_PROFILES else DEFAULT_PROFILE
