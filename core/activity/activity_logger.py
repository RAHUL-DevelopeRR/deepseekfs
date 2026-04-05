"""Activity Logger — SQLite-backed event tracking for Neuron "Memory OS"

Single responsibility: append structured events to a local SQLite log
and query them for "Jump Back In", "Revisit", "Memory Lane", and
"Streak" features.

Thread-safety model:
    Each thread gets its own SQLite connection via threading.local().
    WAL journal mode allows concurrent readers + a single writer without
    blocking.  A 5-second busy_timeout prevents SQLITE_BUSY errors when
    multiple worker threads (search, index, summarize) write
    simultaneously.

Events tracked:
    search      — user performed a semantic search
    open_file   — user opened/accessed a file
    summarize   — user requested AI summary of a file
    tag_apply   — user applied a tag to a file
    tag_remove  — user removed a tag from a file

Schema:
    activity_events(
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    REAL NOT NULL,          -- Unix epoch (float)
        event_type   TEXT NOT NULL,
        query_text   TEXT,
        file_path    TEXT,
        workspace    TEXT,
        metadata     TEXT                    -- JSON string
    )
"""
from __future__ import annotations

import sqlite3
import threading
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

import app.config as config
from app.logger import logger


class _ActivityDB:
    """Thread-safe SQLite wrapper for activity events.

    Uses thread-local connections so each worker (IndexThread,
    SearchThread, SummarizeThread, UI thread) gets its own handle.
    WAL mode + busy_timeout ensure concurrent writes are serialised
    gracefully without SQLITE_BUSY errors.
    """

    _CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS activity_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    REAL NOT NULL,
        event_type   TEXT NOT NULL,
        query_text   TEXT,
        file_path    TEXT,
        workspace    TEXT,
        metadata     TEXT
    );
    """

    _CREATE_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_timestamp ON activity_events(timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_event_type ON activity_events(event_type);",
        "CREATE INDEX IF NOT EXISTS idx_file_path ON activity_events(file_path);",
    ]

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection.

        Each thread maintains its own connection because SQLite's
        default threading mode forbids sharing connections across
        threads.  check_same_thread=False is set as a safety net
        (we never actually share), but the thread-local pattern is
        the real protection.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 5-second busy timeout prevents SQLITE_BUSY when another
            # thread holds the write lock momentarily
            conn.execute("PRAGMA busy_timeout = 5000;")
            self._local.conn = conn
        return conn

    def _init_db(self):
        """Create tables and indexes if they don't exist.

        Uses WAL journal mode for better concurrent read/write
        performance.
        """
        conn = self._conn()
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(self._CREATE_TABLE)
        for idx_sql in self._CREATE_INDEXES:
            conn.execute(idx_sql)
        conn.commit()

    # ── Write ────────────────────────────────────────────────

    def insert_event(
        self,
        event_type: str,
        query_text: Optional[str] = None,
        file_path: Optional[str] = None,
        workspace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Insert a new activity event.

        Catches and logs any DB errors so a logging failure never
        crashes the calling thread (defense-in-depth — the public
        ``log_event`` wrapper also catches).
        """
        try:
            timestamp = time.time()
            metadata_json = json.dumps(metadata) if metadata else None
            self._conn().execute(
                """INSERT INTO activity_events
                   (timestamp, event_type, query_text, file_path, workspace, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp, event_type, query_text, file_path, workspace, metadata_json),
            )
            self._conn().commit()
        except Exception as e:
            logger.warning(f"_ActivityDB.insert_event failed: {e}")

    # ── Read ─────────────────────────────────────────────────

    def get_events_between(
        self,
        start_time: float,
        end_time: float,
        event_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Get events within a time range with optional filters.

        All parameters are bound via ``?`` placeholders to prevent
        SQL injection.
        """
        query = "SELECT * FROM activity_events WHERE timestamp >= ? AND timestamp <= ?"
        params: list = [start_time, end_time]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        query += " ORDER BY timestamp DESC"

        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        rows = self._conn().execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get most recent events, optionally filtered by type."""
        query = "SELECT * FROM activity_events"
        params: list = []

        if event_type:
            query += " WHERE event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn().execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        """Get recently accessed files (deduplicated by path).

        Groups by file_path and returns the most-recently-opened
        files with their last access time and total access count.
        """
        query = """
        SELECT file_path, MAX(timestamp) as last_access, COUNT(*) as access_count
        FROM activity_events
        WHERE file_path IS NOT NULL AND event_type = 'open_file'
        GROUP BY file_path
        ORDER BY last_access DESC
        LIMIT ?
        """
        rows = self._conn().execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_files_matching_query(
        self, query_tokens: List[str], exclude_days: int = 2, limit: int = 5
    ) -> List[Dict]:
        """Get files whose path contains any of the query tokens,
        but that were NOT accessed in the last ``exclude_days`` days.

        This powers the "You might want to revisit…" heuristic:
        surface slightly-older files that share terminology with the
        current search, encouraging the user to reconnect with
        relevant past work.
        """
        if not query_tokens:
            return []

        cutoff_time = time.time() - (exclude_days * 24 * 3600)

        # Build LIKE conditions for each token (parameterised)
        like_conditions = " OR ".join(["file_path LIKE ?" for _ in query_tokens])
        like_params = [f"%{token}%" for token in query_tokens]

        query_sql = f"""
        SELECT file_path, MAX(timestamp) as last_access, COUNT(*) as access_count
        FROM activity_events
        WHERE file_path IS NOT NULL
          AND event_type = 'open_file'
          AND ({like_conditions})
          AND timestamp < ?
        GROUP BY file_path
        ORDER BY last_access DESC
        LIMIT ?
        """

        params = like_params + [cutoff_time, limit]
        rows = self._conn().execute(query_sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_daily_stats(self, date: datetime) -> Dict:
        """Get activity statistics for a specific calendar day.

        Returns total events, distinct files accessed, search count,
        top queries (with counts), and top files (with counts).
        """
        start = datetime(date.year, date.month, date.day, 0, 0, 0).timestamp()
        end = start + 86400  # 24 hours

        # Total events
        total = self._conn().execute(
            "SELECT COUNT(*) FROM activity_events WHERE timestamp >= ? AND timestamp < ?",
            (start, end),
        ).fetchone()[0]

        # Distinct file opens
        files = self._conn().execute(
            """SELECT COUNT(DISTINCT file_path) FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'open_file'""",
            (start, end),
        ).fetchone()[0]

        # Search count
        searches = self._conn().execute(
            """SELECT COUNT(*) FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'search'""",
            (start, end),
        ).fetchone()[0]

        # Top 5 queries
        top_queries = self._conn().execute(
            """SELECT query_text, COUNT(*) as count FROM activity_events
               WHERE timestamp >= ? AND timestamp < ?
                 AND event_type = 'search' AND query_text IS NOT NULL
               GROUP BY query_text
               ORDER BY count DESC
               LIMIT 5""",
            (start, end),
        ).fetchall()

        # Top 10 most accessed files
        top_files = self._conn().execute(
            """SELECT file_path, COUNT(*) as count FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'open_file'
               GROUP BY file_path
               ORDER BY count DESC
               LIMIT 10""",
            (start, end),
        ).fetchall()

        return {
            "total_events": total,
            "files_accessed": files,
            "searches_performed": searches,
            "top_queries": [dict(r) for r in top_queries],
            "top_files": [dict(r) for r in top_files],
        }

    def get_streak_days(self) -> int:
        """Calculate current continuity streak.

        A "streak day" is a calendar day (in local timezone) on
        which the user performed at least one search AND opened at
        least one file.  The streak is the count of such days going
        backwards from today without any gaps.

        Example:
            Today (search+open) = streak 1
            Yesterday (search+open) = streak 2
            Day before (search only, no open) = streak breaks → return 2

        Implementation:
            1. Query the last 90 days, grouping by calendar day.
            2. Walk backwards from today checking consecutive days.
            3. Break on the first day that's missing or incomplete.
        """
        query = """
        SELECT DISTINCT DATE(timestamp, 'unixepoch', 'localtime') as day,
               SUM(CASE WHEN event_type = 'search' THEN 1 ELSE 0 END) as searches,
               SUM(CASE WHEN event_type = 'open_file' THEN 1 ELSE 0 END) as opens
        FROM activity_events
        WHERE timestamp >= ?
        GROUP BY day
        ORDER BY day DESC
        """

        # 90-day lookback is sufficient — streaks longer than that are
        # extremely rare and we avoid scanning the entire table.
        lookback = time.time() - (90 * 24 * 3600)
        rows = self._conn().execute(query, (lookback,)).fetchall()

        if not rows:
            return 0

        streak = 0
        today = datetime.now().date()
        expected_date = today

        for row in rows:
            day_str = row[0]  # "YYYY-MM-DD"
            searches = row[1]
            opens = row[2]

            day_date = datetime.strptime(day_str, "%Y-%m-%d").date()

            # Must be the expected consecutive date (today, then
            # yesterday, then day-before-yesterday, etc.)
            if day_date != expected_date:
                break

            # Both search AND file-open required for a streak day
            if searches > 0 and opens > 0:
                streak += 1
                expected_date = day_date - timedelta(days=1)
            else:
                break

        return streak

    def close(self):
        """Close the thread-local connection (for clean shutdown)."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


# ─────────────────────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────────────────────
_activity_logger: Optional["ActivityLogger"] = None
_lock = threading.Lock()


class ActivityLogger:
    """Main activity logger facade.  Singleton via ``_get_logger()``.

    Every public method catches exceptions internally so that a
    logging failure never crashes the caller (UI thread, search
    thread, etc.).
    """

    def __init__(self):
        db_path = config.STORAGE_DIR / "activity.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = _ActivityDB(str(db_path))
        logger.info(f"ActivityLogger: initialized at {db_path}")

    def log_event(
        self,
        event_type: str,
        query_text: Optional[str] = None,
        file_path: Optional[str] = None,
        workspace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an activity event.  Never raises."""
        try:
            self._db.insert_event(event_type, query_text, file_path, workspace, metadata)
        except Exception as e:
            logger.warning(f"ActivityLogger: failed to log event {event_type}: {e}")

    def get_events_between(
        self,
        start_time: float,
        end_time: float,
        event_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Get events within a time range.  Returns [] on error."""
        try:
            return self._db.get_events_between(start_time, end_time, event_type, file_path, limit)
        except Exception as e:
            logger.warning(f"ActivityLogger: get_events_between failed: {e}")
            return []

    def get_recent_events(
        self, limit: int = 100, event_type: Optional[str] = None
    ) -> List[Dict]:
        """Get most recent events.  Returns [] on error."""
        try:
            return self._db.get_recent_events(limit, event_type)
        except Exception as e:
            logger.warning(f"ActivityLogger: get_recent_events failed: {e}")
            return []

    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        """Get recently accessed files.  Returns [] on error."""
        try:
            return self._db.get_recent_files(limit)
        except Exception as e:
            logger.warning(f"ActivityLogger: get_recent_files failed: {e}")
            return []

    def get_revisit_suggestions(
        self, query_tokens: List[str], exclude_days: int = 2, limit: int = 5
    ) -> List[Dict]:
        """Get files matching query tokens but not accessed recently."""
        try:
            return self._db.get_files_matching_query(query_tokens, exclude_days, limit)
        except Exception as e:
            logger.warning(f"ActivityLogger: get_revisit_suggestions failed: {e}")
            return []

    def get_daily_stats(self, date: datetime) -> Dict:
        """Get activity statistics for a specific day."""
        try:
            return self._db.get_daily_stats(date)
        except Exception as e:
            logger.warning(f"ActivityLogger: get_daily_stats failed: {e}")
            return {
                "total_events": 0, "files_accessed": 0,
                "searches_performed": 0, "top_queries": [], "top_files": [],
            }

    def get_streak_days(self) -> int:
        """Get current continuity streak.  Returns 0 on error."""
        try:
            return self._db.get_streak_days()
        except Exception as e:
            logger.warning(f"ActivityLogger: get_streak_days failed: {e}")
            return 0


def _get_logger() -> ActivityLogger:
    """Get or create the singleton ActivityLogger instance.

    Uses double-checked locking for thread safety without
    acquiring the lock on every call.
    """
    global _activity_logger
    if _activity_logger is None:
        with _lock:
            if _activity_logger is None:
                try:
                    _activity_logger = ActivityLogger()
                except Exception as e:
                    # If the DB can't be opened (permissions, corrupt file),
                    # log the error but do NOT crash the app.
                    logger.error(f"ActivityLogger: FAILED to initialize: {e}")
                    # Create a stub that returns empty data
                    _activity_logger = ActivityLogger.__new__(ActivityLogger)
                    _activity_logger._db = None
    return _activity_logger


# ─────────────────────────────────────────────────────────────
# Public API — module-level convenience functions
# ─────────────────────────────────────────────────────────────
def log_event(
    event_type: str,
    query_text: Optional[str] = None,
    file_path: Optional[str] = None,
    workspace: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Log an activity event.  Never raises."""
    try:
        _get_logger().log_event(event_type, query_text, file_path, workspace, metadata)
    except Exception:
        pass  # absolute last resort — never crash


def get_events_between(
    start_time: float,
    end_time: float,
    event_type: Optional[str] = None,
    file_path: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict]:
    """Get events within a time range."""
    return _get_logger().get_events_between(start_time, end_time, event_type, file_path, limit)


def get_recent_events(limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
    """Get most recent events."""
    return _get_logger().get_recent_events(limit, event_type)


def get_recent_files(limit: int = 10) -> List[Dict]:
    """Get recently accessed files (for 'Jump back in')."""
    return _get_logger().get_recent_files(limit)


def get_revisit_suggestions(
    query_tokens: List[str], exclude_days: int = 2, limit: int = 5
) -> List[Dict]:
    """Get 'you might want to revisit' suggestions.

    Returns files whose paths match query tokens but that haven't
    been accessed in the last ``exclude_days`` days.
    """
    return _get_logger().get_revisit_suggestions(query_tokens, exclude_days, limit)


def get_daily_stats(date: datetime) -> Dict:
    """Get activity statistics for a calendar day."""
    return _get_logger().get_daily_stats(date)


def get_streak_days() -> int:
    """Get current continuity streak (consecutive days with search + file open)."""
    return _get_logger().get_streak_days()
