"""
Neuron — RLHF Feedback Types
=============================
Immutable data models for the feedback system.
Follows the principle of separation: types define shape, stores define behavior.
"""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class Rating(IntEnum):
    """User feedback rating.
    
    IntEnum so it serializes directly to SQLite INTEGER.
    """
    NEGATIVE = -1
    POSITIVE = 1


@dataclass(frozen=True)
class FeedbackEntry:
    """A single feedback record — immutable after creation.
    
    Attributes:
        id:          Unique identifier (UUID4 hex, first 12 chars)
        timestamp:   Unix epoch seconds
        query:       The user's original input
        response:    The model's response
        mode:        Routing mode (chat|query|action)
        rating:      User's rating (+1 or -1)
        intent:      Intent classifier result
        confidence:  Intent classifier confidence score
        correction:  Optional user-provided correction text
        model:       Model identifier
    """
    query: str
    response: str
    mode: str
    rating: Rating
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    intent: Optional[str] = None
    confidence: Optional[float] = None
    correction: Optional[str] = None
    model: str = "SmolLM3-3B"

    def to_dict(self) -> dict:
        """Serialize to dictionary for SQLite insertion."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "query": self.query,
            "response": self.response,
            "mode": self.mode,
            "rating": int(self.rating),
            "intent": self.intent,
            "confidence": self.confidence,
            "correction": self.correction,
            "model": self.model,
        }

    @classmethod
    def from_row(cls, row: dict) -> FeedbackEntry:
        """Deserialize from SQLite row."""
        return cls(
            id=row["id"],
            timestamp=row["timestamp"],
            query=row["query"],
            response=row["response"],
            mode=row["mode"],
            rating=Rating(row["rating"]),
            intent=row.get("intent"),
            confidence=row.get("confidence"),
            correction=row.get("correction"),
            model=row.get("model", "SmolLM3-3B"),
        )

    def to_training_pair(self) -> dict:
        """Export as a training data pair (OpenAI chat format)."""
        messages = [
            {"role": "user", "content": self.query},
        ]
        # If user provided a correction, use that as the "correct" response
        target = self.correction if self.correction else self.response
        messages.append({"role": "assistant", "content": target})
        return {"messages": messages, "rating": int(self.rating)}
