"""Claw-code tool-surface integration helpers."""
from __future__ import annotations

import json
from pathlib import Path

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult


CLAW_BACKUP_ROOT = Path.home() / "Downloads" / "claw-code-backup"
CLAW_TOOL_SNAPSHOT = CLAW_BACKUP_ROOT / "src" / "reference_data" / "tools_snapshot.json"


class ClawToolIndexTool(BaseTool):
    name = "claw_tool_index"
    description = (
        "Inspect the mirrored claw-code tool definitions and show which Neuron "
        "local tools map to that coding-agent surface."
    )
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("query", "string", "Tool name or capability to search for", required=False, default=""),
        ToolParam("limit", "integer", "Maximum entries to return", required=False, default=12),
    ]

    _NEURON_MAP = {
        "BashTool": "shell",
        "PowerShellTool": "powershell_session",
        "FileReadTool": "file_read",
        "FileWriteTool": "file_write",
        "FileEditTool": "file_edit",
        "GlobTool": "glob",
        "GrepTool": "shell / Select-String",
        "TodoWriteTool": "task/event log",
        "TaskCreateTool": "MemoryOS task queue",
    }

    def execute(self, query: str = "", limit: int = 12, **kwargs) -> ToolResult:
        if not CLAW_TOOL_SNAPSHOT.exists():
            return ToolResult(False, f"Claw tool snapshot not found: {CLAW_TOOL_SNAPSHOT}")

        try:
            entries = json.loads(CLAW_TOOL_SNAPSHOT.read_text(encoding="utf-8"))
            needle = (query or "").lower().strip()
            matches = []
            for entry in entries:
                name = str(entry.get("name", ""))
                source = str(entry.get("source_hint", ""))
                responsibility = str(entry.get("responsibility", ""))
                haystack = f"{name} {source} {responsibility}".lower()
                if needle and needle not in haystack:
                    continue
                mapped = self._NEURON_MAP.get(name, "")
                suffix = f" -> Neuron: {mapped}" if mapped else ""
                matches.append(f"- {name}{suffix}\n  source: {source}")
                if len(matches) >= max(1, min(int(limit or 12), 40)):
                    break

            if not matches:
                return ToolResult(True, f"No claw-code tool definitions matched '{query}'.")

            return ToolResult(
                True,
                "Claw-code tool definitions mapped into Neuron Action mode:\n"
                + "\n".join(matches),
                {"snapshot": str(CLAW_TOOL_SNAPSHOT), "count": len(matches)},
            )
        except Exception as exc:
            return ToolResult(False, f"Could not read claw tool snapshot: {exc}")
