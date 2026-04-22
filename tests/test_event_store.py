"""
Neuron — Event Store Tests
============================
Tests the structured event persistence system.

Covers:
  - Event creation with factory methods
  - SQLite storage insert/query
  - Filtering by type and task
  - Stats calculation
  - Clear operation
"""
import os
import sys
import tempfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.events.types import AgentEvent, EventType, EventStatus
from services.events.store import EventStore


@pytest.fixture
def store():
    """Create a temporary event store for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = EventStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


class TestAgentEvent:
    """Test event model and factory methods."""

    def test_basic_event(self):
        ev = AgentEvent(event_type=EventType.USER_INPUT.value)
        assert ev.event_type == "user_input"
        assert ev.status == "success"
        assert ev.timestamp > 0

    def test_tool_started_factory(self):
        ev = AgentEvent.tool_started("file_read", '{"path": "/foo"}', "task123")
        assert ev.event_type == "tool_call"
        assert ev.status == "started"
        assert ev.tool_name == "file_read"
        assert ev.task_id == "task123"

    def test_tool_finished_factory(self):
        ev = AgentEvent.tool_finished("file_read", True, "contents...", 150, "task123")
        assert ev.event_type == "tool_result"
        assert ev.status == "success"
        assert ev.duration_ms == 150

    def test_tool_failed_factory(self):
        ev = AgentEvent.tool_finished("file_read", False, "not found", 50)
        assert ev.status == "failed"

    def test_llm_inference_factory(self):
        ev = AgentEvent.llm_inference(2500, tokens=150)
        assert ev.event_type == "llm_inference"
        assert ev.duration_ms == 2500

    def test_error_factory(self):
        ev = AgentEvent.error("something broke", "task456")
        assert ev.status == "failed"
        assert "something broke" in ev.output_summary

    def test_to_dict(self):
        ev = AgentEvent(event_type="test")
        d = ev.to_dict()
        assert "event_type" in d
        assert "timestamp" in d
        assert d["event_type"] == "test"


class TestEventStore:
    """Test SQLite event persistence."""

    def test_insert_and_query(self, store):
        ev = AgentEvent(event_type="test_event", status="success")
        row_id = store.insert(ev)
        assert row_id > 0

        events = store.query_recent(10)
        assert len(events) == 1
        assert events[0]["event_type"] == "test_event"

    def test_query_by_task(self, store):
        store.insert(AgentEvent(event_type="a", task_id="task1"))
        store.insert(AgentEvent(event_type="b", task_id="task2"))
        store.insert(AgentEvent(event_type="c", task_id="task1"))

        task1_events = store.query_by_task("task1")
        assert len(task1_events) == 2

    def test_query_by_type(self, store):
        store.insert(AgentEvent(event_type="tool_call"))
        store.insert(AgentEvent(event_type="llm_inference"))
        store.insert(AgentEvent(event_type="tool_call"))

        tool_events = store.query_by_type("tool_call")
        assert len(tool_events) == 2

    def test_stats(self, store):
        store.insert(AgentEvent(event_type="tool_call", status="success"))
        store.insert(AgentEvent(event_type="error", status="failed"))
        store.insert(AgentEvent(event_type="tool_call", status="success", task_id="t1"))

        stats = store.stats()
        assert stats["total_events"] == 3
        assert stats["tool_calls"] == 2
        assert stats["errors"] == 1
        assert stats["tasks"] == 1

    def test_clear(self, store):
        store.insert(AgentEvent(event_type="test"))
        store.insert(AgentEvent(event_type="test"))
        store.clear()
        assert len(store.query_recent(10)) == 0

    def test_truncates_long_summaries(self, store):
        long_text = "x" * 5000
        ev = AgentEvent(event_type="test", input_summary=long_text)
        store.insert(ev)
        events = store.query_recent(1)
        assert len(events[0]["input_summary"]) <= 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
