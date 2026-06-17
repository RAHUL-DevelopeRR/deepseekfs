"""Persistent terminal-session tools for MemoryOS Action mode."""
from __future__ import annotations

from services.powershell_session import get_powershell_session

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult
from .execution_tools import ShellTool


_shell_classifier = ShellTool()


class PowerShellSessionTool(BaseTool):
    name = "powershell_session"
    description = (
        "Run a command inside Neuron's persistent hidden PowerShell session. "
        "Use this for multi-step coding-agent work where cwd/environment should "
        "survive across commands."
    )
    permission = PermissionLevel.MODERATE
    parameters = [
        ToolParam("command", "string", "PowerShell command or script to execute"),
        ToolParam("cwd", "path", "Working directory", required=False, default=""),
        ToolParam("timeout", "integer", "Timeout in seconds", required=False, default=30),
        ToolParam("reset", "boolean", "Restart the PowerShell session before running", required=False, default=False),
    ]

    def _classify_command(self, command: str) -> PermissionLevel:
        return _shell_classifier._classify_command(command)

    def execute(
        self,
        command: str,
        cwd: str = "",
        timeout: int = 30,
        reset: bool = False,
        **kwargs,
    ) -> ToolResult:
        session = get_powershell_session()
        if reset:
            session.reset()
        ok, output = session.run(command=command, cwd=cwd, timeout=timeout)
        pid = session.pid
        prefix = f"[PowerShell pid={pid}] " if pid else "[PowerShell] "
        return ToolResult(ok, prefix + output, {"pid": pid, "persistent": True})
