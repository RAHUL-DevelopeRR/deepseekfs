import shutil

import pytest


def test_powershell_session_tool_registered():
    from services.tools import get_tool

    tool = get_tool("powershell_session")

    assert tool is not None
    assert tool.name == "powershell_session"


def test_executor_selects_persistent_terminal_for_coding_tasks():
    from services.agent.executor import TaskExecutor

    def schema(name):
        return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}

    executor = TaskExecutor(engine=object())
    executor._tool_schemas = [
        schema("file_write"),
        schema("file_edit"),
        schema("file_read"),
        schema("glob"),
        schema("powershell_session"),
        schema("shell"),
    ]

    selected = executor._select_relevant_schemas("create a Java program, save it, compile it, and run it")
    names = {item["function"]["name"] for item in selected}

    assert "powershell_session" in names
    assert "file_write" in names


@pytest.mark.skipif(
    not (shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")),
    reason="PowerShell is not available",
)
def test_powershell_session_runs_command():
    from services.tools.session_tools import PowerShellSessionTool

    result = PowerShellSessionTool().execute(
        command="Write-Output 'neuron-session-ok'",
        timeout=10,
        reset=True,
    )

    assert result.success
    assert "neuron-session-ok" in result.output
