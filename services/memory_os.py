"""
Neuron — MemoryOS Agent (v3 — Modular Architecture)
=====================================================
Orchestrator that wires together:
  - services.agent    (Task, TaskQueue, TaskExecutor)
  - services.events   (EventStore, AgentEvent)
  - services.profiles (ProfileManager)
  - services.plugins  (register_plugins)

Responsibilities:
  1. Accept user input
  2. Route to correct mode (auto-detect or explicit)
  3. Create Task objects for trackable execution
  4. Delegate execution to TaskExecutor
  5. Emit signals for UI updates

Does NOT own the LLM, tools, or event store.
"""
from __future__ import annotations

import json
import time
import threading
from typing import Optional, List, Dict, Callable

from app.logger import logger
from services.agent import Task, TaskQueue, TaskExecutor, TaskStatus, get_task_queue
from services.events import get_event_store, AgentEvent, EventType
from services.tools import ALL_TOOLS, get_tool_schemas
from services.profiles import get_profile_manager


# ── Intent Detection (lightweight, no LLM) ───────────────────

_ACTION_SIGNALS = frozenset({
    "organize", "move", "copy", "rename", "delete", "remove",
    "list files", "show files", "show folder", "dir",
    "install", "pip", "npm", "git", "build",
})

_SEARCH_SIGNALS = frozenset({
    "find", "search", "locate", "where is", "look for",
    "which file", "show me", "get my",
})

# These override ACTION signals — if present, route to CHAT
_CHAT_OVERRIDES = frozenset({
    "code", "program", "script", "algorithm", "function",
    "class", "implement", "write a", "create a", "generate a",
    "help me", "explain", "how to", "what is", "debug",
    "example", "tutorial", "syntax", "logic", "simulation",
})

# These FORCE action mode — explicit file/system operations only
_STRONG_ACTION = frozenset({
    "organize my", "move the", "delete the", "remove the",
    "rename the", "copy the", "run command", "execute command",
    "open folder", "list folder", "create folder", "make folder",
    "create file", "save file", "write file",
})


def _detect_intent(text: str) -> str:
    """Lightweight intent detection. Returns: chat | query | action.
    
    Priority:
      1. Search signals → query
      2. Strong action phrases → action
      3. Chat overrides → chat (even if "create" is present)
      4. Weak action signals → action
      5. Default → chat
    """
    words = text.lower()

    # 1. Search always wins
    if any(sig in words for sig in _SEARCH_SIGNALS):
        return "query"

    # 2. Strong action phrases (explicit file/system ops)
    if any(sig in words for sig in _STRONG_ACTION):
        return "action"

    # 3. Chat overrides trump weak action signals
    if any(sig in words for sig in _CHAT_OVERRIDES):
        return "chat"

    # 4. Weak action signals
    if any(sig in words for sig in _ACTION_SIGNALS):
        return "action"

    return "chat"


# ── MemoryOS Agent ────────────────────────────────────────────

class MemoryOSAgent:
    """Top-level agent orchestrator.
    
    Integrates all subsystems:
      - TaskExecutor  for tool calling
      - TaskQueue     for persistence
      - EventStore    for observability
      - ProfileManager for user settings
      - ResponseCache for persistent response caching
    
    UI callbacks:
      on_step(task, step)         — live step streaming
      on_thinking(task, message)  — "working..." indicators
      on_confirmation(name, args) — tool approval dialog
      on_task_update(task)        — task status changed
      on_token(token)             — streaming token callback
    """

    def __init__(self):
        self._engine = None
        self._executor: Optional[TaskExecutor] = None
        self._conversation: List[Dict] = []

        # UI callbacks (set by panel)
        self.on_step: Optional[Callable] = None
        self.on_thinking: Optional[Callable] = None
        self.on_confirmation: Optional[Callable] = None
        self.on_task_update: Optional[Callable] = None
        self.on_token: Optional[Callable] = None  # Streaming callback

    def _get_engine(self):
        if self._engine is None:
            from services.llm_engine import get_llm_engine
            self._engine = get_llm_engine()
        return self._engine

    def _get_executor(self) -> TaskExecutor:
        if self._executor is None:
            self._executor = TaskExecutor(engine=self._get_engine())
            # Wire UI callbacks through to executor
            self._executor.on_step = self.on_step
            self._executor.on_thinking = self.on_thinking
            self._executor.on_confirmation = self.on_confirmation
        return self._executor

    def clear_history(self):
        self._conversation.clear()
        logger.info("MemoryOS: conversation cleared")

    # ── Public API ────────────────────────────────────────────

    def chat(self, user_message: str, mode: str = "auto") -> str:
        """Process user message.
        
        Thread-safety is provided by LLMEngine's internal lock.
        No MemoryOS-level lock needed — removing it eliminates
        the UI freeze during long inference.
        
        Routing:
          - "auto" → keyword-based intent detection
          - "query" → force semantic search
          - "action" → force tool calling
        """
        store = get_event_store()
        store.insert(AgentEvent(
            event_type=EventType.USER_INPUT.value,
            input_summary=user_message[:300],
        ))

        # Determine mode
        effective = mode if mode != "auto" else _detect_intent(user_message)

        if effective == "query":
            return self._query_mode(user_message)
        elif effective == "action":
            return self._action_mode(user_message)
        else:
            return self._chat_mode(user_message)

    def submit_task(self, goal: str, mode: str = "auto") -> Task:
        """Submit a task to the queue and execute it.
        
        Returns the Task object for tracking.
        """
        task = Task(goal=goal, mode=mode)
        queue = get_task_queue()
        queue.enqueue(task)

        if self.on_task_update:
            self.on_task_update(task)

        # Execute in background
        threading.Thread(
            target=self._run_task,
            args=(task,),
            daemon=True,
        ).start()

        return task

    # ── Chat Mode (fast, no tools) ────────────────────────────

    # Instant responses for common greetings (no LLM needed)
    _GREETINGS = {
        "hi": "Hello! I'm Neuron. How can I help you?",
        "hello": "Hey there! What can I do for you?",
        "hey": "Hi! Ready to help. What do you need?",
        "hi there": "Hello! I'm Neuron MemoryOS. How can I assist you?",
        "hello there": "Hi! I'm ready to help. Ask me anything.",
        "good morning": "Good morning! What can I help you with today?",
        "good evening": "Good evening! How can I help you?",
        "thanks": "You're welcome! Anything else?",
        "thank you": "You're welcome! Let me know if you need anything else.",
    }

    def _chat_mode(self, user_message: str) -> str:
        """Direct conversation with streaming + persistent caching.
        
        Performance tiers:
          1. Greetings:    0ms   (hardcoded, no LLM)
          2. Cache hit:    <5ms  (SQLite lookup)
          3. Streaming:    ~300ms TTFT, tokens appear live
        
        Token budget:
          - Short query: 100 tokens
          - Code request: 800 tokens
          - Normal: profile default (512)
        """
        from services.cache import get_response_cache
        from services.llm_engine import _strip_thinking

        low = user_message.lower().strip().rstrip("!?.")

        # ── Tier 1: Instant greeting (0ms) ────────────────────
        if low in self._GREETINGS:
            response = self._GREETINGS[low]
            self._conversation.append({"role": "user", "content": user_message})
            self._conversation.append({"role": "assistant", "content": response})
            logger.info(f"MemoryOS [CHAT]: 0ms (greeting), {len(response)} chars")
            return response

        # ── Tier 2: Persistent cache hit (<5ms) ───────────────
        cache_key = low[:120]
        cache = get_response_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            self._conversation.append({"role": "user", "content": user_message})
            self._conversation.append({"role": "assistant", "content": cached})
            logger.info(f"MemoryOS [CHAT]: <5ms (cached), {len(cached)} chars")
            return cached

        # ── Tier 3: LLM inference with streaming ─────────────
        engine = self._get_engine()
        profile = get_profile_manager().get_active()

        self._conversation.append({"role": "user", "content": user_message})
        self._compact()

        from services.agent_context import build_chat_context
        messages = [{"role": "system", "content": build_chat_context()}]
        messages.extend(self._conversation[-8:])

        # Dynamic token budget
        if len(low.split()) <= 3 and not any(w in low for w in ("code", "write", "create", "explain")):
            max_tokens = 100   # Short query → fast
        elif any(w in low for w in ("code", "program", "script", "algorithm", "implement", "function", "class")):
            max_tokens = 800   # Code generation → needs room
        else:
            max_tokens = profile.llm.max_tokens_chat

        t0 = time.time()

        # Stream if callback is set, otherwise batch
        if self.on_token is not None:
            # Streaming mode — emit tokens live
            chunks = []
            for token in engine.chat_stream(
                messages=messages,
                max_tokens=max_tokens,
                temperature=profile.llm.temperature,
            ):
                chunks.append(token)
                try:
                    self.on_token(token)
                except Exception:
                    pass  # UI callback failure shouldn't kill inference
            raw = "".join(chunks)
            response = _strip_thinking(raw.strip()) if raw else ""
        else:
            # Batch mode (fallback)
            response = engine.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=profile.llm.temperature,
            )

        elapsed = int((time.time() - t0) * 1000)

        store = get_event_store()
        store.insert(AgentEvent.llm_inference(elapsed))

        if not response or not response.strip():
            response = "Hello! I'm Neuron. How can I help you?"

        # Persist to cache (short answers only, not code blocks)
        if len(response) < 500 and len(low.split()) <= 8:
            cache.put(cache_key, response)

        self._conversation.append({"role": "assistant", "content": response})
        logger.info(f"MemoryOS [CHAT]: {elapsed}ms, {len(response)} chars, budget={max_tokens}")
        return response

    # ── Query Mode (search + summarize) ───────────────────────

    def _query_mode(self, user_message: str) -> str:
        """Semantic search + AI summary."""
        engine = self._get_engine()
        profile = get_profile_manager().get_active()
        store = get_event_store()

        # Search (fast, no LLM)
        results = self._run_search(user_message)

        store.insert(AgentEvent(
            event_type=EventType.SEARCH.value,
            input_summary=user_message[:300],
            output_summary=f"{len(results)} results",
        ))

        if results:
            raw_list = "\n".join(
                f"  {i+1}. {r.get('name', '')} — {r['path']}"
                for i, r in enumerate(results[:8])
            )
        else:
            raw_list = ""

        # Summarize with LLM
        from services.agent_context import build_query_context
        messages = [{"role": "system", "content": build_query_context()}]

        if results:
            messages.append({
                "role": "user",
                "content": (
                    f"The user searched for: '{user_message}'\n"
                    f"Results:\n{raw_list}\n\n"
                    f"List these files concisely. No explanation needed."
                ),
            })
        else:
            messages.append({
                "role": "user",
                "content": f"The user searched for: '{user_message}'\nNo files found.",
            })

        t0 = time.time()
        response = engine.chat(messages=messages, max_tokens=350, temperature=0.2)
        elapsed = int((time.time() - t0) * 1000)

        store.insert(AgentEvent.llm_inference(elapsed))

        # Fallback
        if not response or not response.strip():
            if results:
                response = f"Found {len(results)} matching files:\n{raw_list}"
            else:
                response = "No matching files found. Try a different query."

        logger.info(f"MemoryOS [QUERY]: {elapsed}ms, {len(results)} results")
        return response

    def _run_search(self, query: str) -> List[Dict]:
        """Execute semantic search with profile weights."""
        try:
            from core.search.semantic_search import SemanticSearch
            searcher = SemanticSearch()
            results = searcher.search(query, top_k=10)
            return [
                {
                    "path": r["path"],
                    "name": r.get("name", ""),
                    "score": r.get("combined_score", 0),
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"MemoryOS: search failed: {e}")
            return []

    # ── Action Mode (task-based tool calling) ─────────────────

    def _action_mode(self, user_message: str) -> str:
        """Create and execute a task with the TaskExecutor."""
        task = Task(goal=user_message, mode="action")
        queue = get_task_queue()
        queue.enqueue(task)

        executor = self._get_executor()
        result = executor.run(task)

        queue.update(task)

        if self.on_task_update:
            self.on_task_update(task)

        return result

    # ── Background Task Runner ────────────────────────────────

    def _run_task(self, task: Task):
        """Execute a task in the background."""
        queue = get_task_queue()
        executor = self._get_executor()

        try:
            executor.run(task)
        except Exception as e:
            task.fail(str(e))

        queue.update(task)

        if self.on_task_update:
            self.on_task_update(task)

    # ── History Management ────────────────────────────────────

    def _compact(self):
        if len(self._conversation) > 40:
            self._conversation = self._conversation[-20:]


# ── Singleton ─────────────────────────────────────────────────
_agent: Optional[MemoryOSAgent] = None
_lock = threading.Lock()


def get_memory_os() -> MemoryOSAgent:
    global _agent
    if _agent is None:
        with _lock:
            if _agent is None:
                _agent = MemoryOSAgent()
    return _agent
