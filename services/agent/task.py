"""
Neuron — Task Model
=====================
Pure data model for agent tasks.
No dependencies on services, UI, or storage.

A Task represents a user's goal that the agent works toward.
Tasks have lifecycle states and contain step history.
"""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class TaskStatus(str, Enum):
    """Task lifecycle states."""
    QUEUED      = "queued"
    PLANNING    = "planning"
    RUNNING     = "running"
    WAITING     = "waiting"     # Waiting for user approval
    COMPLETED   = "completed"
    FAILED      = "failed"
    CANCELLED   = "cancelled"


@dataclass
class TaskStep:
    """A single step in a task's execution plan."""
    index: int
    action: str                    # Tool name or "llm_response"
    description: str               # Human-readable description
    args: Dict[str, Any] = field(default_factory=dict)
    status: str = TaskStatus.QUEUED.value
    output: str = ""
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "action": self.action,
            "description": self.description,
            "args": self.args,
            "status": self.status,
            "output": self.output[:500],
            "duration_ms": self.duration_ms,
        }


@dataclass
class Task:
    """A user-defined goal for the agent.
    
    Design:
      - Immutable ID (UUID)
      - Mutable state machine (status transitions)
      - Step history for observability
      - Self-serializable (to_dict / from_dict)
    """
    goal: str                       # Natural language goal
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = TaskStatus.QUEUED.value
    steps: List[TaskStep] = field(default_factory=list)
    plan: List[str] = field(default_factory=list)  # LLM-generated plan
    result: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    mode: str = "auto"              # auto / query / action

    @property
    def elapsed_ms(self) -> int:
        end = self.completed_at or time.time()
        return int((end - self.created_at) * 1000)

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        )

    def add_step(self, action: str, description: str, **args) -> TaskStep:
        """Add a new step to the task."""
        step = TaskStep(
            index=len(self.steps),
            action=action,
            description=description,
            args=args,
        )
        self.steps.append(step)
        return step

    def complete(self, result: str):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED.value
        self.result = result
        self.completed_at = time.time()

    def fail(self, error: str):
        """Mark task as failed."""
        self.status = TaskStatus.FAILED.value
        self.error = error
        self.completed_at = time.time()

    def cancel(self):
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED.value
        self.completed_at = time.time()

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "plan": self.plan,
            "result": self.result[:1000],
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "mode": self.mode,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Task":
        t = Task(
            goal=d["goal"],
            task_id=d.get("task_id", uuid.uuid4().hex[:12]),
            status=d.get("status", TaskStatus.QUEUED.value),
            result=d.get("result", ""),
            error=d.get("error", ""),
            created_at=d.get("created_at", time.time()),
            completed_at=d.get("completed_at", 0.0),
            mode=d.get("mode", "auto"),
        )
        t.plan = d.get("plan", [])
        for sd in d.get("steps", []):
            step = TaskStep(
                index=sd["index"],
                action=sd["action"],
                description=sd["description"],
                args=sd.get("args", {}),
                status=sd.get("status", "queued"),
                output=sd.get("output", ""),
                duration_ms=sd.get("duration_ms", 0),
            )
            t.steps.append(step)
        return t
