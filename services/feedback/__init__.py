"""
Neuron — RLHF Feedback System
================================
User feedback collection and training data export.

Public API:
    get_feedback_store() → FeedbackStore singleton
    FeedbackEntry       → immutable feedback record
    Rating              → POSITIVE(1) / NEGATIVE(-1)
"""
from __future__ import annotations

from typing import Optional

from services.feedback.types import FeedbackEntry, Rating
from services.feedback.store import FeedbackStore

__all__ = ["FeedbackEntry", "FeedbackStore", "Rating", "get_feedback_store"]

_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    """Get the global feedback store singleton."""
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store
