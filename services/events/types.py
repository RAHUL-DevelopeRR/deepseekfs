"""
Neuron — Event Types & Models
==============================
Pure data models for the structured event system.
No dependencies on storage, UI, or other services.

This module defines the vocabulary of events that flow
through the entire application. Every subsystem speaks
this language.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any


# ─── Event Classification ─────────────────────────────────────

class EventType(str, Enum):
    """What happened."""
    TOOL_CALL       = "tool_call"
    TOOL_RESULT     = "tool_result"
    LLM_INFERENCE   = "llm_inference"
    SEARCH          = "search"
    TASK_CREATED    = "task_created"
    TASK_STEP       = "task_step"
    TASK_COMPLETED  = "task_completed"
    TASK_FAILED     = "task_failed"
    PLAN_GENERATED  = "plan_generated"
    WATCHER_TRIGGER = "watcher_trigger"
    PLUGIN_LOADED   = "plugin_loaded"
    USER_INPUT      = "user_input"
    ERROR           = "error"


class EventStatus(str, Enum):
    """How it ended."""
    STARTED  = "started"
    SUCCESS  = "success"
    FAILED   = "failed"
    BLOCKED  = "blocked"
    DENIED   = "denied"
    RUNNING  = "running"


# ─── Event Model ──────────────────────────────────────────────

@dataclass
class AgentEvent:
    """Immutable record of a single agent event.
    
    Design:
      - Pure data, no behavior
      - Serializable (to_dict)
      - Self-contained (no external refs)
    """
    event_type: str
    status: str = EventStatus.SUCCESS.value
    tool_name: str = ""
    duration_ms: int = 0
    input_summary: str = ""
    output_summary: str = ""
    task_id: str = ""
    metadata: str = ""          # JSON string for extra data
    timestamp: float = field(default_factory=time.time)
    id: Optional[int] = None    # Set by storage layer

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def tool_started(tool_name: str, args_summary: str, task_id: str = "") -> "AgentEvent":
        """Factory: tool call started."""
        return AgentEvent(
            event_type=EventType.TOOL_CALL.value,
            status=EventStatus.STARTED.value,
            tool_name=tool_name,
            input_summary=args_summary[:500],
            task_id=task_id,
        )

    @staticmethod
    def tool_finished(
        tool_name: str, success: bool, output: str,
        duration_ms: int, task_id: str = ""
    ) -> "AgentEvent":
        """Factory: tool call completed."""
        return AgentEvent(
            event_type=EventType.TOOL_RESULT.value,
            status=EventStatus.SUCCESS.value if success else EventStatus.FAILED.value,
            tool_name=tool_name,
            duration_ms=duration_ms,
            output_summary=output[:500],
            task_id=task_id,
        )

    @staticmethod
    def llm_inference(duration_ms: int, tokens: int = 0, task_id: str = "") -> "AgentEvent":
        """Factory: LLM inference completed."""
        return AgentEvent(
            event_type=EventType.LLM_INFERENCE.value,
            duration_ms=duration_ms,
            output_summary=f"{tokens} tokens" if tokens else "",
            task_id=task_id,
        )

    @staticmethod
    def error(message: str, task_id: str = "") -> "AgentEvent":
        """Factory: error occurred."""
        return AgentEvent(
            event_type=EventType.ERROR.value,
            status=EventStatus.FAILED.value,
            output_summary=message[:500],
            task_id=task_id,
        )
