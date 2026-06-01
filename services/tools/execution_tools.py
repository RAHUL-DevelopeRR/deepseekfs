"""Shell and code execution tools."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.logger import logger

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult

BLOCKED_COMMANDS = {
    "format",
    "diskpart",
    "del /s",
    "rmdir /s",
    "rd /s",
    "Remove-Item -Recurse -Force",
    "rm -rf",
    "shutdown",
    "net user",
    "reg delete",
}

SAFE_COMMANDS = {
    "dir",
    "ls",
    "cd",
    "pwd",
    "echo",
    "type",
    "cat",
    "more",
    "where",
    "which",
    "whoami",
    "hostname",
    "ipconfig",
    "Get-ChildItem",
    "Get-Item",
    "Get-Content",
    "Get-Location",
    "Get-Process",
    "Get-Service",
    "Test-Path",
    "Measure-Object",
    "python --version",
    "pip --version",
    "node --version",
    "git status",
    "git log",
    "git branch",
    "git diff",
}


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


class ShellTool(BaseTool):
    name = "shell"
    description = "Execute a PowerShell or CMD command. Safe commands execute immediately. Write commands require confirmation. Destructive commands are blocked."
    permission = PermissionLevel.MODERATE
    parameters = [
        ToolParam("command", "string", "Command to execute"),
        ToolParam("cwd", "path", "Working directory", required=False, default=""),
        ToolParam("timeout", "integer", "Timeout in seconds", required=False, default=30),
    ]

    def _classify_command(self, command: str) -> PermissionLevel:
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked.lower() in cmd_lower:
                return PermissionLevel.DANGEROUS
        for safe in SAFE_COMMANDS:
            if cmd_lower.startswith(safe.lower()):
                return PermissionLevel.SAFE
        return PermissionLevel.MODERATE

    def execute(self, command: str, cwd: str = "", timeout: int = 30, **kwargs) -> ToolResult:
        try:
            risk = self._classify_command(command)
            if risk == PermissionLevel.DANGEROUS:
                return ToolResult(
                    False,
                    f"[BLOCKED] '{command}' is classified as DANGEROUS. This command could cause data loss. Execution denied.",
                )

            work_dir = cwd if cwd and os.path.isdir(cwd) else str(Path.home())
            logger.info(f"ShellTool: Executing [{risk.value}]: {command}")

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
                creationflags=_creation_flags(),
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}" if output else result.stderr
            output = output.strip()[:5000]

            if result.returncode == 0:
                return ToolResult(True, output or "(command completed with no output)")
            return ToolResult(False, f"Command exited with code {result.returncode}:\n{output}")
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Command timed out after {timeout}s: {command}")
        except Exception as exc:
            return ToolResult(False, f"Shell error: {exc}")


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "Execute Python code in a subprocess. The code is written to a temp file and run with the system Python interpreter."
    permission = PermissionLevel.MODERATE
    parameters = [
        ToolParam("code", "string", "Python code to execute"),
        ToolParam("timeout", "integer", "Timeout in seconds", required=False, default=60),
    ]

    def execute(self, code: str, timeout: int = 60, **kwargs) -> ToolResult:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as handle:
                handle.write(code)
                temp_path = handle.name

            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path.home()),
                creationflags=_creation_flags(),
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}" if output else result.stderr
            output = output.strip()[:5000]

            if result.returncode == 0:
                return ToolResult(True, output or "(script completed with no output)")
            return ToolResult(False, f"Script exited with code {result.returncode}:\n{output}")
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Script timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(False, f"Python execution error: {exc}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


class GlobTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern (e.g., '*.py', '**/*.pdf')."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("pattern", "string", "Glob pattern to match"),
        ToolParam("path", "path", "Root directory to search in", required=False, default=""),
        ToolParam("max_results", "integer", "Max results", required=False, default=50),
    ]

    def execute(self, pattern: str, path: str = "", max_results: int = 50, **kwargs) -> ToolResult:
        try:
            root = Path(path) if path else Path.home()
            if not root.is_dir():
                return ToolResult(False, f"Directory not found: {path}")

            results = []
            for match in root.glob(pattern):
                if len(results) >= max_results:
                    break
                results.append(str(match))

            if not results:
                return ToolResult(True, f"No files matching '{pattern}' in {root}")

            output = f"Found {len(results)} file(s) matching '{pattern}':\n"
            output += "\n".join(f"  {item}" for item in results)
            return ToolResult(True, output, results)
        except Exception as exc:
            return ToolResult(False, f"Glob error: {exc}")
