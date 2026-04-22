"""
Neuron — Agent Package
========================
The intelligent agent harness for Neuron.

Public API:
    from services.agent import Task, TaskQueue, TaskExecutor
    from services.agent import get_task_queue
"""
from __future__ import annotations

import threading
from typing import Optional

from services.agent.task import Task, TaskStep, TaskStatus
from services.agent.queue import TaskQueue
from services.agent.executor import TaskExecutor

__all__ = [
    "Task", "TaskStep", "TaskStatus",
    "TaskQueue", "TaskExecutor",
    "get_task_queue",
]


# ── Singleton ─────────────────────────────────────────────────
_queue: Optional[TaskQueue] = None
_lock = threading.Lock()


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue singleton."""
    global _queue
    if _queue is None:
        with _lock:
            if _queue is None:
                _queue = TaskQueue()
    return _queue
