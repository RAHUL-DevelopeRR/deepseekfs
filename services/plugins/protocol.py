"""
Neuron — Plugin Protocol
==========================
Interface contract for external tools.

Any .py file in storage/plugins/ that exports a class
inheriting from BaseTool will be auto-discovered and
registered in the tool registry.

Plugin file convention:
  storage/plugins/my_tool.py
  → exports class MyTool(BaseTool)
  → auto-registered as tool "my_tool"
"""
from __future__ import annotations

# Re-export the base class for plugin authors
from services.tools import BaseTool, ToolParam, ToolResult, PermissionLevel

__all__ = [
    "BaseTool", "ToolParam", "ToolResult", "PermissionLevel",
]
