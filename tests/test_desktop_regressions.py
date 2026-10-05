import ctypes
import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_hotkey_rearms_when_trigger_released_while_modifier_held(monkeypatch):
    from ui import hotkeys
    down = {hotkeys.VK_CTRL}
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(
        GetAsyncKeyState=lambda key: 0x8000 if key in down else 0)), raising=False)
    fired = []
    listener = hotkeys._WindowsHotkeyFilter(hotkeys.PANEL_FALLBACK, lambda: fired.append(True))
    monkeypatch.setattr(listener, "_schedule_rearm", lambda: None)
    message = hotkeys._MSG(message=hotkeys.WM_HOTKEY, wParam=hotkeys.PANEL_FALLBACK.hotkey_id)
    down.add(hotkeys.VK_SPACE)
    listener.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
    down.remove(hotkeys.VK_SPACE)
    listener._maybe_rearm()
    listener._last_fire -= 1
    down.add(hotkeys.VK_SPACE)
    listener.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
    assert len(fired) == 2


def test_instance_lock_activation_and_release(tmp_path):
    from PyQt6.QtCore import QCoreApplication
    from services.desktop_instance import DesktopInstance
    app = QCoreApplication.instance()
    if app is None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
    owner, second = DesktopInstance(tmp_path), DesktopInstance(tmp_path)
    activations = []
    owner.activated.connect(lambda: activations.append(True))
    try:
        assert owner.acquire()
        assert not second.acquire()
        from PyQt6.QtTest import QTest
        QTest.qWait(150)
        assert activations == [True]
        owner.close()
        assert second.acquire()
    finally:
        second.close()
        owner.close()


def test_chat_passes_previous_modes_and_full_current_request(tmp_path, monkeypatch):
    from services import memory_os
    from services.memory_context import MemoryContextStore
    monkeypatch.setattr(memory_os, "get_memory_context_store", lambda: MemoryContextStore(str(tmp_path / "chat.db")))
    monkeypatch.setattr(memory_os, "_live_context_for_prompt", lambda text: ("", 0, False))
    monkeypatch.delenv("NEURON_CHAT_HISTORY_LIMIT", raising=False)
    monkeypatch.delenv("NEURON_CHAT_HISTORY_CHARS", raising=False)
    captured = []
    agent = memory_os.MemoryOSAgent()
    agent._engine = SimpleNamespace(chat=lambda **kw: captured.append(kw["messages"]) or "answer")
    agent._remember("user", "My project is called Atlas", "chat")
    agent._remember("assistant", "Atlas has a launch checklist", "query")
    request = "What is my project? " + "detail " * 200
    agent.chat(request, "chat")
    assert any("Atlas" in m["content"] for m in captured[0])
    assert captured[0][-1]["content"] == request
    reopened = memory_os.MemoryOSAgent()
    assert any("Atlas" in m["content"] for m in reopened._conversation)


def test_context_budget_keeps_newest_messages(tmp_path):
    from services.memory_context import MemoryContextStore
    store = MemoryContextStore(str(tmp_path / "context.db"))
    for number in range(12):
        store.append("user", f"Turn {number}: " + "x" * 80)
    context = store.format_recent_context(limit=12, max_chars=250)
    assert "Turn 11" in context
    assert "Turn 0:" not in context


def test_tool_protocol_exposes_schemas_and_observations():
    from services.tool_protocol import tool_messages, tool_response
    schema = {"type": "function", "function": {"name": "folder_list", "parameters": {"type": "object"}}}
    response = tool_response('<tool_call>{"name":"folder_list","arguments":{"path":"C:/test"}}</tool_call>', [schema])
    messages = tool_messages([{"role": "system", "content": "Do the task"},
        {"role": "assistant", **response}, {"role": "tool", "content": "found notes.txt"}], [schema])
    assert '"name": "folder_list"' in messages[0]["content"]
    assert '<tool_response>\nfound notes.txt' in messages[-1]["content"]
    assert "tool_calls" not in messages[1]
    assert response["tool_calls"]  # Input not mutated.


def test_action_failure_does_not_fall_back_to_chat(monkeypatch):
    from services.agent import executor as module
    from services.agent.task import Task
    class Engine:
        def chat_with_tools(self, **kwargs):
            raise ValueError("schema failure")
        def chat(self, **kwargs):
            raise AssertionError("must not claim success through plain chat")
    task = Task("list a folder")
    result = module.TaskExecutor(Engine()).run(task)
    assert task.status == "failed"
    assert "schema failure" in result


def test_action_executes_all_tool_calls_and_feeds_results(monkeypatch, tmp_path):
    from services.agent import executor as module
    from services.agent.task import Task
    class Engine:
        def chat_with_tools(self, messages, **kwargs):
            if len(messages) == 2:
                return {"content": "", "tool_calls": [{"id": str(i), "function": {
                    "name": "folder_list", "arguments": json.dumps({"path": str(tmp_path / str(i))})}} for i in range(2)]}
            assert len([m for m in messages if m["role"] == "tool"]) == 2
            return {"content": "Two folders listed"}
    agent = module.TaskExecutor(Engine())
    calls = []
    monkeypatch.setattr(agent, "_execute_tool_step", lambda task, name, args: calls.append(args) or "[OK] empty")
    assert agent._execute_loop(Task("list folders")) == "Two folders listed"
    assert len(calls) == 2


def test_denied_code_write_never_runs_or_claims_saved(tmp_path, monkeypatch):
    from pathlib import Path
    from services.memory_os import MemoryOSAgent
    from services.agent.task import Task
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    agent = MemoryOSAgent()
    calls = []
    executor = SimpleNamespace(_execute_tool_step=lambda task, name, args: calls.append(name) or "[DENIED] User declined")
    task = Task("save and run")
    result = agent._save_and_optionally_run_code("python", "print('hello')", "save and run it", task, executor)
    assert task.status == "failed"
    assert calls == ["file_write"]
    assert "not saved" in result


def test_context_does_not_select_tools_for_old_actions():
    from services.agent.executor import TaskExecutor
    agent = TaskExecutor(object())
    names = {s["function"]["name"] for s in agent._select_relevant_schemas(
        "Prior context: delete folders and execute scripts\nLatest user request:\nread notes.txt")}
    assert "file_read" in names
    assert "file_delete" not in names
    assert "python_exec" not in names
