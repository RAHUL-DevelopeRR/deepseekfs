"""
Neuron — RLHF Feedback Store
==============================
SQLite-backed persistent storage for user feedback.

Design principles:
  - Thread-safe (SQLite WAL mode + serialized access)
  - Independent module (no coupling to UI or LLM engine)
  - Exportable (JSONL format for LoRA fine-tuning)
  - Self-cleaning (auto-eviction at 10K entries)
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict

from app.logger import logger
import app.config as config
from services.feedback.types import FeedbackEntry, Rating


_DB_PATH = config.STORAGE_DIR / "feedback.db"
_MAX_ENTRIES = 10_000
_SCHEMA_VERSION = 1

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS feedback (
    id          TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    query       TEXT NOT NULL,
    response    TEXT NOT NULL,
    mode        TEXT NOT NULL,
    rating      INTEGER NOT NULL,
    intent      TEXT,
    confidence  REAL,
    correction  TEXT,
    model       TEXT DEFAULT 'SmolLM3-3B'
);

CREATE INDEX IF NOT EXISTS idx_feedback_rating
    ON feedback(rating);

CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
    ON feedback(timestamp DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class FeedbackStore:
    """Persistent RLHF feedback store.
    
    Usage:
        store = FeedbackStore()
        store.record(query="hi", response="hello", rating=Rating.POSITIVE, mode="chat")
        stats = store.get_stats()
        store.export_jsonl(Path("training_data.jsonl"))
    
    Thread-safe. Uses WAL mode for concurrent reads.
    """

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        logger.info(f"FeedbackStore: initialized at {db_path}")

    def _init_db(self):
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_CREATE_SQL)
            # Set schema version
            conn.execute(
                "INSERT OR IGNORE INTO schema_version(version) VALUES(?)",
                (_SCHEMA_VERSION,),
            )

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection with optimal settings."""
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    # ── Write Operations ──────────────────────────────────────

    def record(
        self,
        query: str,
        response: str,
        rating: Rating,
        mode: str = "chat",
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        correction: Optional[str] = None,
        model: str = "SmolLM3-3B",
    ) -> FeedbackEntry:
        """Record a user feedback entry.
        
        Args:
            query:      User's original input
            response:   Model's response
            rating:     Rating.POSITIVE or Rating.NEGATIVE
            mode:       Routing mode (chat|query|action)
            intent:     Intent classifier result
            confidence: Intent classifier confidence
            correction: Optional user correction
            model:      Model identifier
            
        Returns:
            The created FeedbackEntry
        """
        entry = FeedbackEntry(
            query=query,
            response=response,
            mode=mode,
            rating=rating,
            intent=intent,
            confidence=confidence,
            correction=correction,
            model=model,
        )

        with self._lock:
            with self._connect() as conn:
                data = entry.to_dict()
                conn.execute(
                    """INSERT OR REPLACE INTO feedback
                       (id, timestamp, query, response, mode, rating,
                        intent, confidence, correction, model)
                       VALUES (:id, :timestamp, :query, :response, :mode,
                               :rating, :intent, :confidence, :correction, :model)""",
                    data,
                )
                # Auto-evict oldest entries if over limit
                count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
                if count > _MAX_ENTRIES:
                    excess = count - _MAX_ENTRIES
                    conn.execute(
                        """DELETE FROM feedback WHERE id IN (
                               SELECT id FROM feedback ORDER BY timestamp ASC LIMIT ?
                           )""",
                        (excess,),
                    )
                    logger.info(f"FeedbackStore: evicted {excess} oldest entries")

        logger.info(
            f"FeedbackStore: recorded {'👍' if rating == Rating.POSITIVE else '👎'} "
            f"for '{query[:40]}' (mode={mode})"
        )
        return entry

    # ── Read Operations ───────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get feedback analytics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            positive = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE rating = 1"
            ).fetchone()[0]
            negative = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE rating = -1"
            ).fetchone()[0]

            # Top 5 negative queries (most common failures)
            top_failures = conn.execute(
                """SELECT query, COUNT(*) as cnt FROM feedback
                   WHERE rating = -1 GROUP BY query ORDER BY cnt DESC LIMIT 5"""
            ).fetchall()

            # Mode breakdown
            mode_stats = conn.execute(
                """SELECT mode, rating, COUNT(*) as cnt FROM feedback
                   GROUP BY mode, rating ORDER BY mode"""
            ).fetchall()

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "positive_rate": round(positive / max(total, 1) * 100, 1),
            "top_failures": [
                {"query": r["query"], "count": r["cnt"]} for r in top_failures
            ],
            "mode_breakdown": [
                {"mode": r["mode"], "rating": r["rating"], "count": r["cnt"]}
                for r in mode_stats
            ],
        }

    def get_negative_queries(self) -> List[str]:
        """Get all queries that received negative feedback.
        
        Used to exclude these from the response cache.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT query FROM feedback WHERE rating = -1"
            ).fetchall()
        return [r["query"] for r in rows]

    def get_entries(
        self,
        rating: Optional[Rating] = None,
        limit: int = 100,
    ) -> List[FeedbackEntry]:
        """Retrieve feedback entries with optional filter."""
        with self._connect() as conn:
            if rating is not None:
                rows = conn.execute(
                    "SELECT * FROM feedback WHERE rating = ? ORDER BY timestamp DESC LIMIT ?",
                    (int(rating), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM feedback ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [FeedbackEntry.from_row(dict(r)) for r in rows]

    # ── Export ────────────────────────────────────────────────

    def export_jsonl(self, output_path: Path, positive_only: bool = False) -> int:
        """Export feedback data as JSONL for fine-tuning.
        
        Format: one JSON object per line, OpenAI chat format.
        
        Args:
            output_path:    Path to write the JSONL file
            positive_only:  If True, only export positive feedback
            
        Returns:
            Number of entries exported
        """
        filter_rating = Rating.POSITIVE if positive_only else None
        entries = self.get_entries(rating=filter_rating, limit=_MAX_ENTRIES)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                pair = entry.to_training_pair()
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                count += 1

        logger.info(f"FeedbackStore: exported {count} entries to {output_path}")
        return count

    def export_intent_corrections(self, output_path: Path) -> int:
        """Export intent corrections for classifier retraining.
        
        Exports entries where the user provided a correction,
        formatted as intent training examples.
        
        Returns:
            Number of corrections exported
        """
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT query, mode, intent, correction FROM feedback
                   WHERE correction IS NOT NULL AND correction != ''
                   ORDER BY timestamp DESC"""
            ).fetchall()

        corrections = []
        for r in rows:
            corrections.append({
                "query": r["query"],
                "original_intent": r["intent"],
                "corrected_mode": r["mode"],
                "correction": r["correction"],
            })

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)

        logger.info(f"FeedbackStore: exported {len(corrections)} corrections to {output_path}")
        return len(corrections)
