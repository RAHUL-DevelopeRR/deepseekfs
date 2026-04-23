"""
Neuron — Task Queue Tests
============================
Tests the persistent task queue.

Covers:
  - Task creation and serialization
  - Queue CRUD (enqueue, get, list, cancel)
  - Re-run creates a copy
  - Stats calculation
  - Status filtering
"""
import os
import sys
import tempfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.agent.task import Task, TaskStep, TaskStatus
from services.agent.queue import TaskQueue


@pytest.fixture
def queue():
    """Create a temporary task queue for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    q = TaskQueue(db_path=path)
    yield q
    q.close()
    os.unlink(path)


class TestTask:
    """Test Task model."""

    def test_creation(self):
        t = Task(goal="test goal")
        assert t.goal == "test goal"
        assert t.status == "queued"
        assert len(t.task_id) == 12

    def test_add_step(self):
        t = Task(goal="test")
        step = t.add_step("file_read", "Read a file", path="/foo")
        assert step.index == 0
        assert step.action == "file_read"
        assert step.args["path"] == "/foo"

    def test_complete(self):
        t = Task(goal="test")
        t.complete("done!")
        assert t.status == "completed"
        assert t.result == "done!"
        assert t.completed_at > 0
        assert t.is_terminal

    def test_fail(self):
        t = Task(goal="test")
        t.fail("something broke")
        assert t.status == "failed"
        assert t.error == "something broke"
        assert t.is_terminal

    def test_cancel(self):
        t = Task(goal="test")
        t.cancel()
        assert t.status == "cancelled"
        assert t.is_terminal

    def test_serialization(self):
        t = Task(goal="test goal")
        t.add_step("shell", "Run command", command="dir")
        t.complete("result here")

        d = t.to_dict()
        t2 = Task.from_dict(d)
        assert t2.goal == t.goal
        assert t2.task_id == t.task_id
        assert t2.status == "completed"
        assert len(t2.steps) == 1

    def test_elapsed_ms(self):
        t = Task(goal="test")
        assert t.elapsed_ms >= 0  # Can be 0 if test runs in < 1ms


class TestTaskQueue:
    """Test persistent task queue."""

    def test_enqueue_and_get(self, queue):
        t = Task(goal="find files")
        queue.enqueue(t)
        loaded = queue.get(t.task_id)
        assert loaded is not None
        assert loaded.goal == "find files"

    def test_dequeue_fifo(self, queue):
        t1 = Task(goal="first")
        t2 = Task(goal="second")
        queue.enqueue(t1)
        queue.enqueue(t2)

        next_task = queue.dequeue()
        assert next_task.goal == "first"

    def test_update(self, queue):
        t = Task(goal="update test")
        queue.enqueue(t)
        t.complete("done")
        queue.update(t)

        loaded = queue.get(t.task_id)
        assert loaded.status == "completed"

    def test_cancel(self, queue):
        t = Task(goal="cancel me")
        queue.enqueue(t)
        assert queue.cancel(t.task_id)

        loaded = queue.get(t.task_id)
        assert loaded.status == "cancelled"

    def test_cannot_cancel_completed(self, queue):
        t = Task(goal="done")
        t.complete("result")
        queue.enqueue(t)
        assert not queue.cancel(t.task_id)

    def test_list_all(self, queue):
        queue.enqueue(Task(goal="a"))
        queue.enqueue(Task(goal="b"))
        queue.enqueue(Task(goal="c"))
        assert len(queue.list_all()) == 3

    def test_rerun(self, queue):
        t = Task(goal="rerun me")
        t.complete("original result")
        queue.enqueue(t)

        new_id = queue.rerun(t.task_id)
        assert new_id is not None
        assert new_id != t.task_id

        new_task = queue.get(new_id)
        assert new_task.goal == "rerun me"
        assert new_task.status == "queued"

    def test_clear_completed(self, queue):
        t1 = Task(goal="completed")
        t1.complete("done")
        t2 = Task(goal="still queued")

        queue.enqueue(t1)
        queue.enqueue(t2)

        removed = queue.clear_completed()
        assert removed == 1
        assert len(queue.list_all()) == 1

    def test_stats(self, queue):
        t1 = Task(goal="q"); queue.enqueue(t1)
        t2 = Task(goal="c"); t2.complete("done"); queue.enqueue(t2)
        t3 = Task(goal="f"); t3.fail("err"); queue.enqueue(t3)

        stats = queue.stats()
        assert stats["queued"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
