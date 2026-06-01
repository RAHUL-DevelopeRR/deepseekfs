"""Base types for MemoryOS tools."""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List


class PermissionLevel(enum.Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    success: bool
    output: str
    data: Any = None


@dataclass
class ToolParam:
    """Parameter definition for a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class BaseTool(ABC):
    """Abstract base class for all MemoryOS tools."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def permission(self) -> PermissionLevel: ...

    @property
    @abstractmethod
    def parameters(self) -> List[ToolParam]: ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult: ...

    def to_description_str(self) -> str:
        params = ", ".join(
            f"{param.name}: {param.type}" + (" (optional)" if not param.required else "")
            for param in self.parameters
        )
        return f"- **{self.name}**({params}): {self.description}"
