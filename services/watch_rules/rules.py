"""
Neuron — Watch Rule Models
=============================
Declarative rules for file watcher hooks.

A WatchRule defines: when a file matching [criteria] appears
in [paths], execute [action].

Example:
    WatchRule(
        name="auto_summarize_pdfs",
        patterns=["*.pdf"],
        paths=["C:/Users/rahul/Downloads"],
        action="summarize",
        enabled=True,
    )
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class WatchRule:
    """A declarative file watch rule.
    
    When a file matching `patterns` appears in `paths`,
    execute the `action` with `action_args`.
    """
    name: str
    patterns: List[str]            # Glob patterns: ["*.pdf", "*.docx"]
    paths: List[str]               # Watch directories
    action: str                    # Tool name or "notify"
    action_args: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    rule_id: str = ""

    def __post_init__(self):
        if not self.rule_id:
            import uuid
            self.rule_id = uuid.uuid4().hex[:8]

    def matches(self, filepath: str) -> bool:
        """Check if a file path matches this rule's patterns and paths."""
        from pathlib import Path
        import fnmatch

        fp = Path(filepath)

        # Check if file is in one of the watched paths
        in_path = any(
            str(fp).startswith(str(Path(p)))
            for p in self.paths
        ) if self.paths else True  # Empty paths = match all

        # Check if filename matches any pattern
        matches_pattern = any(
            fnmatch.fnmatch(fp.name, pattern)
            for pattern in self.patterns
        )

        return in_path and matches_pattern

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "patterns": self.patterns,
            "paths": self.paths,
            "action": self.action,
            "action_args": self.action_args,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: Dict) -> "WatchRule":
        return WatchRule(
            name=d["name"],
            patterns=d.get("patterns", []),
            paths=d.get("paths", []),
            action=d.get("action", "notify"),
            action_args=d.get("action_args", {}),
            enabled=d.get("enabled", True),
            created_at=d.get("created_at", time.time()),
            rule_id=d.get("rule_id", ""),
        )
