"""
Neuron — Events Package
========================
Structured observability for the entire application.

Public API:
    from services.events import EventStore, AgentEvent, EventType, EventStatus
    from services.events import get_event_store
"""
from __future__ import annotations

import threading
from typing import Optional

from services.events.types import AgentEvent, EventType, EventStatus
from services.events.store import EventStore

__all__ = [
    "AgentEvent", "EventType", "EventStatus",
    "EventStore", "get_event_store",
]


# ── Singleton ─────────────────────────────────────────────────
_instance: Optional[EventStore] = None
_lock = threading.Lock()


def get_event_store() -> EventStore:
    """Get or create the global event store singleton."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EventStore()
    return _instance
