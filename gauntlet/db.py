"""Local persistence. SQLite, WAL, atomic writes. Progress is never lost.

Layout is deliberately hybrid: a single authoritative JSON blob for the live
game state (atomic, no migration pain for a single-player local game), plus
normalised tables for the things we genuinely need to *query* — attempt history,
boss records, interview runs.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    payload      TEXT NOT NULL,
    version      INTEGER NOT NULL DEFAULT 1,
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id     TEXT NOT NULL,
    pattern        TEXT NOT NULL,
    family         TEXT NOT NULL,
    difficulty     TEXT NOT NULL,
    mode           TEXT NOT NULL,
    encounter_kind TEXT NOT NULL,
    solved         INTEGER NOT NULL,
    rank           TEXT,
    hints_used     INTEGER NOT NULL DEFAULT 0,
    seconds        REAL NOT NULL DEFAULT 0,
    target_seconds REAL NOT NULL DEFAULT 0,
    runs           INTEGER NOT NULL DEFAULT 0,
    syntax_errors  INTEGER NOT NULL DEFAULT 0,
    tests_passed   INTEGER NOT NULL DEFAULT 0,
    tests_total    INTEGER NOT NULL DEFAULT 0,
    first_try      INTEGER NOT NULL DEFAULT 0,
    is_retest      INTEGER NOT NULL DEFAULT 0,
    root_cause     TEXT,
    declared_pattern TEXT,
    time_to_first_code REAL DEFAULT 0,
    submitted_code TEXT,
    created_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_id);
CREATE INDEX IF NOT EXISTS idx_attempts_family  ON attempts(family);
CREATE INDEX IF NOT EXISTS idx_attempts_time    ON attempts(created_at);

CREATE TABLE IF NOT EXISTS boss_records (
    boss_id     TEXT NOT NULL,
    attempt_no  INTEGER NOT NULL,
    seconds     REAL NOT NULL,
    hints_used  INTEGER NOT NULL,
    rank        TEXT NOT NULL,
    defeated    INTEGER NOT NULL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (boss_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS interview_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile      TEXT NOT NULL,
    format       TEXT NOT NULL,
    problem_ids  TEXT NOT NULL,
    score        REAL NOT NULL,
    solved       INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    seconds      REAL NOT NULL,
    detail       TEXT NOT NULL,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  REAL NOT NULL,
    ended_at    REAL,
    encounters  INTEGER NOT NULL DEFAULT 0,
    xp_gained   INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_state(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        "INSERT INTO state (id, payload, version, updated_at) VALUES (1, ?, 1, ?)"
        " ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,"
        " updated_at=excluded.updated_at",
        (json.dumps(payload), time.time()),
    )
    conn.commit()


def load_state(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT payload FROM state WHERE id = 1").fetchone()
    return json.loads(row["payload"]) if row else None


def record_attempt(conn: sqlite3.Connection, **fields) -> int:
    fields.setdefault("created_at", time.time())
    columns = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO attempts ({columns}) VALUES ({marks})",
                       tuple(fields.values()))
    conn.commit()
    return cur.lastrowid


def attempts_for(conn: sqlite3.Connection, problem_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM attempts WHERE problem_id = ? ORDER BY created_at", (problem_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def recent_attempts(conn: sqlite3.Connection, limit: int = 50) -> list:
    rows = conn.execute(
        "SELECT * FROM attempts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def attempt_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(solved) AS solved,"
        " SUM(CASE WHEN solved = 1 AND hints_used = 0 THEN 1 ELSE 0 END) AS unaided,"
        " SUM(CASE WHEN solved = 1 AND first_try = 1 THEN 1 ELSE 0 END) AS first_try,"
        " AVG(CASE WHEN solved = 1 THEN seconds END) AS avg_seconds"
        " FROM attempts"
    ).fetchone()
    return {k: (row[k] or 0) for k in row.keys()}


def best_time(conn: sqlite3.Connection, problem_id: str) -> float | None:
    row = conn.execute(
        "SELECT MIN(seconds) AS best FROM attempts"
        " WHERE problem_id = ? AND solved = 1", (problem_id,)
    ).fetchone()
    return row["best"] if row and row["best"] else None


def record_boss(conn: sqlite3.Connection, boss_id: str, **fields) -> None:
    row = conn.execute(
        "SELECT COALESCE(MAX(attempt_no), 0) AS n FROM boss_records WHERE boss_id = ?",
        (boss_id,)).fetchone()
    conn.execute(
        "INSERT INTO boss_records (boss_id, attempt_no, seconds, hints_used, rank,"
        " defeated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (boss_id, row["n"] + 1, fields.get("seconds", 0), fields.get("hints_used", 0),
         fields.get("rank", ""), int(fields.get("defeated", False)), time.time()))
    conn.commit()


def boss_history(conn: sqlite3.Connection, boss_id: str | None = None) -> list:
    if boss_id:
        rows = conn.execute(
            "SELECT * FROM boss_records WHERE boss_id = ? ORDER BY attempt_no",
            (boss_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM boss_records ORDER BY boss_id, attempt_no").fetchall()
    return [dict(r) for r in rows]


def record_interview(conn: sqlite3.Connection, **fields) -> int:
    fields.setdefault("created_at", time.time())
    columns = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO interview_runs ({columns}) VALUES ({marks})",
                       tuple(fields.values()))
    conn.commit()
    return cur.lastrowid


def interview_history(conn: sqlite3.Connection, limit: int = 20) -> list:
    rows = conn.execute(
        "SELECT * FROM interview_runs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def export_save(conn: sqlite3.Connection) -> dict:
    return {
        "version": 1,
        "exported_at": time.time(),
        "state": load_state(conn),
        "attempts": recent_attempts(conn, limit=100000),
        "boss_records": boss_history(conn),
        "interview_runs": interview_history(conn, limit=10000),
    }


def import_save(conn: sqlite3.Connection, payload: dict) -> None:
    if payload.get("state"):
        save_state(conn, payload["state"])
    conn.execute("DELETE FROM attempts")
    for row in payload.get("attempts", []):
        row = {k: v for k, v in row.items() if k != "id"}
        record_attempt(conn, **row)
    conn.execute("DELETE FROM boss_records")
    for row in payload.get("boss_records", []):
        conn.execute(
            "INSERT INTO boss_records (boss_id, attempt_no, seconds, hints_used,"
            " rank, defeated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["boss_id"], row["attempt_no"], row["seconds"], row["hints_used"],
             row["rank"], row["defeated"], row["created_at"]))
    conn.commit()
