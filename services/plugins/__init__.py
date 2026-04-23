"""
Neuron — Plugins Package
===========================
External tool discovery and registration.

Public API:
    from services.plugins import register_plugins, discover_plugins
    from services.plugins.protocol import BaseTool, ToolParam, ToolResult
"""
from services.plugins.loader import discover_plugins, register_plugins

__all__ = ["discover_plugins", "register_plugins"]
