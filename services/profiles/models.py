"""
Neuron — Profile Models
=========================
Pure data model for user profiles.
Each profile is a separate JSON file in storage/profiles/.

Scoring weights are configurable but hidden behind
a username-gated access control.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ScoringWeights:
    """Search scoring weights. Sum should equal 1.0."""
    semantic: float = 0.55
    time: float = 0.20
    size: float = 0.10
    depth: float = 0.10
    access: float = 0.05

    def validate(self) -> bool:
        total = self.semantic + self.time + self.size + self.depth + self.access
        return abs(total - 1.0) < 0.01

    def to_dict(self) -> Dict[str, float]:
        return {
            "semantic": self.semantic,
            "time": self.time,
            "size": self.size,
            "depth": self.depth,
            "access": self.access,
        }

    @staticmethod
    def from_dict(d: Dict) -> "ScoringWeights":
        return ScoringWeights(
            semantic=d.get("semantic", 0.55),
            time=d.get("time", 0.20),
            size=d.get("size", 0.10),
            depth=d.get("depth", 0.10),
            access=d.get("access", 0.05),
        )

    @staticmethod
    def default() -> "ScoringWeights":
        return ScoringWeights()


@dataclass
class LLMSettings:
    """Per-profile LLM configuration."""
    temperature: float = 0.5
    max_tokens_chat: int = 512
    max_tokens_agent: int = 400
    max_agent_turns: int = 6

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_tokens_chat": self.max_tokens_chat,
            "max_tokens_agent": self.max_tokens_agent,
            "max_agent_turns": self.max_agent_turns,
        }

    @staticmethod
    def from_dict(d: Dict) -> "LLMSettings":
        return LLMSettings(
            temperature=d.get("temperature", 0.5),
            max_tokens_chat=d.get("max_tokens_chat", 512),
            max_tokens_agent=d.get("max_tokens_agent", 400),
            max_agent_turns=d.get("max_agent_turns", 6),
        )


@dataclass
class Profile:
    """User profile with all configurable settings.
    
    Stored as: storage/profiles/{name}.json
    """
    name: str
    watch_paths: List[str] = field(default_factory=list)
    excluded_paths: List[str] = field(default_factory=list)
    top_k: int = 20
    theme: str = "auto"
    hotkey: str = "shift+space"
    scoring: ScoringWeights = field(default_factory=ScoringWeights.default)
    llm: LLMSettings = field(default_factory=LLMSettings)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "watch_paths": self.watch_paths,
            "excluded_paths": self.excluded_paths,
            "top_k": self.top_k,
            "theme": self.theme,
            "hotkey": self.hotkey,
            "scoring": self.scoring.to_dict(),
            "llm": self.llm.to_dict(),
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Profile":
        return Profile(
            name=d.get("name", "default"),
            watch_paths=d.get("watch_paths", []),
            excluded_paths=d.get("excluded_paths", []),
            top_k=d.get("top_k", 20),
            theme=d.get("theme", "auto"),
            hotkey=d.get("hotkey", "shift+space"),
            scoring=ScoringWeights.from_dict(d.get("scoring", {})),
            llm=LLMSettings.from_dict(d.get("llm", {})),
            created_at=d.get("created_at", time.time()),
        )

    @staticmethod
    def default() -> "Profile":
        return Profile(name="default")
