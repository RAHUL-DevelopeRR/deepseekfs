"""Shell and code execution tools."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.logger import logger

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult


# ═══════════════════════════════════════════════════════════════
# Command Classification — Hardened (v5.2)
# ═══════════════════════════════════════════════════════════════
#
# Design principles:
#   1. Every comparison is case-insensitive (Windows commands are
#      case-insensitive, PowerShell cmdlets are case-insensitive).
#   2. BLOCKED_BASES are checked as the *first token* only, so
#      "format" blocks "format C:" but not "Format-Table".
#   3. BLOCKED_PATTERNS are substring checks for multi-word phrases
#      that are dangerous regardless of position.
#   4. PowerShell aliases are included because an LLM may emit
#      "ri -Recurse" instead of "Remove-Item -Recurse".
#   5. SAFE_COMMANDS use startswith after lowering; they are the
#      first token (or token + flag) of known read-only commands.

# ── Dangerous base commands (checked as first token) ──────────
# These are dangerous when they appear as the *command* itself.
# We check the first whitespace-delimited token only, which
# prevents false positives like "echo formatting disk" matching
# "format".
BLOCKED_BASES = {
    # Disk / partition destruction
    "format",
    "diskpart",
    # Recursive file deletion — CMD
    "del",          # "del /s" but "del" alone is still risky
    "erase",        # CMD synonym for del
    "rmdir",
    "rd",
    # Recursive file deletion — Unix / PowerShell
    "rm",
    "remove-item",
    "ri",           # PowerShell alias for Remove-Item
    # System control
    "shutdown",
    "restart-computer",
    "stop-computer",
    # Account manipulation
    "net",          # "net user", "net localgroup" — all risky
    # Registry
    "reg",
    # PowerShell aliases for Remove-Item
    "del",          # PowerShell aliases del → Remove-Item
}

# ── Dangerous multi-word patterns (substring check) ───────────
# These catch compound invocations that are dangerous regardless
# of where they appear in a pipeline.
BLOCKED_PATTERNS = [
    "rm -rf",
    "rm -r",
    "remove-item -recurse",
    "ri -recurse",
    "del /s",
    "erase /s",
    "rmdir /s",
    "rd /s",
    "format-volume",
    "clear-disk",
    "initialize-disk",
    "reg delete",
    "net user",
    "net localgroup",
    "stop-process -force",
]

# ── Pre-compile the patterns as lowered strings for fast lookup
_BLOCKED_BASES_LOWER = {b.lower() for b in BLOCKED_BASES}
_BLOCKED_PATTERNS_LOWER = [p.lower() for p in BLOCKED_PATTERNS]

# ── Safe commands (checked as prefix of the full command) ─────
# Read-only operations that can execute without user confirmation.
SAFE_COMMANDS = [
    # CMD / Unix basics
    "dir", "ls", "cd", "pwd", "echo", "type", "cat", "more",
    "where", "which", "whoami", "hostname", "ipconfig", "ifconfig",
    "ping", "nslookup", "tracert",
    # PowerShell read-only cmdlets
    "get-childitem", "get-item", "get-content", "get-location",
    "get-process", "get-service", "test-path", "measure-object",
    "get-date", "get-host", "get-command", "get-alias",
    "select-object", "where-object", "format-table", "format-list",
    "out-string", "sort-object", "group-object",
    # Version checks
    "python --version", "python3 --version",
    "pip --version", "pip3 --version",
    "node --version", "npm --version", "npx --version",
    "cargo --version", "rustc --version",
    "java --version", "javac --version",
    # Git read-only
    "git status", "git log", "git branch", "git diff",
    "git show", "git remote", "git tag",
]

# Pre-compute lowered for fast comparison
_SAFE_COMMANDS_LOWER = [s.lower() for s in SAFE_COMMANDS]

# Maximum output bytes returned to the caller to prevent memory
# exhaustion from commands like "Get-ChildItem -Recurse C:\"
_MAX_OUTPUT_CHARS = 16_000


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
        """Classify a command into SAFE / MODERATE / DANGEROUS.

        Strategy (evaluated in order):
          1. Check multi-word BLOCKED_PATTERNS as substring — catches
             "rm -rf", "del /s" etc. even mid-pipeline.
          2. Extract the first token and check BLOCKED_BASES — catches
             "format C:" without blocking "Format-Table".
          3. Check SAFE_COMMANDS as prefix — catches "git log --oneline".
          4. Default to MODERATE (user confirmation required).
        """
        cmd_lower = command.lower().strip()

        # ── 1. Dangerous substring patterns ──
        for pattern in _BLOCKED_PATTERNS_LOWER:
            if pattern in cmd_lower:
                logger.warning(f"ShellTool: BLOCKED pattern '{pattern}' in: {command[:80]}")
                return PermissionLevel.DANGEROUS

        # ── 2. Dangerous base command (first token) ──
        # Split on whitespace, pipes, semicolons to get the actual command
        # e.g. "echo hello | format C:" → check "echo" AND "format"
        tokens = re.split(r'[|;&]', cmd_lower)
        for segment in tokens:
            first_token = segment.strip().split()[0] if segment.strip() else ""
            if first_token in _BLOCKED_BASES_LOWER:
                logger.warning(f"ShellTool: BLOCKED base '{first_token}' in: {command[:80]}")
                return PermissionLevel.DANGEROUS

        # ── 3. Safe prefix ──
        for safe in _SAFE_COMMANDS_LOWER:
            if cmd_lower.startswith(safe):
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
            output = output.strip()[:_MAX_OUTPUT_CHARS]

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
