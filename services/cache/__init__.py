"""
Neuron — Response Cache (SQLite)
=================================
Persistent LRU cache for LLM responses.

Maps query keys to cached responses so repeated questions
return instantly (0ms) without LLM inference.

Thread-safe. WAL mode for concurrent reads.
Evicts oldest entries when max size exceeded.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Optional

from app.logger import logger
import app.config as config


_DB_PATH = str(config.STORAGE_DIR / "response_cache.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    response   TEXT NOT NULL,
    created_at REAL NOT NULL,
    hit_count  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cache_ts ON cache(created_at ASC);
"""

DEFAULT_MAX_SIZE = 256


class ResponseCache:
    """SQLite-backed LRU response cache.
    
    Contract:
      - get(key) -> str | None    (cache hit/miss)
      - put(key, response)        (insert + evict if needed)
      - stats() -> dict           (hit rate, size)
      - clear()                   (wipe all entries)
    """

    def __init__(self, db_path: str = _DB_PATH, max_size: int = DEFAULT_MAX_SIZE):
        self._db_path = db_path
        self._max_size = max_size
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        # Create schema
        self._conn().executescript(_SCHEMA)
        self._conn().commit()
        logger.info(f"ResponseCache: initialized at {db_path}")

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn = conn
        return conn

    # ── Read ───────────────────────────────────────────────────

    def get(self, key: str) -> Optional[str]:
        """Look up a cached response. Returns None on miss."""
        row = self._conn().execute(
            "SELECT response FROM cache WHERE key = ?", (key,)
        ).fetchone()

        if row is not None:
            self._hits += 1
            # Bump hit count (non-blocking, best-effort)
            try:
                self._conn().execute(
                    "UPDATE cache SET hit_count = hit_count + 1 WHERE key = ?",
                    (key,),
                )
                self._conn().commit()
            except Exception:
                pass
            return row["response"]

        self._misses += 1
        return None

    # ── Write ──────────────────────────────────────────────────

    def put(self, key: str, response: str):
        """Insert or replace a cached response. Evicts oldest if full."""
        with self._write_lock:
            self._conn().execute(
                """INSERT OR REPLACE INTO cache (key, response, created_at, hit_count)
                   VALUES (?, ?, ?, 0)""",
                (key, response, time.time()),
            )
            self._conn().commit()

            # Evict oldest if over capacity
            count = self._conn().execute(
                "SELECT COUNT(*) FROM cache"
            ).fetchone()[0]

            if count > self._max_size:
                excess = count - self._max_size
                self._conn().execute(
                    """DELETE FROM cache WHERE key IN (
                         SELECT key FROM cache ORDER BY created_at ASC LIMIT ?
                       )""",
                    (excess,),
                )
                self._conn().commit()

    # ── Admin ──────────────────────────────────────────────────

    def stats(self) -> dict:
        """Cache statistics."""
        count = self._conn().execute(
            "SELECT COUNT(*) FROM cache"
        ).fetchone()[0]
        total_reqs = self._hits + self._misses
        hit_rate = (self._hits / total_reqs * 100) if total_reqs > 0 else 0
        return {
            "entries": count,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
        }

    def clear(self):
        """Wipe all cached responses."""
        with self._write_lock:
            self._conn().execute("DELETE FROM cache")
            self._conn().commit()
        self._hits = 0
        self._misses = 0
        logger.info("ResponseCache: cleared")

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None


# ── Singleton ─────────────────────────────────────────────────
_cache: Optional[ResponseCache] = None
_cache_lock = threading.Lock()


def get_response_cache() -> ResponseCache:
    """Get the global response cache singleton."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = ResponseCache()
    return _cache
