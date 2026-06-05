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


def test_executor_parses_json_tool_fallback():
    executor = TaskExecutor(engine=None)
    parsed = executor._extract_json_tool_call(
        '```json\n{"tool": "folder_list", "args": {"path": "."}}\n```'
    )

    assert parsed == ("folder_list", {"path": "."})


def test_tool_selection_avoids_zero_score_write_delete_tools():
    executor = TaskExecutor(engine=None)
    schemas = executor._select_relevant_schemas("read services/llm_engine.py")
    names = {schema["function"]["name"] for schema in schemas}

    assert "file_read" in names
    assert "file_write" not in names
    assert "file_delete" not in names


def test_safe_shell_command_skips_confirmation(monkeypatch):
    import services.agent.executor as executor_mod

    calls = []

    def fake_execute_tool(tool_name, **kwargs):
        calls.append((tool_name, kwargs))
        from services.tools import ToolResult
        return ToolResult(True, "ok")

    monkeypatch.setattr(executor_mod, "execute_tool", fake_execute_tool)
    executor = TaskExecutor(engine=None)
    task = Task(goal="run git status")

    result = executor._execute_tool_step(task, "shell", {"command": "git status"})

    assert result == "[OK] ok"
    assert calls and calls[0][0] == "shell"


def test_dangerous_tool_is_blocked_even_with_confirmation(tmp_path):
    target = tmp_path / "do-not-delete.txt"
    target.write_text("keep", encoding="utf-8")

    executor = TaskExecutor(engine=None)
    executor.on_confirmation = lambda *_: True
    task = Task(goal="delete a file")

    result = executor._execute_tool_step(task, "file_delete", {"path": str(target)})

    assert result.startswith("[BLOCKED]")
    assert target.exists()
    assert task.steps[0].status == "blocked"


def test_repeated_tool_call_does_not_prompt_twice(tmp_path):
    target = tmp_path / "created-once.txt"

    class RepeatingEngine:
        def chat_with_tools(self, **_kwargs):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "file_write",
                            "arguments": (
                                '{"path": "'
                                + str(target).replace("\\", "\\\\")
                                + '", "content": "hello"}'
                            ),
                        }
                    }
                ],
            }

    approvals = []
    executor = TaskExecutor(engine=RepeatingEngine())
    executor.on_confirmation = lambda *_: approvals.append(True) or True
    task = Task(goal="create a file")

    result = executor.run(task)

    assert "repeated file_write" in result
    assert len(approvals) == 1
    assert target.read_text(encoding="utf-8") == "hello"
