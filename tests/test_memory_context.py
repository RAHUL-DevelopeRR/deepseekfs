from services.memory_context import MemoryContextStore
from pathlib import Path


def test_memory_context_persists_recent_messages(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryContextStore(str(db_path))
    store.append("user", "Give me a Java HashMap example", "chat")
    store.append("assistant", "```java\nclass HashMapExample {}\n```", "chat")

    reopened = MemoryContextStore(str(db_path))
    recent = reopened.recent_messages(limit=5)

    assert recent[0]["role"] == "user"
    assert "HashMap" in recent[0]["content"]
    assert "HashMapExample" in reopened.format_recent_context()


def test_action_mode_includes_persistent_context(tmp_path):
    from services.memory_os import MemoryOSAgent

    captured = {}

    class FakeExecutor:
        on_step = None
        on_thinking = None
        on_confirmation = None

        def run(self, task):
            captured["goal"] = task.goal
            return "done"

    agent = MemoryOSAgent()
    agent._memory = MemoryContextStore(str(tmp_path / "memory.db"))
    agent._conversation = []
    agent._executor = FakeExecutor()
    agent._remember("assistant", "```java\npublic class HashMapExample {}\n```", "chat")

    result = agent._action_mode("review the previous program")

    assert result == "done"
    assert "HashMapExample" in captured["goal"]
    assert "Latest user request:\nreview the previous program" in captured["goal"]


def test_action_mode_saves_and_runs_latest_code_block(tmp_path, monkeypatch):
    from services.memory_os import MemoryOSAgent

    calls = []

    class FakeExecutor:
        on_step = None
        on_thinking = None
        on_confirmation = None

        def _execute_tool_step(self, task, tool_name, args):
            calls.append((tool_name, args))
            return f"[OK] {tool_name}"

        def run(self, task):
            raise AssertionError("deterministic follow-up should bypass model loop")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    agent = MemoryOSAgent()
    agent._memory = MemoryContextStore(str(tmp_path / "memory.db"))
    agent._conversation = []
    agent._executor = FakeExecutor()
    agent._remember(
        "assistant",
        "```java\npublic class HashMapExample { public static void main(String[] args) { System.out.println(\"hi\"); } }\n```",
        "chat",
    )

    result = agent._action_mode("save it and run it")

    assert "NeuronWorkspace" in result
    assert calls[0][0] == "file_write"
    assert calls[0][1]["path"].endswith("HashMapExample.java")
    assert calls[1][0] == "powershell_session"
    assert "javac" in calls[1][1]["command"]


def test_action_mode_generates_and_saves_new_code_artifact(tmp_path, monkeypatch):
    from services.memory_os import MemoryOSAgent

    calls = []

    class FakeEngine:
        def chat(self, **kwargs):
            return (
                "```java\n"
                "public class HospitalManagementSystem {\n"
                "  public static void main(String[] args) { System.out.println(\"ok\"); }\n"
                "}\n"
                "```"
            )

    class FakeExecutor:
        on_step = None
        on_thinking = None
        on_confirmation = None

        def _execute_tool_step(self, task, tool_name, args):
            calls.append((tool_name, args))
            return f"[OK] {tool_name}"

        def run(self, task):
            raise AssertionError("coding action should bypass generic model tool loop")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    agent = MemoryOSAgent()
    agent._memory = MemoryContextStore(str(tmp_path / "memory.db"))
    agent._conversation = []
    agent._engine = FakeEngine()
    agent._executor = FakeExecutor()

    result = agent._action_mode("create a Java program for a hospital management system and save it")

    assert "HospitalManagementSystem.java" in result
    assert calls[0][0] == "file_write"
    assert calls[0][1]["path"].endswith("HospitalManagementSystem.java")
    assert "HospitalManagementSystem" in calls[0][1]["content"]
    assert all(call[0] != "powershell_session" for call in calls)


def test_code_generation_does_not_use_jdbc_template(tmp_path):
    from services.memory_os import MemoryOSAgent

    calls = []

    class FakeEngine:
        def chat(self, **kwargs):
            calls.append(kwargs)
            return (
                "```java\n"
                "public class CustomJdbcFromModel {\n"
                "  public static void main(String[] args) { System.out.println(\"model\"); }\n"
                "}\n"
                "```"
            )

    agent = MemoryOSAgent()
    agent._memory = MemoryContextStore(str(tmp_path / "memory.db"))
    agent._conversation = []
    agent._engine = FakeEngine()

    artifact = agent._generate_code_artifact("create a Java JDBC program")

    assert calls, "Qwen/model path should be used instead of a deterministic JDBC template"
    assert artifact is not None
    assert artifact[1].startswith("public class CustomJdbcFromModel")


def test_action_mode_rewrites_previous_code_before_saving(tmp_path, monkeypatch):
    from services.memory_os import MemoryOSAgent

    calls = []

    class FakeEngine:
        def chat(self, **kwargs):
            return (
                "```java\n"
                "public class HashMapExample {\n"
                "  public static void main(String[] args) { System.out.println(\"bye\"); }\n"
                "}\n"
                "```"
            )

    class FakeExecutor:
        on_step = None
        on_thinking = None
        on_confirmation = None

        def _execute_tool_step(self, task, tool_name, args):
            calls.append((tool_name, args))
            return f"[OK] {tool_name}"

        def run(self, task):
            raise AssertionError("rewrite follow-up should bypass generic model tool loop")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    agent = MemoryOSAgent()
    agent._memory = MemoryContextStore(str(tmp_path / "memory.db"))
    agent._conversation = []
    agent._engine = FakeEngine()
    agent._executor = FakeExecutor()
    agent._remember(
        "assistant",
        "```java\npublic class HashMapExample { public static void main(String[] args) { System.out.println(\"hi\"); } }\n```",
        "chat",
    )

    result = agent._action_mode("alter the program to print bye and run it")

    assert "HashMapExample.java" in result
    assert calls[0][0] == "file_write"
    assert "bye" in calls[0][1]["content"]
    assert calls[1][0] == "powershell_session"
