"""
Neuron — Watch Hooks
======================
Evaluates watch rules against file events and executes actions.

Integrates with the existing FileWatcher by providing a callback
that the watcher calls on file create/modify events.

Design:
  - Rules are loaded from storage/watch_rules.json
  - Hooks are evaluated synchronously (lightweight)
  - Tool execution happens in a separate thread (non-blocking)
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import List, Optional, Callable

from app.logger import logger
import app.config as config
from services.watch_rules.rules import WatchRule
from services.events import get_event_store, AgentEvent, EventType


_RULES_FILE = config.STORAGE_DIR / "watch_rules.json"


class WatchHookEngine:
    """Evaluates watch rules against file events.
    
    Contract:
      - load_rules() / save_rules()
      - add_rule(rule) / remove_rule(rule_id)
      - evaluate(filepath, event_type)  ← called by FileWatcher
    """

    def __init__(self):
        self._rules: List[WatchRule] = []
        self._lock = threading.Lock()
        self.on_action: Optional[Callable] = None  # Notify UI
        self.load_rules()

    # ── Rule CRUD ─────────────────────────────────────────────

    def load_rules(self):
        """Load rules from persistent storage."""
        if _RULES_FILE.exists():
            try:
                data = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
                self._rules = [WatchRule.from_dict(d) for d in data]
                logger.info(f"WatchHooks: loaded {len(self._rules)} rules")
            except Exception as e:
                logger.warning(f"WatchHooks: failed to load rules: {e}")
                self._rules = []
        else:
            self._rules = []

    def save_rules(self):
        """Persist rules to storage."""
        try:
            data = [r.to_dict() for r in self._rules]
            _RULES_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"WatchHooks: failed to save rules: {e}")

    def add_rule(self, rule: WatchRule):
        """Add a new watch rule."""
        with self._lock:
            self._rules.append(rule)
            self.save_rules()
        logger.info(f"WatchHooks: added rule '{rule.name}'")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.rule_id != rule_id]
            if len(self._rules) < before:
                self.save_rules()
                return True
        return False

    def list_rules(self) -> List[WatchRule]:
        """Get all rules."""
        return self._rules.copy()

    # ── Evaluation ────────────────────────────────────────────

    def evaluate(self, filepath: str, event_type: str = "created"):
        """Check if any rules match this file event.
        
        Called by FileWatcher on file creation/modification.
        Matching rules execute their actions in a background thread.
        """
        for rule in self._rules:
            if not rule.enabled:
                continue

            if rule.matches(filepath):
                logger.info(
                    f"WatchHooks: Rule '{rule.name}' triggered for {filepath}"
                )
                # Execute action in background (non-blocking)
                threading.Thread(
                    target=self._execute_action,
                    args=(rule, filepath, event_type),
                    daemon=True,
                ).start()

    def _execute_action(self, rule: WatchRule, filepath: str, event_type: str):
        """Execute a watch rule's action."""
        store = get_event_store()

        store.insert(AgentEvent(
            event_type=EventType.WATCHER_TRIGGER.value,
            tool_name=rule.action,
            input_summary=f"Rule '{rule.name}' → {filepath}",
        ))

        if rule.action == "notify":
            msg = f"📁 New file matching '{rule.name}': {Path(filepath).name}"
            logger.info(f"WatchHooks: {msg}")
            if self.on_action:
                self.on_action(msg)
            return

        # Execute tool
        try:
            from services.tools import execute_tool
            args = dict(rule.action_args)
            args.setdefault("path", filepath)
            result = execute_tool(rule.action, **args)

            store.insert(AgentEvent(
                event_type=EventType.TOOL_RESULT.value,
                tool_name=rule.action,
                status="success" if result.success else "failed",
                output_summary=result.output[:300],
            ))

            if self.on_action and result.success:
                self.on_action(f"✅ {rule.name}: {result.output[:200]}")

        except Exception as e:
            logger.error(f"WatchHooks: Action failed for rule '{rule.name}': {e}")
            store.insert(AgentEvent.error(str(e)))


# ── Singleton ─────────────────────────────────────────────────
_instance: Optional[WatchHookEngine] = None
_init_lock = threading.Lock()


def get_watch_hooks() -> WatchHookEngine:
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = WatchHookEngine()
    return _instance
