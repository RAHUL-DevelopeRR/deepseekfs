"""Activity Logger — SQLite-backed event tracking for Neuron "Memory OS"

Single responsibility: append structured events to a local SQLite log and query them.

Events tracked:
- search: user performed a semantic search
- open_file: user opened/accessed a file
- summarize: user requested AI summary of a file
- tag_apply: user applied a tag to a file
- tag_remove: user removed a tag from a file

Schema:
- id: auto-increment primary key
- timestamp: Unix epoch time (float)
- event_type: string (search, open_file, summarize, etc.)
- query_text: search query (if applicable)
- file_path: file path (if applicable)
- workspace: workspace/folder context (if available)
- metadata: JSON string for additional context
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
    """Thread-safe SQLite wrapper for activity events."""

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
        """Get or create thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._conn()
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(self._CREATE_TABLE)
        for idx_sql in self._CREATE_INDEXES:
            conn.execute(idx_sql)
        conn.commit()

    def insert_event(
        self,
        event_type: str,
        query_text: Optional[str] = None,
        file_path: Optional[str] = None,
        workspace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Insert a new activity event."""
        timestamp = time.time()
        metadata_json = json.dumps(metadata) if metadata else None

        self._conn().execute(
            """INSERT INTO activity_events (timestamp, event_type, query_text, file_path, workspace, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (timestamp, event_type, query_text, file_path, workspace, metadata_json),
        )
        self._conn().commit()

    def get_events_between(
        self,
        start_time: float,
        end_time: float,
        event_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Get events within a time range with optional filters."""
        query = "SELECT * FROM activity_events WHERE timestamp >= ? AND timestamp <= ?"
        params = [start_time, end_time]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        rows = self._conn().execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get most recent events."""
        query = "SELECT * FROM activity_events"
        params = []

        if event_type:
            query += " WHERE event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn().execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        """Get recently accessed files (deduplicated by path)."""
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
        """Get files that match query tokens but weren't accessed recently."""
        cutoff_time = time.time() - (exclude_days * 24 * 3600)

        # Build LIKE conditions for each token
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
        """Get activity statistics for a specific day."""
        start = datetime(date.year, date.month, date.day, 0, 0, 0).timestamp()
        end = start + 86400  # 24 hours

        # Total events
        total = self._conn().execute(
            "SELECT COUNT(*) FROM activity_events WHERE timestamp >= ? AND timestamp < ?",
            (start, end),
        ).fetchone()[0]

        # File opens
        files = self._conn().execute(
            """SELECT COUNT(DISTINCT file_path) FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'open_file'""",
            (start, end),
        ).fetchone()[0]

        # Searches
        searches = self._conn().execute(
            """SELECT COUNT(*) FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'search'""",
            (start, end),
        ).fetchone()[0]

        # Top queries
        top_queries = self._conn().execute(
            """SELECT query_text, COUNT(*) as count FROM activity_events
               WHERE timestamp >= ? AND timestamp < ? AND event_type = 'search' AND query_text IS NOT NULL
               GROUP BY query_text
               ORDER BY count DESC
               LIMIT 5""",
            (start, end),
        ).fetchall()

        # Most accessed files
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
        """Calculate current continuity streak (days with at least 1 search + 1 file open)."""
        # Get distinct days (in local timezone) going backwards from today
        query = """
        SELECT DISTINCT DATE(timestamp, 'unixepoch', 'localtime') as day,
               SUM(CASE WHEN event_type = 'search' THEN 1 ELSE 0 END) as searches,
               SUM(CASE WHEN event_type = 'open_file' THEN 1 ELSE 0 END) as opens
        FROM activity_events
        WHERE timestamp >= ?
        GROUP BY day
        ORDER BY day DESC
        """

        # Look back 90 days max
        lookback = time.time() - (90 * 24 * 3600)
        rows = self._conn().execute(query, (lookback,)).fetchall()

        if not rows:
            return 0

        # Count consecutive days with both search and open
        streak = 0
        today = datetime.now().date()
        expected_date = today

        for row in rows:
            day_str = row[0]  # "YYYY-MM-DD"
            searches = row[1]
            opens = row[2]

            day_date = datetime.strptime(day_str, "%Y-%m-%d").date()

            # Must match expected consecutive date
            if day_date != expected_date:
                break

            # Must have both search and file open
            if searches > 0 and opens > 0:
                streak += 1
                expected_date = day_date - timedelta(days=1)
            else:
                break

        return streak


# ─────────────────────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────────────────────
_activity_logger: Optional[ActivityLogger] = None
_lock = threading.Lock()


class ActivityLogger:
    """Main activity logger facade. Singleton pattern."""

    def __init__(self):
        db_path = config.STORAGE_DIR / "activity.db"
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
        """Log an activity event."""
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
        """Get events within a time range."""
        return self._db.get_events_between(start_time, end_time, event_type, file_path, limit)

    def get_recent_events(
        self, limit: int = 100, event_type: Optional[str] = None
    ) -> List[Dict]:
        """Get most recent events."""
        return self._db.get_recent_events(limit, event_type)

    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        """Get recently accessed files."""
        return self._db.get_recent_files(limit)

    def get_revisit_suggestions(
        self, query_tokens: List[str], exclude_days: int = 2, limit: int = 5
    ) -> List[Dict]:
        """Get files matching query tokens but not accessed recently."""
        return self._db.get_files_matching_query(query_tokens, exclude_days, limit)

    def get_daily_stats(self, date: datetime) -> Dict:
        """Get activity statistics for a specific day."""
        return self._db.get_daily_stats(date)

    def get_streak_days(self) -> int:
        """Get current continuity streak."""
        return self._db.get_streak_days()


def _get_logger() -> ActivityLogger:
    """Get or create singleton ActivityLogger instance."""
    global _activity_logger
    if _activity_logger is None:
        with _lock:
            if _activity_logger is None:
                _activity_logger = ActivityLogger()
    return _activity_logger


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def log_event(
    event_type: str,
    query_text: Optional[str] = None,
    file_path: Optional[str] = None,
    workspace: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Log an activity event (module-level convenience function)."""
    _get_logger().log_event(event_type, query_text, file_path, workspace, metadata)


def get_events_between(
    start_time: float,
    end_time: float,
    event_type: Optional[str] = None,
    file_path: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict]:
    """Get events within a time range (module-level convenience function)."""
    return _get_logger().get_events_between(start_time, end_time, event_type, file_path, limit)


def get_recent_events(limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
    """Get most recent events (module-level convenience function)."""
    return _get_logger().get_recent_events(limit, event_type)


def get_recent_files(limit: int = 10) -> List[Dict]:
    """Get recently accessed files (module-level convenience function)."""
    return _get_logger().get_recent_files(limit)


def get_revisit_suggestions(
    query_tokens: List[str], exclude_days: int = 2, limit: int = 5
) -> List[Dict]:
    """Get 'you might want to revisit' suggestions."""
    return _get_logger().get_revisit_suggestions(query_tokens, exclude_days, limit)


def get_daily_stats(date: datetime) -> Dict:
    """Get activity statistics for a day."""
    return _get_logger().get_daily_stats(date)


def get_streak_days() -> int:
    """Get current continuity streak."""
    return _get_logger().get_streak_days()
