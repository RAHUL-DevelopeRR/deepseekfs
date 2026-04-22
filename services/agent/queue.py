"""
Neuron — Task Queue (SQLite-backed)
=====================================
Persistent task queue with CRUD operations.
Tasks survive application restarts.

Design:
  - SQLite for durability (WAL mode for concurrency)
  - Thread-safe with write lock
  - JSON serialization for task data
  - Supports re-run by creating a copy with new ID
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import List, Optional, Dict

from app.logger import logger
import app.config as config
from services.agent.task import Task, TaskStatus


_DB_PATH = str(config.STORAGE_DIR / "tasks.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    goal         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    mode         TEXT NOT NULL DEFAULT 'auto',
    data_json    TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    completed_at REAL DEFAULT 0,
    priority     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
"""


class TaskQueue:
    """Persistent task queue with full CRUD.
    
    Contract:
      - enqueue(task) -> str           (returns task_id)
      - dequeue() -> Optional[Task]    (next queued task)
      - update(task) -> None           (persist state changes)
      - get(task_id) -> Optional[Task]
      - list_all() -> List[Task]
      - rerun(task_id) -> str          (creates copy, returns new ID)
      - cancel(task_id) -> bool
      - clear_completed() -> int       (returns count removed)
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._conn().executescript(_SCHEMA)
        self._conn().commit()
        logger.info(f"TaskQueue: initialized at {db_path}")

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn = conn
        return conn

    # ── Write operations ──────────────────────────────────────

    def enqueue(self, task: Task) -> str:
        """Add a task to the queue. Returns task_id."""
        with self._write_lock:
            self._conn().execute(
                """INSERT OR REPLACE INTO tasks
                   (task_id, goal, status, mode, data_json, created_at, completed_at, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.task_id,
                    task.goal,
                    task.status,
                    task.mode,
                    json.dumps(task.to_dict()),
                    task.created_at,
                    task.completed_at,
                    0,
                ),
            )
            self._conn().commit()
        logger.info(f"TaskQueue: enqueued [{task.task_id}] '{task.goal[:50]}'")
        return task.task_id

    def update(self, task: Task):
        """Persist current task state."""
        with self._write_lock:
            self._conn().execute(
                """UPDATE tasks SET
                   status = ?, data_json = ?, completed_at = ?
                   WHERE task_id = ?""",
                (
                    task.status,
                    json.dumps(task.to_dict()),
                    task.completed_at,
                    task.task_id,
                ),
            )
            self._conn().commit()

    def cancel(self, task_id: str) -> bool:
        """Cancel a task if it's not terminal."""
        task = self.get(task_id)
        if task and not task.is_terminal:
            task.cancel()
            self.update(task)
            logger.info(f"TaskQueue: cancelled [{task_id}]")
            return True
        return False

    # ── Read operations ───────────────────────────────────────

    def dequeue(self) -> Optional[Task]:
        """Get the next queued task (FIFO). Does NOT remove it."""
        row = self._conn().execute(
            "SELECT data_json FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row:
            return Task.from_dict(json.loads(row["data_json"]))
        return None

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        row = self._conn().execute(
            "SELECT data_json FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row:
            return Task.from_dict(json.loads(row["data_json"]))
        return None

    def list_all(self, limit: int = 50) -> List[Task]:
        """All tasks, newest first."""
        rows = self._conn().execute(
            "SELECT data_json FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [Task.from_dict(json.loads(r["data_json"])) for r in rows]

    def list_by_status(self, status: str, limit: int = 50) -> List[Task]:
        """Tasks filtered by status."""
        rows = self._conn().execute(
            "SELECT data_json FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [Task.from_dict(json.loads(r["data_json"])) for r in rows]

    # ── Compound operations ───────────────────────────────────

    def rerun(self, task_id: str) -> Optional[str]:
        """Create a copy of a task for re-execution. Returns new task_id."""
        original = self.get(task_id)
        if original is None:
            return None

        new_task = Task(goal=original.goal, mode=original.mode)
        self.enqueue(new_task)
        logger.info(f"TaskQueue: re-run [{task_id}] -> [{new_task.task_id}]")
        return new_task.task_id

    def clear_completed(self) -> int:
        """Remove all terminal tasks. Returns count removed."""
        terminal = (
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        )
        with self._write_lock:
            cur = self._conn().execute(
                f"DELETE FROM tasks WHERE status IN ({','.join('?' * len(terminal))})",
                terminal,
            )
            self._conn().commit()
            return cur.rowcount

    def stats(self) -> Dict:
        """Summary statistics."""
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        queued = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'queued'"
        ).fetchone()[0]
        running = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'failed'"
        ).fetchone()[0]
        return {
            "total": total,
            "queued": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
        }

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
