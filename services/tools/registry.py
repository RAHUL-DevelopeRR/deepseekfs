"""Tool registry and schema generation."""
from __future__ import annotations

from typing import Dict, List, Optional

from .base import BaseTool, ToolResult
from .claw_tools import ClawToolIndexTool
from .execution_tools import GlobTool, PythonExecTool, ShellTool
from .file_tools import FileDeleteTool, FileEditTool, FileReadTool, FileWriteTool
from .folder_tools import FolderCreateTool, FolderListTool, FolderOrganizeTool, FolderSearchTool
from .search_tools import OCRTool, SemanticSearchTool, SummarizeTool
from .session_tools import PowerShellSessionTool
from .system_tools import SystemProfileTool

ALL_TOOLS: Dict[str, BaseTool] = {}

_TYPE_MAP = {
    "string": "string",
    "path": "string",
    "integer": "integer",
    "boolean": "boolean",
}


def _register_tools() -> None:
    tool_classes = [
        FileReadTool,
        FileWriteTool,
        FileEditTool,
        FileDeleteTool,
        FolderCreateTool,
        FolderListTool,
        FolderSearchTool,
        FolderOrganizeTool,
        SemanticSearchTool,
        SummarizeTool,
        OCRTool,
        SystemProfileTool,
        ClawToolIndexTool,
        PowerShellSessionTool,
        ShellTool,
        PythonExecTool,
        GlobTool,
    ]
    for tool_class in tool_classes:
        tool = tool_class()
        ALL_TOOLS[tool.name] = tool


_register_tools()


def get_tool(name: str) -> Optional[BaseTool]:
    return ALL_TOOLS.get(name)


def get_all_tools() -> Dict[str, BaseTool]:
    return ALL_TOOLS.copy()


def get_tool_descriptions() -> str:
    return "\n".join(tool.to_description_str() for tool in ALL_TOOLS.values())


def execute_tool(name: str, **kwargs) -> ToolResult:
    tool = get_tool(name)
    if tool is None:
        return ToolResult(False, f"Unknown tool: {name}")
    try:
        return tool.execute(**kwargs)
    except Exception as exc:
        return ToolResult(False, f"Tool '{name}' execution error: {exc}")


def get_tool_schemas() -> List[Dict]:
    schemas = []
    for tool in ALL_TOOLS.values():
        properties = {}
        required = []
        for param in tool.parameters:
            properties[param.name] = {
                "type": _TYPE_MAP.get(param.type, "string"),
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return schemas
