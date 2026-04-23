"""
Neuron — Watch Rules Package
===============================
Declarative file watch rules with hook execution.

Public API:
    from services.watch_rules import WatchRule, WatchHookEngine, get_watch_hooks
"""
from services.watch_rules.rules import WatchRule
from services.watch_rules.hooks import WatchHookEngine, get_watch_hooks

__all__ = ["WatchRule", "WatchHookEngine", "get_watch_hooks"]
