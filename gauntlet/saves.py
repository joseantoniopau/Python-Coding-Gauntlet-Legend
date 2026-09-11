"""Save states: many slots, quiet autosaves, and an undo for the load you regret.

gauntlet/db.py keeps one authoritative row of live state and it stays exactly as
it is — engine.py writes through it after every action. This module adds a
second, independent layer beside that row: eight named slots, a rolling autosave
ring, and a pre-load snapshot, all in a table of its own.

Three rules shaped the design.

  * A load must never be able to destroy what it replaces. Every load snapshots
    the outgoing state first, so a mis-click is one undo away. Players forgive
    almost anything except losing an evening to the wrong slot.
  * A damaged slot is refused, never half-loaded. Length and checksum are proved
    before a single key reaches the engine, because a half-applied save is worse
    than no save at all — it looks like progress and is not.
  * Old saves keep working. A slot from an older build is merged over the current
    DEFAULT_STATE with engine._merge, the same path a live save already takes.
    One migration behaviour in the codebase, not two.

Nothing in here touches db.SCHEMA or db's functions; it only adds tables and
calls the public helpers, so engine.py and whoever is editing it are unaffected.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import zlib
from dataclasses import fields as dataclass_fields
from pathlib import Path

from . import adaptive, config, curriculum, db, srs as srsmod, world
from . import skills as skillmod
from . import story as storymod

# Bump only when the *envelope* changes shape. The game state inside it is
# forward-filled by _merge, so adding keys to DEFAULT_STATE is not a bump.
SCHEMA_VERSION = 1

MANUAL_SLOTS = 8          # named slots the player picks between, 1..8
AUTOSAVE_RING = 4         # rolling, so a bad autosave cannot eat the good one
UNDO_RING = 4             # pre-load snapshots; deep enough to undo an undo

KIND_MANUAL = "manual"
KIND_AUTO = "auto"
KIND_UNDO = "undo"
KINDS = (KIND_MANUAL, KIND_AUTO, KIND_UNDO)

_RING_SIZE = {KIND_MANUAL: MANUAL_SLOTS, KIND_AUTO: AUTOSAVE_RING, KIND_UNDO: UNDO_RING}
_PREFIX = {KIND_MANUAL: "slot", KIND_AUTO: "auto", KIND_UNDO: "undo"}
_KIND_BY_PREFIX = {v: k for k, v in _PREFIX.items()}

# The moments worth autosaving at. Permissive on purpose: another agent adding a
# new trigger should not have to edit this file to use it.
AUTOSAVE_EVENTS = {
    "encounter_cleared": "Encounter cleared",
    "region_entered": "Entered a new region",
    "boss_defeated": "Boss defeated",
    "quest_turned_in": "Quest turned in",
    "level_gained": "Level gained",
    "session_end": "Session ended",
}

EXPORT_KIND = "gauntlet-save-slot"
EXPORT_GAME_KIND = "gauntlet-save-game"

SCHEMA = """
CREATE TABLE IF NOT EXISTS save_slots (
    slot_id        TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    ordinal        INTEGER NOT NULL,
    name           TEXT NOT NULL DEFAULT '',
    reason         TEXT NOT NULL DEFAULT '',
    schema_version INTEGER NOT NULL,
    app_version    TEXT NOT NULL DEFAULT '',
    codec          TEXT NOT NULL DEFAULT 'zlib+json',
    body           BLOB NOT NULL,
    body_sha       TEXT NOT NULL,
    body_len       INTEGER NOT NULL,
    has_history    INTEGER NOT NULL DEFAULT 0,
    consumed       INTEGER NOT NULL DEFAULT 0,
    summary        TEXT NOT NULL DEFAULT '{}',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_save_slots_kind ON save_slots(kind, updated_at);
"""


# ---------------------------------------------------------------------------
# Failures the caller is expected to show the player, verbatim
# ---------------------------------------------------------------------------

class SaveError(Exception):
    """Anything the save layer refuses to do. The message is player-facing."""


class SlotNotFound(SaveError):
    pass


class SaveCorrupt(SaveError):
    """The slot exists and is unreadable. Never partially applied."""


# ---------------------------------------------------------------------------
# Connection and ids
# ---------------------------------------------------------------------------

def ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent, and cheap enough to call from every entry point so that no
    caller has to remember to. The existence probe keeps the common case to one
    indexed lookup instead of re-running the script on every slot read."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'save_slots'"
    ).fetchone()
    if row is None:
        conn.executescript(SCHEMA)
        conn.commit()


def connect(path: Path | None = None) -> sqlite3.Connection:
    """db.connect plus this module's tables, for tools that only want saves."""
    conn = db.connect(path)
    ensure_schema(conn)
    return conn


def slot_id(kind: str, ordinal: int) -> str:
    if kind not in KINDS:
        raise SaveError(f"Unknown save kind {kind!r}.")
    size = _RING_SIZE[kind]
    low = 1 if kind == KIND_MANUAL else 0
    if not low <= int(ordinal) < low + size:
        raise SaveError(f"Slot {ordinal} is out of range for {kind} saves "
                        f"({low}-{low + size - 1}).")
    return f"{_PREFIX[kind]}:{int(ordinal)}"


def parse_slot_id(value) -> tuple:
    """Accepts 'slot:3', 'auto:1', or a bare 3 meaning manual slot three."""
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return KIND_MANUAL, int(value)
    text = str(value or "").strip().lower()
    prefix, _, rest = text.partition(":")
    if prefix not in _KIND_BY_PREFIX or not rest.isdigit():
        raise SaveError(f"{value!r} is not a save slot id.")
    return _KIND_BY_PREFIX[prefix], int(rest)


def _canonical_id(value) -> str:
    kind, ordinal = parse_slot_id(value)
    return slot_id(kind, ordinal)


# ---------------------------------------------------------------------------
# Encoding. Compressed because manual slots carry attempt history, checksummed
# because the only thing worse than losing a save is loading half of one.
# ---------------------------------------------------------------------------

def _encode(payload: dict) -> tuple:
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SaveError("Refusing to write a save that will not serialise "
                        f"cleanly: {exc}") from exc
    return zlib.compress(raw, 6), hashlib.sha256(raw).hexdigest(), len(raw)


def _decode(row) -> dict:
    """Prove the bytes before trusting them. Every failure path raises."""
    sid = row["slot_id"]
    version = int(row["schema_version"] or 0)
    if version > SCHEMA_VERSION:
        raise SaveCorrupt(
            f"Save {sid} was written by a newer build (format {version}; this "
            f"build reads {SCHEMA_VERSION}). Refusing to load it rather than "
            "guess at the parts it does not understand.")
    if (row["codec"] or "zlib+json") != "zlib+json":
        raise SaveCorrupt(f"Save {sid} uses an unknown encoding "
                          f"({row['codec']}). Nothing was loaded.")
    body = row["body"]
    if not body:
        raise SaveCorrupt(f"Save {sid} is empty. Nothing was loaded.")
    try:
        raw = zlib.decompress(bytes(body))
    except zlib.error as exc:
        raise SaveCorrupt(
            f"Save {sid} is damaged and cannot be unpacked ({exc}). The slot "
            "was left exactly as it was and your current game is untouched."
        ) from exc
    if len(raw) != int(row["body_len"] or -1):
        raise SaveCorrupt(
            f"Save {sid} is truncated: {len(raw)} bytes where {row['body_len']} "
            "were written. Refusing to load a partial game.")
    if hashlib.sha256(raw).hexdigest() != row["body_sha"]:
        raise SaveCorrupt(
            f"Save {sid} failed its checksum — the file changed since it was "
            "written. Refusing to load it; your current game is untouched.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SaveCorrupt(f"Save {sid} is not readable JSON ({exc}). "
                          "Nothing was loaded.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
        raise SaveCorrupt(f"Save {sid} is missing its game state. Nothing was loaded.")
    return payload


def _row(conn: sqlite3.Connection, sid: str):
    ensure_schema(conn)
    return conn.execute("SELECT * FROM save_slots WHERE slot_id = ?", (sid,)).fetchone()


def _require_row(conn: sqlite3.Connection, sid: str):
    row = _row(conn, sid)
    if row is None:
        raise SlotNotFound(f"Save {sid} is empty.")
    return row


# ---------------------------------------------------------------------------
# Forward compatibility. One migration path, borrowed from the engine.
# ---------------------------------------------------------------------------

def normalize(raw: dict) -> dict:
    """Merge a stored state over today's defaults, exactly as engine does on
    boot. Imported here rather than reimplemented so an old save can never take
    a different migration path than a live one."""
    from . import engine                      # local: engine imports db, not us

    merged = json.loads(json.dumps(engine.DEFAULT_STATE))   # cheap deep copy
    engine._merge(merged, raw or {})
    for name in skillmod.SKILLS:
        merged["skills"].setdefault(name, skillmod.SkillState(name=name).to_dict())
    if not merged.get("story"):
        merged["story"] = storymod.new_story_state()
    return merged


# ---------------------------------------------------------------------------
# Summaries — what the player actually chooses between
# ---------------------------------------------------------------------------

_REGION_BY_ID = {r["id"]: r for r in world.REGIONS}
_BOSS_BY_ID = {b["id"]: b for b in world.BOSSES}
_SKILL_FIELDS = {f.name for f in dataclass_fields(skillmod.SkillState)}


def _skill_states(state: dict) -> dict:
    """Tolerant of old and new save shapes: unknown keys are dropped, missing
    skills are filled, because a summary must never be the thing that fails."""
    out = {}
    for name, data in (state.get("skills") or {}).items():
        if not isinstance(data, dict):
            continue
        clean = {k: v for k, v in data.items() if k in _SKILL_FIELDS}
        clean["name"] = name
        try:
            out[name] = skillmod.SkillState(**clean)
        except TypeError:
            out[name] = skillmod.SkillState(name=name)
    for name in skillmod.SKILLS:
        out.setdefault(name, skillmod.SkillState(name=name))
    return out


def _readiness_overall(conn, state: dict, skills: dict) -> int:
    """The headline readiness number, computed the same way the engine does.
    Without a connection we have no graded evidence to stand on, so we say so
    by returning zero rather than inventing a figure from exploration."""
    if conn is None:
        return 0
    stats = db.attempt_stats(conn)
    rows = conn.execute(
        "SELECT difficulty, COUNT(DISTINCT problem_id) AS n FROM attempts"
        " WHERE solved = 1 AND hints_used = 0 GROUP BY difficulty").fetchall()
    counts = {r["difficulty"]: r["n"] for r in rows}
    schedule = {}
    for key, data in (state.get("schedule") or {}).items():
        try:
            schedule[key] = srsmod.ScheduleEntry(**data)
        except TypeError:
            continue
    ready = adaptive.readiness(
        skills=skills, schedule=schedule, stats=stats,
        unaided_easy=counts.get("EASY", 0) + counts.get("TUTORIAL", 0),
        unaided_medium=counts.get("MEDIUM", 0))
    return int(ready.get("overall", 0))


def format_playtime(seconds: float) -> str:
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m" if minutes else "under a minute"


def _last_event(state: dict, note: str, reason: str) -> str:
    """What was happening when this save was taken, in the player's terms."""
    if note:
        return note
    if reason:
        return AUTOSAVE_EVENTS.get(reason, reason.replace("_", " ").capitalize())
    fired = (state.get("story") or {}).get("fired") or []
    for entry_id in reversed(fired[-6:]):
        beat = storymod.MAIN_BY_ID.get(entry_id)
        if beat is not None:
            return beat.title
        pair = storymod.STEP_BY_ID.get(entry_id)
        if pair is not None:
            return f"{pair[0].title}: {pair[1].title}"
        milestone = storymod.MILESTONE_BY_ID.get(entry_id)
        if milestone is not None:
            return milestone.name
    cleared = state.get("cleared_bosses") or []
    if cleared:
        boss = _BOSS_BY_ID.get(cleared[-1], {})
        return f"Defeated {boss.get('name', cleared[-1])}"
    solved = len(state.get("solved_ids") or [])
    return f"{solved} problems solved" if solved else "A new game"


def summarize(state: dict, *, conn: sqlite3.Connection | None = None,
              readiness: dict | None = None, note: str = "",
              reason: str = "") -> dict:
    """The human-choosable card for a slot. Deliberately total: any piece that
    cannot be computed degrades to a sane default, because a save must never
    fail on account of its own description."""
    state = state or {}
    player = state.get("player") or {}
    skills = _skill_states(state)
    try:
        chapter = curriculum.next_objective(skills)
    except Exception:
        chapter = {"number": 1, "total": len(curriculum.CHAPTERS),
                   "title": curriculum.CHAPTERS[0].title, "id": curriculum.CHAPTERS[0].id}
    region_id = player.get("region") or "python_village"
    region = _REGION_BY_ID.get(region_id, {})
    xp = int(player.get("xp", 0) or 0)
    # XP is the ledger; the stored level is a cache the engine refreshes on its
    # next status pass. Derive from XP so a save taken mid-flight is not a level
    # behind on the card the player chooses from.
    level = world.level_for(xp) if xp else int(player.get("level", 1) or 1)
    if readiness is not None:
        overall = int(readiness.get("overall", 0))
    else:
        try:
            overall = _readiness_overall(conn, state, skills)
        except Exception:
            overall = 0
    playtime = float(player.get("playtime_seconds", 0.0) or 0.0)
    return {
        "player_name": player.get("name", "The Security Architect"),
        "level": level,
        "xp": xp,
        "gold": int(player.get("gold", 0) or 0),
        "title": world.title_for(level) or player.get("title", ""),
        "honorific": storymod.honorific(state.get("story") or {}),
        "chapter_number": chapter.get("number", 1),
        "chapter_total": chapter.get("total", len(curriculum.CHAPTERS)),
        "chapter_title": chapter.get("title", ""),
        "chapter_id": chapter.get("id", ""),
        "region_id": region_id,
        "region": region.get("name", region_id.replace("_", " ").title()),
        "readiness": overall,
        "playtime_seconds": playtime,
        "playtime": format_playtime(playtime),
        "last_event": _last_event(state, note, reason),
        "solved": len(state.get("solved_ids") or []),
        "bosses_cleared": len(state.get("cleared_bosses") or []),
        "secrets_found": len(state.get("secrets_found") or []),
        "in_encounter": bool(state.get("encounter")),
        "saved_at": time.time(),
    }


# ---------------------------------------------------------------------------
# History capture. Manual slots carry the graded record with them; autosaves do
# not, because writing every attempt row six times an hour is how a local save
# file turns into a hundred megabytes of duplicated evidence.
# ---------------------------------------------------------------------------

def capture_history(conn: sqlite3.Connection) -> dict:
    return {
        "attempts": db.recent_attempts(conn, limit=1000000),
        "boss_records": db.boss_history(conn),
        "interview_runs": db.interview_history(conn, limit=1000000),
    }


def _restore_history(conn: sqlite3.Connection, history: dict) -> int:
    """Replace the queryable tables with the snapshot's. Destructive by design —
    a save state is a timeline, not a merge — and always reversible, because the
    undo snapshot taken before a load carries history whenever the incoming save
    does."""
    written = 0
    conn.execute("DELETE FROM attempts")
    for row in history.get("attempts") or []:
        db.record_attempt(conn, **{k: v for k, v in row.items() if k != "id"})
        written += 1
    conn.execute("DELETE FROM boss_records")
    for row in history.get("boss_records") or []:
        conn.execute(
            "INSERT INTO boss_records (boss_id, attempt_no, seconds, hints_used,"
            " rank, defeated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["boss_id"], row["attempt_no"], row["seconds"], row["hints_used"],
             row["rank"], row["defeated"], row["created_at"]))
        written += 1
    conn.execute("DELETE FROM interview_runs")
    for row in history.get("interview_runs") or []:
        db.record_interview(conn, **{k: v for k, v in row.items() if k != "id"})
        written += 1
    conn.commit()
    return written


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _ring_slot(conn: sqlite3.Connection, kind: str, *, exclude: str = "") -> int:
    """Free ordinal if there is one, otherwise the oldest — which is what makes
    the ring a safety net instead of a single overwritable file."""
    size = _RING_SIZE[kind]
    rows = conn.execute(
        "SELECT slot_id, ordinal, updated_at FROM save_slots WHERE kind = ?",
        (kind,)).fetchall()
    used = {int(r["ordinal"]): float(r["updated_at"]) for r in rows
            if int(r["ordinal"]) < size}
    # `exclude` is a slot we are about to read from, so it is off limits as a
    # write target — overwriting it would consume the very snapshot being used.
    spoken_for = {ordinal for slot, ordinal in
                  ((r["slot_id"], int(r["ordinal"])) for r in rows)
                  if slot == exclude}
    for n in range(size):
        if n not in used and n not in spoken_for:
            return n
    candidates = {n: t for n, t in used.items() if n not in spoken_for}
    if not candidates:
        raise SaveError(f"No {kind} slot is free to write.")
    return min(candidates, key=lambda n: candidates[n])


def _write(conn: sqlite3.Connection, kind: str, ordinal: int, state: dict, *,
           name: str = "", reason: str = "", note: str = "",
           readiness: dict | None = None, include_history: bool = False) -> dict:
    ensure_schema(conn)
    sid = slot_id(kind, ordinal)
    summary = summarize(state, conn=conn, readiness=readiness, note=note, reason=reason)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": config.VERSION,
        "saved_at": summary["saved_at"],
        "state": state,
        "summary": summary,
    }
    if include_history:
        payload["history"] = capture_history(conn)
    body, sha, length = _encode(payload)
    now = time.time()
    existing = _row(conn, sid)
    created = float(existing["created_at"]) if existing else now
    label = name or (existing["name"] if existing else "") or _default_name(kind, ordinal)
    conn.execute(
        "INSERT INTO save_slots (slot_id, kind, ordinal, name, reason,"
        " schema_version, app_version, codec, body, body_sha, body_len,"
        " has_history, consumed, summary, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)"
        " ON CONFLICT(slot_id) DO UPDATE SET"
        " name=excluded.name, reason=excluded.reason,"
        " schema_version=excluded.schema_version, app_version=excluded.app_version,"
        " codec=excluded.codec, body=excluded.body, body_sha=excluded.body_sha,"
        " body_len=excluded.body_len, has_history=excluded.has_history,"
        " consumed=0, summary=excluded.summary, updated_at=excluded.updated_at",
        (sid, kind, int(ordinal), label, reason, SCHEMA_VERSION, config.VERSION,
         "zlib+json", sqlite3.Binary(body), sha, length, int(include_history),
         json.dumps(summary), created, now))
    conn.commit()
    return describe(conn, sid)


def _default_name(kind: str, ordinal: int) -> str:
    if kind == KIND_MANUAL:
        return f"Slot {ordinal}"
    if kind == KIND_AUTO:
        return f"Autosave {ordinal + 1}"
    return f"Before load {ordinal + 1}"


def save_to_slot(conn: sqlite3.Connection, ordinal, state: dict, *,
                 name: str = "", note: str = "", readiness: dict | None = None,
                 include_history: bool = True) -> dict:
    """Write the live state into one of the named slots the player picks."""
    kind, number = parse_slot_id(ordinal)
    if kind != KIND_MANUAL:
        raise SaveError("save_to_slot writes named slots only; use autosave() "
                        "or snapshot_for_undo() for the rings.")
    return _write(conn, KIND_MANUAL, number, state, name=name, note=note,
                  reason="manual", readiness=readiness,
                  include_history=include_history)


def autosave(conn: sqlite3.Connection, state: dict, reason: str, *,
             note: str = "", readiness: dict | None = None,
             include_history: bool = False) -> dict | None:
    """Quiet, frequent, and rolling. Returns None when the state is byte-for-byte
    what the newest autosave already holds, so an idle loop cannot rotate the
    good saves out of the ring with copies of the same moment."""
    ensure_schema(conn)
    _, state_sha, _ = _encode({"state": state})
    newest = conn.execute(
        "SELECT summary FROM save_slots WHERE kind = ? ORDER BY updated_at DESC"
        " LIMIT 1", (KIND_AUTO,)).fetchone()
    if newest is not None:
        try:
            previous = json.loads(newest["summary"] or "{}").get("state_sha")
        except ValueError:
            previous = None
        if previous == state_sha:
            return None
    ordinal = _ring_slot(conn, KIND_AUTO)
    written = _write(conn, KIND_AUTO, ordinal, state, reason=reason, note=note,
                     readiness=readiness, include_history=include_history)
    # Stamp the state fingerprint into the stored summary so the next autosave
    # can tell "nothing happened" from "something happened that looks similar".
    row = _require_row(conn, written["slot_id"])
    summary = json.loads(row["summary"] or "{}")
    summary["state_sha"] = state_sha
    conn.execute("UPDATE save_slots SET summary = ? WHERE slot_id = ?",
                 (json.dumps(summary), written["slot_id"]))
    conn.commit()
    written["summary"] = summary
    return written


def snapshot_for_undo(conn: sqlite3.Connection, state: dict, *, note: str = "",
                      include_history: bool = False,
                      readiness: dict | None = None,
                      exclude: str = "") -> dict:
    """The safety net. Taken before every load, including loads that go fine."""
    ordinal = _ring_slot(conn, KIND_UNDO, exclude=exclude)
    return _write(conn, KIND_UNDO, ordinal, state, reason="pre_load",
                  note=note or "State replaced by a load", readiness=readiness,
                  include_history=include_history)


def rename_slot(conn: sqlite3.Connection, sid, name: str) -> dict:
    target = _canonical_id(sid)
    _require_row(conn, target)
    conn.execute("UPDATE save_slots SET name = ? WHERE slot_id = ?",
                 (name.strip()[:60], target))
    conn.commit()
    return describe(conn, target)


def delete_slot(conn: sqlite3.Connection, sid) -> dict:
    target = _canonical_id(sid)
    _require_row(conn, target)
    conn.execute("DELETE FROM save_slots WHERE slot_id = ?", (target,))
    conn.commit()
    return {"ok": True, "slot_id": target}


# ---------------------------------------------------------------------------
# Reading, listing, verifying
# ---------------------------------------------------------------------------

def describe(conn: sqlite3.Connection, sid) -> dict:
    """The catalogue entry for one slot. Reads the summary column, so it stays
    cheap and works even when the body turns out to be unreadable."""
    target = _canonical_id(sid)
    row = _require_row(conn, target)
    kind, ordinal = parse_slot_id(target)
    try:
        summary = json.loads(row["summary"] or "{}")
    except ValueError:
        summary = {}
    return {
        "slot_id": target, "kind": kind, "ordinal": ordinal,
        "name": row["name"], "reason": row["reason"],
        "reason_label": AUTOSAVE_EVENTS.get(row["reason"], ""),
        "schema_version": int(row["schema_version"]),
        "app_version": row["app_version"],
        "has_history": bool(row["has_history"]),
        "consumed": bool(row["consumed"]),
        "bytes": int(row["body_len"]),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "empty": False,
        "summary": summary,
    }


def _empty_entry(kind: str, ordinal: int) -> dict:
    return {
        "slot_id": slot_id(kind, ordinal), "kind": kind, "ordinal": ordinal,
        "name": _default_name(kind, ordinal), "reason": "", "reason_label": "",
        "schema_version": SCHEMA_VERSION, "app_version": "", "has_history": False,
        "consumed": False, "bytes": 0, "created_at": 0.0, "updated_at": 0.0,
        "empty": True, "summary": {}, "status": "empty", "message": "",
    }


def verify_slot(conn: sqlite3.Connection, sid) -> dict:
    """Non-destructive integrity check. Never raises for a damaged slot — the
    save screen has to be able to show a bad slot, not crash on it."""
    target = _canonical_id(sid)
    row = _row(conn, target)
    if row is None:
        return {"slot_id": target, "ok": False, "status": "empty", "message": ""}
    try:
        _decode(row)
    except SaveCorrupt as exc:
        return {"slot_id": target, "ok": False, "status": "corrupt",
                "message": str(exc)}
    return {"slot_id": target, "ok": True, "status": "ok", "message": ""}


def list_slots(conn: sqlite3.Connection, *, kinds=None,
               include_empty: bool = True, verify: bool = True) -> list:
    """Everything the save screen needs in one call, corrupt slots included and
    labelled, so the player can never pick a dead one by accident."""
    ensure_schema(conn)
    wanted = tuple(kinds) if kinds else KINDS
    out = []
    for kind in wanted:
        low = 1 if kind == KIND_MANUAL else 0
        for ordinal in range(low, low + _RING_SIZE[kind]):
            sid = slot_id(kind, ordinal)
            if _row(conn, sid) is None:
                if include_empty:
                    out.append(_empty_entry(kind, ordinal))
                continue
            entry = describe(conn, sid)
            check = verify_slot(conn, sid) if verify else {"status": "unchecked",
                                                           "message": ""}
            entry["status"] = check["status"]
            entry["message"] = check["message"]
            out.append(entry)
    return out


def verify_all(conn: sqlite3.Connection) -> list:
    ensure_schema(conn)
    rows = conn.execute("SELECT slot_id FROM save_slots ORDER BY slot_id").fetchall()
    return [verify_slot(conn, r["slot_id"]) for r in rows]


def read_slot(conn: sqlite3.Connection, sid) -> dict:
    """Decoded, verified payload. Raises rather than returning a half-state."""
    target = _canonical_id(sid)
    return _decode(_require_row(conn, target))


# ---------------------------------------------------------------------------
# Loading — and the undo that makes loading safe
# ---------------------------------------------------------------------------

def apply_state(conn: sqlite3.Connection, state: dict) -> dict:
    """Write a state into the live row db/engine read from. The caller still has
    to adopt the returned dict as its own in-memory state."""
    db.save_state(conn, state)
    return state


def load_slot(conn: sqlite3.Connection, sid, *, current_state: dict | None = None,
              apply: bool = True, restore_history: bool = True) -> dict:
    """Load a slot over the live game.

    The outgoing state is snapshotted into the undo ring BEFORE anything is
    written, and the decode is proved BEFORE the snapshot is spent, so the three
    ways this can go wrong — corrupt slot, missing slot, wrong slot — all leave
    the player either untouched or one undo_load() away from untouched.
    """
    target = _canonical_id(sid)
    payload = _decode(_require_row(conn, target))          # refuses before it acts
    state = normalize(payload.get("state") or {})
    history = payload.get("history") if restore_history else None

    undo_id = ""
    if current_state is not None:
        # Carry history in the snapshot whenever the load will overwrite it,
        # otherwise undo would restore the state and lose the graded record.
        snap = snapshot_for_undo(
            conn, current_state, include_history=bool(history),
            note=f"Before loading {describe(conn, target)['name']}")
        undo_id = snap["slot_id"]

    restored = 0
    if apply:
        apply_state(conn, state)
        if history:
            restored = _restore_history(conn, history)

    return {
        "ok": True,
        "slot_id": target,
        "state": state,
        "summary": payload.get("summary") or summarize(state, conn=conn),
        "undo_slot": undo_id,
        "undo_available": bool(undo_id),
        "history_rows": restored,
        "applied": bool(apply),
        "from_version": int(payload.get("schema_version", 0) or 0),
    }


def undo_available(conn: sqlite3.Connection) -> bool:
    ensure_schema(conn)
    row = conn.execute(
        "SELECT 1 FROM save_slots WHERE kind = ? AND consumed = 0 LIMIT 1",
        (KIND_UNDO,)).fetchone()
    return row is not None


def undo_load(conn: sqlite3.Connection, *, current_state: dict | None = None,
              apply: bool = True) -> dict:
    """Step back to the state the last load replaced.

    The state being undone is itself pushed onto the ring first, so a second
    undo walks forward again. That is not cleverness for its own sake: a player
    who undoes by reflex needs the way back as much as the way out.
    """
    ensure_schema(conn)
    row = conn.execute(
        "SELECT * FROM save_slots WHERE kind = ? AND consumed = 0"
        " ORDER BY updated_at DESC LIMIT 1", (KIND_UNDO,)).fetchone()
    if row is None:
        raise SaveError("There is nothing to undo — no load has replaced your "
                        "game since this save file was made.")
    payload = _decode(row)                                  # prove it first
    state = normalize(payload.get("state") or {})
    history = payload.get("history")

    if current_state is not None:
        snapshot_for_undo(conn, current_state, include_history=bool(history),
                          note="Before undo", exclude=row["slot_id"])

    restored = 0
    if apply:
        apply_state(conn, state)
        if history:
            restored = _restore_history(conn, history)

    conn.execute("UPDATE save_slots SET consumed = 1 WHERE slot_id = ?",
                 (row["slot_id"],))
    conn.commit()
    return {
        "ok": True,
        "slot_id": row["slot_id"],
        "state": state,
        "summary": payload.get("summary") or summarize(state, conn=conn),
        "history_rows": restored,
        "applied": bool(apply),
    }


# ---------------------------------------------------------------------------
# Portable files
# ---------------------------------------------------------------------------

def _write_file(path: Path, payload: dict) -> Path:
    """Temp file then replace, so an interrupted export cannot leave a half file
    sitting where a whole one used to be."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def export_slot(conn: sqlite3.Connection, sid, path=None) -> dict:
    """One slot as a portable file. The envelope repeats the checksum so a file
    mangled in transit is refused on import for the same reason a mangled slot
    is refused on load."""
    target = _canonical_id(sid)
    row = _require_row(conn, target)
    payload = _decode(row)                                   # never export junk
    envelope = {
        "kind": EXPORT_KIND,
        "slot_id": target,
        "schema_version": SCHEMA_VERSION,
        "app_version": config.VERSION,
        "exported_at": time.time(),
        "name": row["name"],
        "checksum": row["body_sha"],
        "length": int(row["body_len"]),
        "summary": json.loads(row["summary"] or "{}"),
        "payload": payload,
    }
    if path is not None:
        envelope["path"] = str(_write_file(Path(path), envelope))
    return envelope


def _read_envelope(source) -> dict:
    if isinstance(source, dict):
        return source
    path = Path(str(source)).expanduser()
    if not path.exists():
        raise SaveError(f"No save file at {path}.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SaveCorrupt(f"{path.name} is not a readable save file ({exc}). "
                          "Nothing was imported.") from exc


def _verify_envelope(envelope: dict) -> dict:
    """Same bar a slot on disk has to clear, applied to a file. Returns the
    payload; raises before anything is written."""
    if envelope.get("kind") != EXPORT_KIND:
        raise SaveCorrupt("That file is not a single-slot save export. "
                          "Nothing was imported.")
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
        raise SaveCorrupt("That save file has no game state in it. "
                          "Nothing was imported.")
    version = int(payload.get("schema_version", envelope.get("schema_version", 0)) or 0)
    if version > SCHEMA_VERSION:
        raise SaveCorrupt(
            f"That save was written by a newer build (format {version}; this "
            f"build reads {SCHEMA_VERSION}). Nothing was imported.")
    claimed = envelope.get("checksum")
    if claimed:
        _, actual, length = _encode(payload)
        if actual != claimed or int(envelope.get("length", length)) != length:
            raise SaveCorrupt("That save file failed its checksum — it was "
                              "changed or truncated since it was exported. "
                              "Nothing was imported.")
    return payload


def import_slot(conn: sqlite3.Connection, source, *, ordinal=None,
                name: str = "") -> dict:
    """Bring a portable file back into a named slot. Verified before it lands,
    and it lands in a slot — never straight over the live game."""
    ensure_schema(conn)
    envelope = _read_envelope(source)
    payload = _verify_envelope(envelope)
    if ordinal is None:
        free = [n for n in range(1, MANUAL_SLOTS + 1)
                if _row(conn, slot_id(KIND_MANUAL, n)) is None]
        if not free:
            raise SaveError("Every named slot is full. Pick one to overwrite "
                            "and import again.")
        number = free[0]
    else:
        kind, number = parse_slot_id(ordinal)
        if kind != KIND_MANUAL:
            raise SaveError("Imports land in named slots, not in the autosave "
                            "or undo rings.")
    state = normalize(payload.get("state") or {})
    summary = payload.get("summary") or {}
    return _write(conn, KIND_MANUAL, number, state,
                  name=name or envelope.get("name") or "Imported save",
                  reason="imported",
                  note=summary.get("last_event", "Imported from a file"),
                  include_history=bool(payload.get("history")))


def _restore_exported_slot(conn: sqlite3.Connection, envelope: dict) -> dict:
    """Put an exported slot back where it came from, autosaves included, so a
    whole-game export round-trips to the same save screen the player left."""
    inner = _verify_envelope(envelope)
    kind, ordinal = parse_slot_id(envelope.get("slot_id") or "slot:1")
    summary = inner.get("summary") or {}
    return _write(conn, kind, ordinal, normalize(inner.get("state") or {}),
                  name=envelope.get("name") or _default_name(kind, ordinal),
                  reason=summary.get("reason") or "imported",
                  note=summary.get("last_event", ""),
                  include_history=bool(inner.get("history")))


def export_game(conn: sqlite3.Connection, *, include_slots: bool = True,
                path=None) -> dict:
    """The existing whole-game export, plus the slots. db.export_save is called
    unchanged and its keys are untouched, so anything already reading that shape
    — engine.export, /api/export, the tests — keeps working."""
    payload = db.export_save(conn)
    payload["kind"] = EXPORT_GAME_KIND
    if include_slots:
        ensure_schema(conn)
        slots = []
        for row in conn.execute(
                "SELECT slot_id FROM save_slots WHERE kind IN (?, ?)"
                " ORDER BY kind, ordinal", (KIND_MANUAL, KIND_AUTO)).fetchall():
            try:
                slots.append(export_slot(conn, row["slot_id"]))
            except SaveCorrupt:
                continue          # a damaged slot is not worth carrying forward
        payload["slots"] = slots
    if path is not None:
        payload["path"] = str(_write_file(Path(path), payload))
    return payload


def import_game(conn: sqlite3.Connection, source) -> dict:
    """The mirror of export_game. Whole-game payloads written before this module
    existed import exactly as they did before — they simply have no slots."""
    payload = _read_envelope(source)
    db.import_save(conn, payload)
    ensure_schema(conn)
    restored, refused = 0, 0
    for envelope in payload.get("slots") or []:
        try:
            _restore_exported_slot(conn, envelope)
            restored += 1
        except SaveError:
            refused += 1          # one bad slot does not sink the whole import
    return {"ok": True, "slots_restored": restored, "slots_refused": refused}
