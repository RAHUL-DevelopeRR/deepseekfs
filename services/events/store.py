"""
Neuron — Event Store (SQLite)
==============================
Persistence layer for structured events.
Single responsibility: read/write AgentEvent to SQLite.

Thread-safe. One connection per thread (SQLite requirement).
Indexes on task_id, event_type, timestamp for fast queries.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import List, Dict, Optional

from app.logger import logger
import app.config as config
from services.events.types import AgentEvent


_DB_PATH = str(config.STORAGE_DIR / "events.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      REAL    NOT NULL,
    event_type     TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'success',
    tool_name      TEXT    DEFAULT '',
    duration_ms    INTEGER DEFAULT 0,
    input_summary  TEXT    DEFAULT '',
    output_summary TEXT    DEFAULT '',
    task_id        TEXT    DEFAULT '',
    metadata       TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(timestamp DESC);
"""


class EventStore:
    """SQLite-backed event persistence.
    
    Contract:
      - insert(event) -> int   (returns row ID)
      - query_recent(n) -> list
      - query_by_task(id) -> list
      - stats() -> dict
      - clear() -> None
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()
        # Create schema on init thread
        self._conn().executescript(_SCHEMA)
        self._conn().commit()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn = conn
        return conn

    # ── Write ──────────────────────────────────────────────────

    def insert(self, event: AgentEvent) -> int:
        """Persist an event. Returns its auto-generated ID."""
        with self._write_lock:
            cur = self._conn().execute(
                """INSERT INTO events
                   (timestamp, event_type, status, tool_name,
                    duration_ms, input_summary, output_summary,
                    task_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.timestamp,
                    event.event_type,
                    event.status,
                    event.tool_name,
                    event.duration_ms,
                    event.input_summary[:2000],
                    event.output_summary[:2000],
                    event.task_id,
                    event.metadata[:2000],
                ),
            )
            self._conn().commit()
            return cur.lastrowid

    # ── Read ───────────────────────────────────────────────────

    def query_recent(self, limit: int = 50) -> List[Dict]:
        """Most recent events, newest first."""
        rows = self._conn().execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_task(self, task_id: str) -> List[Dict]:
        """All events for a task, chronological."""
        rows = self._conn().execute(
            "SELECT * FROM events WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_type(self, event_type: str, limit: int = 50) -> List[Dict]:
        """Events filtered by type."""
        rows = self._conn().execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
            (event_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> Dict:
        """Aggregate statistics for the Activity panel."""
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        tool_calls = conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = 'tool_call'"
        ).fetchone()[0]
        errors = conn.execute(
            "SELECT COUNT(*) FROM events WHERE status = 'failed'"
        ).fetchone()[0]
        tasks = conn.execute(
            "SELECT COUNT(DISTINCT task_id) FROM events WHERE task_id != ''"
        ).fetchone()[0]
        return {
            "total_events": total,
            "tool_calls": tool_calls,
            "errors": errors,
            "tasks": tasks,
        }

    # ── Admin ──────────────────────────────────────────────────

    def clear(self):
        """Delete all events."""
        with self._write_lock:
            self._conn().execute("DELETE FROM events")
            self._conn().commit()

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
