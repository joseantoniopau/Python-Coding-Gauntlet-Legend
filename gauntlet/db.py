"""Local persistence. SQLite, WAL, atomic writes. Progress is never lost.

Layout is deliberately hybrid: a single authoritative JSON blob for the live
game state (atomic, no migration pain for a single-player local game), plus
normalised tables for the things we genuinely need to *query* — attempt history,
boss records, timed practical runs.
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
    -- WHERE the fight happened, and WHAT THE PLAYER SAID WAS WRONG.
    --
    -- Both are here rather than in the save blob because they are asked as
    -- COUNTING questions -- how many clears in the marsh, how many failures
    -- named before the diagnosis rendered -- and a counting question over a
    -- JSON blob is a loop somebody eventually gets wrong. `region` is what
    -- lets a hidden sage gate on "six encounters cleared in this place"
    -- honestly; `declared_cause` is the player naming the bug before the
    -- grader says, which is the only evidence the Debugging Dungeon's sage
    -- accepts. Both default to '' so every row written before they existed
    -- reads as "not recorded" rather than as a wrong answer.
    region         TEXT NOT NULL DEFAULT '',
    declared_cause TEXT NOT NULL DEFAULT '',
    time_to_first_code REAL DEFAULT 0,
    submitted_code TEXT,
    served_rung    INTEGER,
    evidence_kind  TEXT,
    practice_id    TEXT,
    practice_kind  TEXT,
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

-- The hold-out ledger: one row per sealed problem this player has ever been
-- served, and there is never a second one. That primary key IS the rule that a
-- sealed problem can only be asked once — the lineage is spent the moment it is
-- served, pass, fail or walk away — so the rule lives in the data model rather
-- than in whatever screen happens to render it.
--
-- `first_encounter` is decided at serve time and frozen: it records whether the
-- whole lineage was new to this player right then. A second sibling is not
-- independent evidence of transfer and must never be able to become it later.
CREATE TABLE IF NOT EXISTS transfer_encounters (
    problem_id      TEXT PRIMARY KEY,
    lineage_id      TEXT NOT NULL,
    pattern         TEXT NOT NULL DEFAULT '',
    skill           TEXT NOT NULL DEFAULT '',
    difficulty      TEXT NOT NULL DEFAULT '',
    mode            TEXT NOT NULL DEFAULT '',
    first_encounter INTEGER NOT NULL DEFAULT 0,
    served_at       REAL NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0,
    solved          INTEGER NOT NULL DEFAULT 0,
    unaided         INTEGER NOT NULL DEFAULT 0,
    hints_used      INTEGER NOT NULL DEFAULT 0,
    seconds         REAL NOT NULL DEFAULT 0,
    rank            TEXT NOT NULL DEFAULT '',
    counted         INTEGER NOT NULL DEFAULT 0,
    resolved_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_transfer_lineage ON transfer_encounters(lineage_id);

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
    _add_missing_columns(conn)
    conn.commit()
    return conn


# Columns added to `attempts` after the first release. CREATE TABLE IF NOT
# EXISTS does nothing to a table that is already there, so a save written by an
# older build keeps the older shape and every INSERT naming a new column fails.
# This is the whole migration story for this file: additive columns, defaults
# that read as "not recorded", and no rewriting of history. A player mid-run
# must not lose their game to a schema change.
_ADDED_COLUMNS = (
    ("attempts", "region", "TEXT NOT NULL DEFAULT ''"),
    ("attempts", "declared_cause", "TEXT NOT NULL DEFAULT ''"),
    ("attempts", "served_rung", "INTEGER"),
    ("attempts", "evidence_kind", "TEXT"),
    ("attempts", "practice_id", "TEXT"),
    ("attempts", "practice_kind", "TEXT"),
)


def _add_missing_columns(conn: sqlite3.Connection) -> list:
    """Bring an older `attempts` table up to the current shape. Idempotent."""
    added = []
    for table, column, decl in _ADDED_COLUMNS:
        have = {row["name"] for row in
                conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if not have or column in have:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        added.append(f"{table}.{column}")
    return added


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


def evidence_counters(conn: sqlite3.Connection) -> dict:
    """The counting questions the hidden sages ask, answered in SQL.

    `sages.DISCOVERY` gates on things nothing was measuring: how many
    encounters have been cleared in ONE region, how many regions have been
    touched at all, how many clears landed on the first submission, how many
    lineages have been cleared in two different skins, how many personal bests
    have been broken on a rematch, and how many failures the player NAMED
    before the diagnosis rendered.

    Every one of them is a query over `attempts` and none of them is a new
    number kept somewhere else. That matters more than it looks: a counter
    banked in the save blob is a counter that can disagree with the history it
    was supposed to be counting, and a sage that opens for a player who did not
    do the work is a sage that measures nothing.

    Keyed by PATTERN rather than by skill, because this file does not import
    `skills` and must not start; the caller maps through PATTERN_TO_SKILL,
    which is the one place that mapping lives.
    """
    out: dict = {}

    rows = conn.execute(
        "SELECT region, COUNT(DISTINCT problem_id) AS n FROM attempts"
        " WHERE solved = 1 AND region != '' GROUP BY region").fetchall()
    out["region_clears"] = {r["region"]: r["n"] for r in rows}
    out["regions_touched"] = len(out["region_clears"])

    rows = conn.execute(
        "SELECT pattern, COUNT(*) AS n FROM attempts"
        " WHERE solved = 1 AND first_try = 1 GROUP BY pattern").fetchall()
    out["first_try_by_pattern"] = {r["pattern"]: r["n"] for r in rows}

    # A lineage cleared in two DIFFERENT skins. `family` is the spaced
    # repetition family, which is exactly "the same exercise wearing another
    # face", so two distinct problem ids inside one family is the evidence.
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM (SELECT family FROM attempts"
        " WHERE solved = 1 AND family != '' GROUP BY family"
        " HAVING COUNT(DISTINCT problem_id) >= 2)").fetchone()
    out["lineage_pairs"] = int(row["n"] or 0)

    # A personal best broken on a rematch: a solved attempt that is faster than
    # every EARLIER solved attempt at the same problem. The first clear is not
    # a best broken, which is why the window excludes it.
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM attempts a"
        " WHERE a.solved = 1 AND EXISTS ("
        "   SELECT 1 FROM attempts b WHERE b.problem_id = a.problem_id"
        "     AND b.solved = 1 AND b.created_at < a.created_at)"
        " AND a.seconds < ("
        "   SELECT MIN(b.seconds) FROM attempts b"
        "    WHERE b.problem_id = a.problem_id AND b.solved = 1"
        "      AND b.created_at < a.created_at)").fetchone()
    out["beat_own_time"] = int(row["n"] or 0)

    # The player named the bug and was right, on a submission that FAILED.
    # Naming it after a clear is not a diagnosis, it is a description.
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM attempts"
        " WHERE solved = 0 AND declared_cause != ''"
        "   AND declared_cause = root_cause").fetchone()
    out["root_cause_correct"] = int(row["n"] or 0)

    return out


def best_time(conn: sqlite3.Connection, problem_id: str) -> float | None:
    row = conn.execute(
        "SELECT MIN(seconds) AS best FROM attempts"
        " WHERE problem_id = ? AND solved = 1", (problem_id,)
    ).fetchone()
    return row["best"] if row and row["best"] else None


# ---------------------------------------------------------------------------
# The hold-out ledger
# ---------------------------------------------------------------------------
#
# Two numbers live in this file and they are kept apart on purpose. Ordinary
# mastery is a measure of familiarity and the whole progression depends on it;
# it is computed from `attempts`, exactly as it always was. Transfer readiness
# is computed from this table alone and from nothing else, so neither number can
# quietly borrow evidence from the other.

TRANSFER_FIELDS = ("problem_id", "lineage_id", "pattern", "skill", "difficulty",
                   "mode", "first_encounter", "served_at", "resolved", "solved",
                   "unaided", "hints_used", "seconds", "rank", "counted",
                   "resolved_at")


def open_transfer(conn: sqlite3.Connection, *, problem_id: str, lineage_id: str,
                  pattern: str = "", skill: str = "", difficulty: str = "",
                  mode: str = "", first_encounter: bool = False) -> bool:
    """Spend one hold-out problem. True if this is the first time it was served.

    `INSERT OR IGNORE` rather than an upsert, deliberately: a second serving of
    the same sealed problem must not be able to rewrite `first_encounter`, or
    the one thing this table exists to prove — that the measurement was taken
    cold — becomes a thing the player can retry until it says what they want.
    """
    cur = conn.execute(
        "INSERT OR IGNORE INTO transfer_encounters (problem_id, lineage_id,"
        " pattern, skill, difficulty, mode, first_encounter, served_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (problem_id, lineage_id, pattern, skill, difficulty, mode,
         int(bool(first_encounter)), time.time()))
    conn.commit()
    return bool(cur.rowcount)


def resolve_transfer(conn: sqlite3.Connection, problem_id: str, *, solved: bool,
                     unaided: bool, hints_used: int = 0, seconds: float = 0.0,
                     rank: str = "") -> dict | None:
    """Fold the graded outcome into the ledger row opened when it was served.

    `counted` — whether this encounter moves transfer readiness at all — is
    written here rather than computed at read time, because it is a fact about
    the moment the problem was served and the moment it was graded. It is
    `first_encounter AND unaided`; whether it was SOLVED is the measurement, not
    the admission ticket, or a failed transfer attempt would vanish from its own
    denominator.

    WRITE-ONCE, and that is the whole defence against the cheapest farm there
    is. `open_transfer` already refuses to re-serve a lineage, but a resolved
    row that could be UPDATEd again meant the retry did not need to be a fresh
    serving: fail a sealed problem, ask for it a second time, submit the answer
    you now have, and this UPDATE quietly turned solved=0 into solved=1 in the
    one row the score is computed from. Every sealed problem was therefore
    clearable by brute force and the number went to 100% measuring nothing.
    A graded hold-out encounter is graded once. Later submissions against the
    same problem are ordinary practice — they move mastery through `attempts`
    like anything else — and they return the standing row unchanged, because
    the measurement already happened and it said what it said.
    """
    row = transfer_row(conn, problem_id)
    if row is None:
        return None
    if row["resolved"]:
        return row
    counted = int(bool(row["first_encounter"]) and bool(unaided))
    conn.execute(
        "UPDATE transfer_encounters SET resolved = 1, solved = ?, unaided = ?,"
        " hints_used = ?, seconds = ?, rank = ?, counted = ?, resolved_at = ?"
        " WHERE problem_id = ?",
        (int(bool(solved)), int(bool(unaided)), int(hints_used), float(seconds),
         rank or "", counted, time.time(), problem_id))
    conn.commit()
    return transfer_row(conn, problem_id)


def transfer_row(conn: sqlite3.Connection, problem_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transfer_encounters WHERE problem_id = ?",
        (problem_id,)).fetchone()
    return dict(row) if row else None


def transfer_ledger(conn: sqlite3.Connection) -> list:
    """Every hold-out problem this player has ever been served, oldest first."""
    rows = conn.execute(
        "SELECT * FROM transfer_encounters ORDER BY served_at").fetchall()
    return [dict(r) for r in rows]


def merge_transfer(conn: sqlite3.Connection, rows) -> int:
    """Fold a save file's hold-out ledger into the one on disk, ADDITIVELY.

    Every other table in a save is a timeline: load a slot and your XP, your
    attempts and your quest log go back to where they were, because that is what
    a save slot is for. This table is not a timeline. It is the record of what
    this human being has laid eyes on, and a save file cannot make somebody
    un-see a problem.

    Without that asymmetry the whole measurement is free to farm, in four clicks
    and no cheating tools: save to a slot, sit a sealed problem, fail it, load
    the slot, sit the same sealed problem again now that you have read it and
    thought about it, and the ledger calls that a cold first encounter. Do it
    until the number says 100%. Rolling back was the attack; refusing to roll
    this table back is the answer, and it belongs here rather than in a UI
    confirmation, because the same hole is reachable from a slot load, the undo
    ring and a whole-game import.

    So: rows on disk are never deleted, and the merge of two rows for the same
    problem never claims more than either of them did.

      * `first_encounter` takes the MINIMUM. If either record says the lineage
        had already been met, then it had been met, and this encounter is not
        evidence of transfer.
      * `served_at` takes the earliest, which is when those eyes actually met it.
      * an outcome arrives only where there is not one already: a save carrying
        the graded result of a problem this install served and never resolved
        completes it, and nothing regrades a row that is already resolved.
      * `counted` is recomputed from the merged row, never copied, so it cannot
        arrive pre-set to 1 in a hand-edited file.

    Returns the number of rows written. It does not commit: both callers wrap
    the merge in a transaction of their own, and an inner commit would end the
    import's transaction early and cost it the all-or-nothing it advertises.
    """
    written = 0
    for row in rows or ():
        row = {k: row[k] for k in row.keys() if k in TRANSFER_FIELDS} \
            if hasattr(row, "keys") else dict(row)
        problem_id = row.get("problem_id")
        if not problem_id:
            continue
        current = transfer_row(conn, problem_id)
        if current is None:
            merged = {k: row.get(k) for k in TRANSFER_FIELDS if k in row}
            merged.setdefault("lineage_id", "")
            merged.setdefault("served_at", time.time())
            merged["counted"] = int(bool(merged.get("first_encounter"))
                                    and bool(merged.get("unaided"))
                                    and bool(merged.get("resolved")))
        else:
            merged = dict(current)
            # Never upgrades: a second record cannot promote a known lineage
            # back to "met cold".
            merged["first_encounter"] = int(bool(current["first_encounter"])
                                            and bool(row.get("first_encounter")))
            merged["served_at"] = min(float(current["served_at"] or 0) or 1e18,
                                      float(row.get("served_at") or 0) or 1e18)
            if not current["resolved"] and row.get("resolved"):
                for key in ("resolved", "solved", "unaided", "hints_used",
                            "seconds", "rank", "resolved_at"):
                    merged[key] = row.get(key)
            merged["counted"] = int(bool(merged.get("first_encounter"))
                                    and bool(merged.get("unaided"))
                                    and bool(merged.get("resolved")))
        cols = [k for k in TRANSFER_FIELDS if k in merged]
        conn.execute(
            "INSERT OR REPLACE INTO transfer_encounters (%s) VALUES (%s)"
            % (", ".join(cols), ", ".join("?" * len(cols))),
            tuple(merged[c] for c in cols))
        written += 1
    return written


def transfer_problem_ids(conn: sqlite3.Connection) -> set:
    """Hold-out problems already spent. Part of "what has this player seen"."""
    return {r["problem_id"] for r in
            conn.execute("SELECT problem_id FROM transfer_encounters").fetchall()}


def attempted_problem_ids(conn: sqlite3.Connection) -> set:
    """Every problem with a graded attempt against it. The other part."""
    return {r["problem_id"] for r in
            conn.execute("SELECT DISTINCT problem_id FROM attempts").fetchall()}


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


# 2 adds the hold-out ledger. Older files still load — a version 1 save simply
# has no transfer evidence in it, which is the truth about a save written before
# the hold-out existed.
#
# 3 adds the tactical layer: the potion pouch (state["potions"]), the metal bag
# and the rung each blade line stands at (state["forge"]), and a fight in
# progress — the turn, both status lists, the dose pool and the enemy's focus —
# inside state["encounter"].
#
# This bump is NOT for reading. Every one of those is additive and a build that
# has them fills a missing one from its defaults, so a version 1 or 2 file loads
# here exactly as it always did. It is for WRITING: engine.Encounter is built
# with `Encounter(**raw)`, so a save carrying the new encounter fields handed to
# an older build raises TypeError on a key it has never heard of. With the bump
# that build refuses the file by version and says why, which is a sentence the
# player can act on rather than a traceback. That is the entire job of this
# number, and adding state without touching it is how the number stops doing it.
SAVE_FORMAT_VERSION = 3


def export_save(conn: sqlite3.Connection) -> dict:
    return {
        "version": SAVE_FORMAT_VERSION,
        "exported_at": time.time(),
        "state": load_state(conn),
        "attempts": recent_attempts(conn, limit=100000),
        "boss_records": boss_history(conn),
        "interview_runs": interview_history(conn, limit=10000),
        "transfer_encounters": transfer_ledger(conn),
    }


class InvalidSave(ValueError):
    """A save file we refuse to load, with a reason fit to show a player."""


def _validate_save(payload: object) -> dict:
    """Refuse anything that is not recognisably one of our exports.

    The previous version accepted any dict at all and then unconditionally
    deleted the attempts and boss_records tables, so importing ``{}`` silently
    destroyed every piece of graded evidence the learning engine owns — which
    is the whole save. Anything we cannot positively identify is refused.
    """
    if not isinstance(payload, dict):
        raise InvalidSave("that file is not a save file")
    if "version" not in payload:
        raise InvalidSave("that file has no save-format version")
    try:
        version = int(payload["version"])
    except (TypeError, ValueError):
        raise InvalidSave("that save file's version is not a number") from None
    if version > SAVE_FORMAT_VERSION:
        raise InvalidSave(
            "that save was written by a newer version of the game (format %d, "
            "this build reads up to %d)" % (version, SAVE_FORMAT_VERSION))
    state = payload.get("state")
    if not isinstance(state, dict) or not state:
        raise InvalidSave("that save file has no game state in it")
    for key in ("attempts", "boss_records", "interview_runs",
                "transfer_encounters"):
        if key in payload and not isinstance(payload[key], list):
            raise InvalidSave("that save file's %s section is damaged" % key)
    return payload


def import_save(conn: sqlite3.Connection, payload: dict) -> None:
    """Replace the game with ``payload``, or raise InvalidSave and change nothing.

    History is only cleared when the payload actually carries a replacement for
    it. A save that predates a table keeps what is already on disk rather than
    having it deleted, because losing graded evidence costs the player real work.
    """
    _validate_save(payload)

    with conn:  # one transaction: a mid-import failure rolls the whole thing back
        save_state(conn, payload["state"])

        if "attempts" in payload:
            conn.execute("DELETE FROM attempts")
            for row in payload["attempts"]:
                row = {k: v for k, v in row.items() if k != "id"}
                record_attempt(conn, **row)

        if "boss_records" in payload:
            conn.execute("DELETE FROM boss_records")
            for row in payload["boss_records"]:
                conn.execute(
                    "INSERT INTO boss_records (boss_id, attempt_no, seconds,"
                    " hints_used, rank, defeated, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["boss_id"], row["attempt_no"], row["seconds"],
                     row["hints_used"], row["rank"], row["defeated"],
                     row["created_at"]))

        # The hold-out ledger travels with the save or the import hands the
        # player back a spent hold-out they can spend again. It MERGES rather
        # than replaces — see merge_transfer — because an import that could
        # delete these rows is a one-file undo button on the measurement.
        if "transfer_encounters" in payload:
            merge_transfer(conn, payload["transfer_encounters"])

        # Exported since version 1 and never imported, so a round trip quietly
        # dropped every timed practical result the player had earned.
        if "interview_runs" in payload:
            conn.execute("DELETE FROM interview_runs")
            for row in payload["interview_runs"]:
                cols = [k for k in row.keys() if k != "id"]
                conn.execute(
                    "INSERT INTO interview_runs (%s) VALUES (%s)"
                    % (", ".join(cols), ", ".join("?" * len(cols))),
                    tuple(row[c] for c in cols))
