"""
Neuron — Profiles Package
============================
User profile management with configurable scoring weights.

Public API:
    from services.profiles import ProfileManager, Profile, ScoringWeights
    from services.profiles import get_profile_manager
"""
from __future__ import annotations

import threading
from typing import Optional

from services.profiles.models import Profile, ScoringWeights, LLMSettings
from services.profiles.manager import ProfileManager

__all__ = [
    "Profile", "ScoringWeights", "LLMSettings",
    "ProfileManager", "get_profile_manager",
]

_instance: Optional[ProfileManager] = None
_lock = threading.Lock()


def get_profile_manager() -> ProfileManager:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ProfileManager()
    return _instance
