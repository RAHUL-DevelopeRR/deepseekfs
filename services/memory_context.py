"""Persistent offline context store for MemoryOS."""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Dict, List

import app.config as config
from app.logger import logger


_DB_PATH = str(config.STORAGE_DIR / "memoryos_context.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL DEFAULT 'default',
    role        TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'chat',
    content     TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memoryos_session_created
ON messages(session_id, created_at DESC);
"""


class MemoryContextStore:
    """SQLite-backed conversation memory for offline continuity."""

    def __init__(self, db_path: str = _DB_PATH, session_id: str = "default"):
        self._db_path = db_path
        self._session_id = session_id
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._conn().executescript(_SCHEMA)
        self._conn().commit()
        logger.info(f"MemoryContext: initialized at {db_path}")

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn = conn
        return conn

    def append(self, role: str, content: str, mode: str = "chat") -> None:
        text = (content or "").strip()
        if not text:
            return
        with self._write_lock:
            self._conn().execute(
                """INSERT INTO messages(session_id, role, mode, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (self._session_id, role, mode, text, time.time()),
            )
            self._conn().commit()

    def recent_messages(self, limit: int = 24) -> List[Dict[str, str]]:
        rows = self._conn().execute(
            """SELECT role, mode, content, created_at
               FROM messages
               WHERE session_id = ?
               ORDER BY created_at DESC, id DESC
               LIMIT ?""",
            (self._session_id, max(1, int(limit))),
        ).fetchall()
        return [
            {
                "role": row["role"],
                "mode": row["mode"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in reversed(rows)
        ]

    def format_recent_context(self, limit: int = 12, max_chars: int = 5000) -> str:
        messages = self.recent_messages(limit=limit)
        if not messages:
            return "No prior MemoryOS context."

        lines: list[str] = []
        total = 0
        for msg in messages:
            role = msg["role"].title()
            mode = msg.get("mode") or "chat"
            content = " ".join(str(msg["content"]).split())
            if len(content) > 900:
                content = content[:900].rstrip() + "..."
            line = f"{role} ({mode}): {content}"
            total += len(line)
            if total > max_chars:
                break
            lines.append(line)
        return "\n".join(lines) if lines else "Prior context was too large to include."

    def clear(self) -> None:
        with self._write_lock:
            self._conn().execute(
                "DELETE FROM messages WHERE session_id = ?",
                (self._session_id,),
            )
            self._conn().commit()
        logger.info("MemoryContext: cleared")


_store: MemoryContextStore | None = None
_lock = threading.Lock()


def get_memory_context_store() -> MemoryContextStore:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = MemoryContextStore()
    return _store
