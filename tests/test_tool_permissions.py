"""Tests for MemoryOS tool authorization."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.agent.executor import TaskExecutor
from services.agent.task import Task


def test_moderate_tool_requires_confirmation_handler(tmp_path):
    target = tmp_path / "created-by-tool.txt"
    executor = TaskExecutor(engine=None)
    task = Task(goal="create a file")

    result = executor._execute_tool_step(
        task,
        "file_write",
        {"path": str(target), "content": "should not be written"},
    )

    assert result.startswith("[DENIED]")
    assert not target.exists()
    assert task.steps[0].status == "denied"
