"""
Neuron — Task Executor
========================
Executes tasks using the LLM + tool registry.

Responsibilities:
  1. Run LLM inference with native function calling
  2. Execute tool calls with validation
  3. Emit AgentEvents for every action
  4. Update Task state at each step
  5. Emit pyqtSignal-compatible callbacks for UI streaming

Design:
  - Does NOT own the LLM engine or tool registry (injected)
  - Does NOT own the UI (emits callbacks)
  - Pure orchestration logic
"""
from __future__ import annotations

import json
import time
from typing import Optional, Callable, Dict, List, Any

from app.logger import logger
from services.agent.task import Task, TaskStep, TaskStatus
from services.events import AgentEvent, EventType, EventStatus, get_event_store
from services.validation import validate_tool_args
from services.tools import (
    ALL_TOOLS, get_tool, execute_tool, get_tool_schemas,
    ToolResult, PermissionLevel,
)


MAX_TURNS = 6  # Maximum tool-call turns per task


class TaskExecutor:
    """Executes a single Task to completion.
    
    Usage:
        executor = TaskExecutor(engine=get_llm_engine())
        executor.on_step = lambda task, step: update_ui(step)
        result = executor.run(task)
    
    Callbacks (set by caller):
        on_step(task, step)           — fired after each step
        on_thinking(task, message)    — fired when LLM is processing
        on_confirmation(tool, args)   — returns True/False for MODERATE tools
    """

    def __init__(self, engine=None):
        self._engine = engine
        self._tool_schemas: Optional[List[Dict]] = None

        # Callbacks for UI streaming (set by caller)
        self.on_step: Optional[Callable] = None
        self.on_thinking: Optional[Callable] = None
        self.on_confirmation: Optional[Callable] = None

    def _get_engine(self):
        if self._engine is None:
            from services.llm_engine import get_llm_engine
            self._engine = get_llm_engine()
        return self._engine

    def _get_schemas(self) -> List[Dict]:
        if self._tool_schemas is None:
            self._tool_schemas = get_tool_schemas()
        return self._tool_schemas

    def _select_relevant_schemas(self, goal: str) -> List[Dict]:
        """Select only relevant tool schemas based on the goal.
        
        Sending all 14 schemas to a 3B model creates a massive prompt
        (2000+ tokens) and causes 60-90 second inference times.
        Selecting 4-6 relevant tools cuts this to ~5-10 seconds.
        """
        keywords = goal.lower()
        all_schemas = self._get_schemas()

        # Tool relevance scoring based on keywords
        _TOOL_KEYWORDS = {
            "file_read":       {"read", "open", "content", "view", "show"},
            "file_write":      {"write", "create", "save", "make"},
            "file_edit":       {"edit", "modify", "change", "update"},
            "file_delete":     {"delete", "remove", "trash", "erase"},
            "folder_create":   {"folder", "directory", "mkdir", "create folder"},
            "folder_list":     {"list", "dir", "folder", "what's in", "show folder"},
            "folder_search":   {"search", "find", "locate", "where"},
            "folder_organize": {"organize", "sort", "clean", "arrange"},
            "semantic_search": {"search", "find", "about", "related"},
            "summarize":       {"summarize", "summary", "describe", "overview"},
            "shell":           {"run", "command", "shell", "cmd", "pip", "npm", "git"},
            "python_exec":     {"python", "code", "script", "execute", "run python"},
            "glob":            {"glob", "pattern", "find files", "wildcard"},
            "ocr":             {"ocr", "image", "text from", "screenshot"},
        }

        scored = []
        for schema in all_schemas:
            name = schema.get("function", {}).get("name", "")
            kw_set = _TOOL_KEYWORDS.get(name, set())
            score = sum(1 for kw in kw_set if kw in keywords)
            scored.append((score, schema))

        # Sort by relevance, take top 5
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [s for _, s in scored[:5]]

        # Always include at least folder_list and file_read (most common)
        names = {s.get("function", {}).get("name") for s in selected}
        for fallback in ["folder_list", "file_read"]:
            if fallback not in names:
                for s in all_schemas:
                    if s.get("function", {}).get("name") == fallback:
                        selected.append(s)
                        break

        logger.info(f"Executor: Selected {len(selected)} tools for: {goal[:50]}")
        return selected

    # ── Main execution loop ───────────────────────────────────

    def run(self, task: Task) -> str:
        """Execute a task to completion. Returns the final response.
        
        This is the agent's ReAct loop:
          1. Build messages from task context
          2. Call LLM with tools
          3. If tool_call → validate → execute → observe → loop
          4. If content → return as final answer
        """
        task.status = TaskStatus.RUNNING.value
        store = get_event_store()

        store.insert(AgentEvent(
            event_type=EventType.TASK_CREATED.value,
            input_summary=task.goal[:500],
            task_id=task.task_id,
        ))

        try:
            result = self._execute_loop(task)
            task.complete(result)
            store.insert(AgentEvent(
                event_type=EventType.TASK_COMPLETED.value,
                duration_ms=task.elapsed_ms,
                output_summary=result[:500],
                task_id=task.task_id,
            ))
            return result

        except Exception as e:
            error_msg = str(e)
            task.fail(error_msg)
            store.insert(AgentEvent.error(error_msg, task.task_id))
            logger.error(f"Executor: Task [{task.task_id}] failed: {e}")
            return f"Task failed: {error_msg}"

    def _execute_loop(self, task: Task) -> str:
        """Core ReAct loop with native function calling."""
        engine = self._get_engine()
        schemas = self._select_relevant_schemas(task.goal)
        store = get_event_store()

        from services.agent_context import build_action_context
        conversation: List[Dict] = []

        for turn in range(MAX_TURNS):
            if self.on_thinking:
                self.on_thinking(task, f"Step {turn + 1}/{MAX_TURNS}...")

            # Build messages
            messages = [{"role": "system", "content": build_action_context("")}]
            messages.append({"role": "user", "content": task.goal})
            messages.extend(conversation)

            # LLM inference with native tools
            t0 = time.time()
            try:
                result_msg = engine.chat_with_tools(
                    messages=messages,
                    tools=schemas,
                    max_tokens=300,
                    temperature=0.3,
                )
            except Exception as e:
                # Fallback to plain chat if tool calling fails
                logger.warning(f"Executor: Native tools failed, falling back: {e}")
                response = engine.chat(messages=messages, max_tokens=300, temperature=0.3)
                return response or "I was unable to complete the task."

            elapsed_ms = int((time.time() - t0) * 1000)

            store.insert(AgentEvent.llm_inference(elapsed_ms, task_id=task.task_id))

            # Check for tool calls
            tool_calls = result_msg.get("tool_calls")
            content = result_msg.get("content", "")

            if tool_calls and len(tool_calls) > 0:
                tc = tool_calls[0]
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")

                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                if tool_name and tool_name in ALL_TOOLS:
                    # Execute tool with validation + events
                    step_result = self._execute_tool_step(
                        task, tool_name, tool_args
                    )

                    # Add observation to conversation
                    conversation.append({
                        "role": "assistant",
                        "content": content or f"Calling {tool_name}...",
                    })
                    conversation.append({
                        "role": "user",
                        "content": f"[Tool Result: {tool_name}]\n{step_result}",
                    })
                    continue  # Next turn

            # No tool call — this is the final answer
            if content and content.strip():
                return content.strip()

        # Max turns exhausted
        return "Completed the available steps. Please check the results."

    def _execute_tool_step(
        self, task: Task, tool_name: str, raw_args: Dict
    ) -> str:
        """Execute a single tool call with validation and event logging."""
        store = get_event_store()
        tool = get_tool(tool_name)

        if tool is None:
            return f"[ERROR] Unknown tool: {tool_name}"

        # Step tracking
        step = task.add_step(
            action=tool_name,
            description=f"Calling {tool_name}",
            **raw_args,
        )
        step.status = TaskStatus.RUNNING.value

        # Emit start event
        store.insert(AgentEvent.tool_started(
            tool_name, json.dumps(raw_args)[:300], task.task_id
        ))

        # Permission check
        if tool.permission == PermissionLevel.DANGEROUS:
            step.status = EventStatus.BLOCKED.value
            step.output = "BLOCKED: Dangerous operation denied."
            if self.on_step:
                self.on_step(task, step)
            return "[BLOCKED] Dangerous operation denied."

        if tool.permission == PermissionLevel.MODERATE:
            if self.on_confirmation:
                approved = self.on_confirmation(tool_name, raw_args)
                if not approved:
                    step.status = EventStatus.DENIED.value
                    step.output = "User denied."
                    if self.on_step:
                        self.on_step(task, step)
                    return "[DENIED] User declined this action."

        # Validate arguments
        valid, cleaned_args, error = validate_tool_args(
            tool_name, tool.parameters, raw_args
        )
        if not valid:
            step.status = EventStatus.FAILED.value
            step.output = f"Validation: {error}"
            if self.on_step:
                self.on_step(task, step)
            store.insert(AgentEvent.tool_finished(
                tool_name, False, error, 0, task.task_id
            ))
            return f"[VALIDATION ERROR] {error}"

        # Execute
        t0 = time.time()
        try:
            result = execute_tool(tool_name, **cleaned_args)
        except Exception as e:
            result = ToolResult(False, f"Execution error: {e}")

        duration_ms = int((time.time() - t0) * 1000)

        # Update step
        step.status = EventStatus.SUCCESS.value if result.success else EventStatus.FAILED.value
        step.output = result.output[:1000]
        step.duration_ms = duration_ms

        # Emit events + UI callback
        store.insert(AgentEvent.tool_finished(
            tool_name, result.success, result.output[:300], duration_ms, task.task_id
        ))

        if self.on_step:
            self.on_step(task, step)

        status_tag = "OK" if result.success else "FAIL"
        logger.info(
            f"Executor: [{task.task_id}] {tool_name} -> "
            f"{status_tag} ({duration_ms}ms, {len(result.output)} chars)"
        )
        return f"[{status_tag}] {result.output[:2000]}"
