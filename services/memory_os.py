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
import os
import re
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Callable

from app.logger import logger
from services.agent import Task, TaskQueue, TaskExecutor, TaskStatus, get_task_queue
from services.events import get_event_store, AgentEvent, EventType
from services.memory_context import get_memory_context_store
from services.tools import ALL_TOOLS, get_tool_schemas
from services.profiles import get_profile_manager


def _live_context_for_prompt(user_message: str) -> tuple[str, int, bool]:
    """Return opt-in public live context. Never passes local RAG data out."""
    try:
        from services.internet_search import (
            format_results_for_prompt,
            should_use_live_data,
            search_public_web,
        )
        if not should_use_live_data(user_message):
            return "", 0, False
        results = search_public_web(user_message)
        return format_results_for_prompt(results), len(results), True
    except Exception as exc:
        logger.warning(f"MemoryOS: live internet context skipped: {exc}")
        return "", 0, True


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
    try:
        value = int(os.getenv(name, str(default)) or str(default))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _verified_live_answer(live_context: str) -> tuple[str, str, str] | None:
    """Extract a trusted live answer marker from the retrieved web context."""
    for line in live_context.splitlines():
        if "ANSWER_VALUE:" not in line:
            continue
        value_match = re.search(
            r"ANSWER_VALUE:\s*(.+?)(?=\s+Public web source text|$)",
            line,
            flags=re.I,
        )
        if not value_match:
            continue
        source_match = re.match(r"\s*\d+\.\s+(.*?)\s+\((https?://[^)]+)\)", line)
        answer = " ".join(value_match.group(1).split()).rstrip(".")
        if not answer:
            continue
        title = source_match.group(1).strip() if source_match else "Live public web result"
        url = source_match.group(2).strip() if source_match else ""
        return answer, title, url
    return None


def _normalize_verified_live_response(response: str, live_context: str) -> str:
    """Keep verified live answers concise when the small model leaks context text."""
    verified = _verified_live_answer(live_context)
    clean = (response or "").strip()
    if not verified:
        return clean

    answer, title, url = verified
    low = clean.lower()
    needs_normalization = (
        not clean
        or answer.lower() not in low
        or "**source:**" not in low
        or (url and url not in clean)
        or "answer_value:" in low
        or "public web source text identifies" in low
    )
    if not needs_normalization:
        return clean

    source = f"{title} ({url})" if url else title
    return f"**Answer:** {answer}\n\n**Source:** {source}"


# ── Intent Detection (embedding-based, no hardcodes) ─────────

def _detect_intent(text: str) -> str:
    """Classify user intent using embedding similarity.
    
    Uses cosine similarity against pre-computed centroids
    from storage/intent_examples.json.
    
    Returns: chat | query | action
    Latency: ~5ms (embedding only, no LLM)
    Fallback: 'chat' if classifier unavailable
    """
    from services.intent import get_intent_classifier
    classifier = get_intent_classifier()
    intent, confidence = classifier.classify(text)
    return intent


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
        self._memory = get_memory_context_store()
        self._conversation: List[Dict] = [
            {"role": msg["role"], "content": msg["content"], "mode": msg.get("mode", "chat")}
            for msg in self._memory.recent_messages(limit=24)
        ]

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
        # Wire UI callbacks through on every access; UI callbacks can be attached
        # after the singleton executor has already been created.
        self._executor.on_step = self.on_step
        self._executor.on_thinking = self.on_thinking
        self._executor.on_confirmation = self.on_confirmation
        return self._executor

    def clear_history(self):
        self._conversation.clear()
        self._memory.clear()
        logger.info("MemoryOS: conversation cleared")

    def _remember(self, role: str, content: str, mode: str) -> None:
        text = (content or "").strip()
        if not text:
            return
        self._conversation.append({"role": role, "content": text, "mode": mode})
        self._memory.append(role=role, content=text, mode=mode)
        self._compact()

    @staticmethod
    def _trim_history_content(content: str, max_chars: int) -> str:
        text = " ".join(str(content or "").split())
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    def _recent_messages(
        self,
        limit: int = 10,
        max_chars_per_message: int = 700,
        modes: Optional[set[str]] = None,
    ) -> List[Dict]:
        if not self._conversation:
            self._conversation = [
                {"role": msg["role"], "content": msg["content"], "mode": msg.get("mode", "chat")}
                for msg in self._memory.recent_messages(limit=24)
            ]
        selected: list[Dict] = []
        for msg in reversed(self._conversation):
            if len(selected) >= limit:
                break
            if msg.get("role") not in {"user", "assistant"} or not msg.get("content"):
                continue
            if modes is not None and msg.get("mode", "chat") not in modes:
                continue
            selected.append({
                "role": msg["role"],
                "content": self._trim_history_content(msg["content"], max_chars_per_message),
            })
        return list(reversed(selected))

    def _context_block(self, limit: int = 12, max_chars: int = 5000) -> str:
        return self._memory.format_recent_context(limit=limit, max_chars=max_chars)

    def _latest_code_artifact(self) -> Optional[tuple[str, str]]:
        """Return the most recent fenced code block from assistant context."""
        sources = list(self._conversation)
        if not sources:
            sources = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self._memory.recent_messages(limit=24)
            ]
        fence = re.compile(r"```([A-Za-z0-9_+#.-]*)\s*\n?(.*?)```", re.DOTALL)
        for msg in reversed(sources):
            if msg.get("role") != "assistant":
                continue
            matches = list(fence.finditer(msg.get("content", "") or ""))
            for match in reversed(matches):
                lang = (match.group(1) or "").strip().lower()
                code = (match.group(2) or "").strip()
                if len(code) >= 20:
                    return lang, code
        return None

    @staticmethod
    def _looks_like_code_followup(user_message: str) -> bool:
        low = (user_message or "").lower()
        wants_persist_or_run = re.search(
            r"\b(save|write|create|store|run|execute|compile|test|"
            r"alter|edit|modify|update|insert|add|change)\b",
            low,
        )
        refers_to_previous = re.search(
            r"\b(it|this|that|program|code|file|script|class)\b", low
        )
        return bool(wants_persist_or_run and refers_to_previous)

    @staticmethod
    def _looks_like_code_creation(user_message: str) -> bool:
        low = (user_message or "").lower()
        has_code_subject = re.search(
            r"\b(code|program|project|app|application|class|java|python|"
            r"javascript|typescript|html|css|database|sql|jdbc|script)\b",
            low,
        )
        has_creation = re.search(
            r"\b(give|create|write|make|build|generate|save|run|compile)\b",
            low,
        )
        return bool(has_code_subject and has_creation)

    @staticmethod
    def _wants_run(user_message: str) -> bool:
        return bool(re.search(r"\b(run|execute|compile|test)\b", (user_message or "").lower()))

    @staticmethod
    def _wants_modify(user_message: str) -> bool:
        return bool(
            re.search(
                r"\b(alter|edit|modify|update|insert|add|change)\b",
                (user_message or "").lower(),
            )
        )

    @staticmethod
    def _extract_generated_code(text: str) -> Optional[tuple[str, str]]:
        fence = re.compile(r"```([A-Za-z0-9_+#.-]*)\s*\n?(.*?)```", re.DOTALL)
        matches = list(fence.finditer(text or ""))
        if matches:
            best = max(matches, key=lambda match: len(match.group(2) or ""))
            lang = (best.group(1) or "").strip().lower()
            code = (best.group(2) or "").strip()
            if len(code) >= 20:
                return lang, code

        raw = (text or "").strip()
        if len(raw) < 40:
            return None
        code_markers = (
            "public class ",
            "class ",
            "def ",
            "import ",
            "#include",
            "function ",
            "const ",
            "<!doctype html",
        )
        if any(marker in raw.lower() for marker in code_markers):
            return "", raw
        return None

    def _thinking(self, message: str) -> None:
        if self.on_thinking:
            try:
                self.on_thinking(message)
            except TypeError:
                try:
                    self.on_thinking(None, message)
                except Exception:
                    pass
            except Exception:
                pass

    @staticmethod
    def _infer_code_file(lang: str, code: str) -> tuple[str, str]:
        low_lang = (lang or "").lower()
        if "java" in low_lang or "public class " in code or re.search(r"\bclass\s+\w+", code):
            match = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)", code)
            if not match:
                match = re.search(r"\bclass\s+([A-Za-z_]\w*)", code)
            class_name = match.group(1) if match else "NeuronProgram"
            return f"{class_name}.java", class_name
        if "python" in low_lang or low_lang == "py":
            return "neuron_script.py", ""
        if low_lang in {"javascript", "js"}:
            return "neuron_script.js", ""
        if low_lang in {"typescript", "ts"}:
            return "neuron_script.ts", ""
        if low_lang in {"html"}:
            return "neuron_page.html", ""
        return "neuron_artifact.txt", ""

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _generate_code_artifact(self, user_message: str, context: str = "") -> Optional[tuple[str, str]]:
        """Generate one complete code artifact for deterministic Action mode."""
        engine = self._get_engine()
        self._thinking("Drafting source code with local Qwen 3B...")
        t0 = time.time()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Neuron's offline coding worker. Return exactly one "
                    "complete, runnable source file in a fenced Markdown code "
                    "block. Do not include prose outside the code block. Prefer "
                    "small standard-library examples unless the user asks for a "
                    "specific dependency. Keep the first draft compact: usually "
                    "80-160 lines, one file, and no tutorial text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"Create the requested code for this Action-mode task:\n"
                    f"{user_message}"
                ).strip(),
            },
        ]
        response = engine.chat(messages=messages, max_tokens=1100, temperature=0.25)
        logger.info(
            "MemoryOS [ACTION]: code generation finished in %dms (%d chars)",
            int((time.time() - t0) * 1000),
            len(response or ""),
        )
        if not response or response.startswith("[AI") or response.startswith("AI unavailable"):
            return None
        return self._extract_generated_code(response)

    def _rewrite_code_artifact(
        self,
        lang: str,
        code: str,
        user_message: str,
    ) -> Optional[tuple[str, str]]:
        """Rewrite an existing code block for edit/alter follow-up requests."""
        engine = self._get_engine()
        self._thinking("Rewriting the existing code with local Qwen 3B...")
        t0 = time.time()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Neuron's offline code editor. Modify the supplied "
                    "source file according to the user's request. Return exactly "
                    "one complete source file in a fenced Markdown code block. "
                    "Do not include prose outside the code block."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language hint: {lang or 'unknown'}\n"
                    f"User edit request: {user_message}\n\n"
                    f"Existing code:\n```{lang}\n{code}\n```"
                ),
            },
        ]
        response = engine.chat(messages=messages, max_tokens=1200, temperature=0.2)
        logger.info(
            "MemoryOS [ACTION]: code rewrite finished in %dms (%d chars)",
            int((time.time() - t0) * 1000),
            len(response or ""),
        )
        if not response or response.startswith("[AI") or response.startswith("AI unavailable"):
            return None
        return self._extract_generated_code(response)

    def _save_and_optionally_run_code(
        self,
        lang: str,
        code: str,
        user_message: str,
        task: Task,
        executor: TaskExecutor,
    ) -> str:
        filename, entry = self._infer_code_file(lang, code)
        workspace = Path.home() / "NeuronWorkspace"
        path = workspace / filename

        outputs: list[str] = []
        self._thinking(f"Preparing file write: {path.name}")
        write_result = executor._execute_tool_step(
            task,
            "file_write",
            {"path": str(path), "content": code, "overwrite": True},
        )
        outputs.append("File write:\n" + write_result)

        if self._wants_run(user_message):
            self._thinking("Preparing terminal command...")
            command = ""
            suffix = path.suffix.lower()
            if suffix == ".java":
                build_dir = workspace / "build"
                command = (
                    f"New-Item -ItemType Directory -Force -Path {self._ps_quote(str(build_dir))} | Out-Null; "
                    f"javac -encoding UTF-8 -d {self._ps_quote(str(build_dir))} {self._ps_quote(str(path))}; "
                    f"if ($LASTEXITCODE -eq 0) {{ java -cp {self._ps_quote(str(build_dir))} {entry} }}"
                )
            elif suffix == ".py":
                command = f"python {self._ps_quote(str(path))}"
            elif suffix == ".js":
                command = f"node {self._ps_quote(str(path))}"
            elif suffix == ".ts":
                command = f"npx ts-node {self._ps_quote(str(path))}"

            if command:
                self._thinking("Running in persistent PowerShell...")
                run_result = executor._execute_tool_step(
                    task,
                    "powershell_session",
                    {"command": command, "cwd": str(workspace), "timeout": 45},
                )
                outputs.append("PowerShell run:\n" + run_result)

        return (
            f"Saved the Action-mode code artifact to `{path}`.\n\n"
            + "\n\n".join(outputs)
        )

    def _run_contextual_code_followup(self, user_message: str, task: Task, executor: TaskExecutor) -> Optional[str]:
        """Save/run the previous code block without waiting for weak tool-call inference."""
        if not self._looks_like_code_followup(user_message):
            return None
        artifact = self._latest_code_artifact()
        if artifact is None:
            return None

        lang, code = artifact
        if self._wants_modify(user_message):
            rewritten = self._rewrite_code_artifact(lang, code, user_message)
            if rewritten is not None:
                lang, code = rewritten

        return self._save_and_optionally_run_code(lang, code, user_message, task, executor)

    def _run_coding_action(self, user_message: str, task: Task, executor: TaskExecutor) -> Optional[str]:
        """Generate/save/run code through tools instead of hoping the model chooses them."""
        if not self._looks_like_code_creation(user_message):
            return None
        self._thinking("Preparing a deterministic coding workflow...")
        context = self._context_block(limit=6, max_chars=1800)
        artifact = self._generate_code_artifact(user_message, context)
        if artifact is None:
            return None
        lang, code = artifact
        return self._save_and_optionally_run_code(lang, code, user_message, task, executor)

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

        effective = _detect_intent(user_message) if mode == "auto" else mode

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

    def _chat_mode(self, user_message: str) -> str:
        """Direct conversation with Qwen streaming.
        
        Performance tiers:
          1. Optional exact cache: <5ms when NEURON_CHAT_RESPONSE_CACHE=1
          2. Streaming Qwen:       tokens appear as llama.cpp emits them

        Token budget:
          - Short query: NEURON_CHAT_SHORT_MAX_TOKENS, default 32
          - Code request: 800 tokens
          - Normal: profile default (512)
        """
        from services.cache import get_response_cache
        from services.llm_engine import _strip_thinking

        low = user_message.lower().strip().rstrip("!?.")
        live_context, live_count, live_attempted = _live_context_for_prompt(user_message)
        if live_attempted and not live_context:
            logger.warning("MemoryOS [CHAT]: live data requested but no internet results returned")
            return (
                "I could not retrieve live internet results for that question, "
                "so I will not answer it from stale model memory. Please check "
                "your connection or try again."
            )

        # Optional exact response cache. Disabled by default so normal chat
        # measures real Qwen generation instead of hiding latency.
        cache_key = low[:120]
        cache = get_response_cache() if _env_flag("NEURON_CHAT_RESPONSE_CACHE", False) else None
        cached = None if live_context or cache is None else cache.get(cache_key)
        if cached is not None:
            self._remember("user", user_message, "chat")
            self._remember("assistant", cached, "chat")
            logger.info(f"MemoryOS [CHAT]: <5ms (cached), {len(cached)} chars")
            return cached

        # LLM inference with streaming.
        engine = self._get_engine()
        profile = get_profile_manager().get_active()

        self._remember("user", user_message, "chat")

        from services.agent_context import build_chat_context
        if live_context:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Neuron's live-data synthesis step. "
                        "Use only the provided public web context. "
                        "Do not answer from model memory. "
                        "For office-holder questions, extract the named person "
                        "from the source text, for example from phrases like "
                        "'Hon'ble Chief Minister Thiru X'. "
                        "Return concise Markdown using exactly this shape: "
                        "**Answer:** ... then **Source:** ..."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{live_context}\n\n"
                        f"Question: {user_message}\n\n"
                        "Answer the question directly. If the context does not "
                        "contain the answer, say that live results did not verify it. "
                        "Include the source URL from the context."
                    ),
                },
            ]
        else:
            messages = [{"role": "system", "content": build_chat_context()}]
            history_limit = _env_int("NEURON_CHAT_HISTORY_LIMIT", 1, minimum=0, maximum=24)
            history_chars = _env_int("NEURON_CHAT_HISTORY_CHARS", 180, minimum=80, maximum=1500)
            messages.extend(
                self._recent_messages(
                    limit=history_limit,
                    max_chars_per_message=history_chars,
                    modes={"chat"},
                )
            )

        # Dynamic token budget
        if len(low.split()) <= 3 and not any(w in low for w in ("code", "write", "create", "explain")):
            max_tokens = _env_int("NEURON_CHAT_SHORT_MAX_TOKENS", 32, minimum=16, maximum=128)
        elif any(w in low for w in ("code", "program", "script", "algorithm", "implement", "function", "class")):
            max_tokens = 800   # Code generation → needs room
        else:
            max_tokens = profile.llm.max_tokens_chat

        t0 = time.time()

        # Stream if callback is set, otherwise batch
        if self.on_token is not None:
            # Streaming mode — emit tokens live, suppress <think> blocks
            chunks = []
            in_think = False
            think_buffer = ""

            for token in engine.chat_stream(
                messages=messages,
                max_tokens=max_tokens,
                temperature=profile.llm.temperature,
            ):
                chunks.append(token)
                think_buffer += token

                # Detect <think> opening
                if not in_think and "<think>" in think_buffer:
                    # Emit any text BEFORE <think>
                    before = think_buffer.split("<think>", 1)[0]
                    if before:
                        try:
                            self.on_token(before)
                        except Exception:
                            pass
                    in_think = True
                    think_buffer = ""
                    continue

                # Detect </think> closing
                if in_think and "</think>" in think_buffer:
                    # Discard everything inside think block
                    after = think_buffer.split("</think>", 1)[1]
                    in_think = False
                    think_buffer = ""
                    if after:
                        try:
                            self.on_token(after)
                        except Exception:
                            pass
                    continue

                # If inside think block, suppress (don't emit)
                if in_think:
                    continue

                # Not in think block — emit and clear buffer
                # But wait for potential partial "<think" at end
                if "<" in think_buffer and not think_buffer.endswith(">"):
                    # Might be start of <think> tag — wait for more
                    continue

                try:
                    self.on_token(think_buffer)
                except Exception:
                    pass
                think_buffer = ""

            # Flush any remaining buffer
            if think_buffer and not in_think:
                try:
                    self.on_token(think_buffer)
                except Exception:
                    pass

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

        # Sanitize: strip hallucinated tool-call syntax from chat output
        # SmolLM3-3B sometimes outputs 'functions.tool_name:' as plain text
        response = re.sub(r'functions\.\w+:.*', '', response).strip()
        if not response:
            response = "Hello! I'm Neuron. How can I help you?"
        if live_context:
            response = _normalize_verified_live_response(response, live_context)

        # Persist to cache only when explicitly enabled. This is useful for
        # demos, but it is not a model-generation speedup.
        if cache is not None and not live_context and len(response) < 500 and len(low.split()) <= 8:
            cache.put(cache_key, response)

        self._remember("assistant", response, "chat")
        logger.info(
            f"MemoryOS [CHAT]: {elapsed}ms, {len(response)} chars, "
            f"budget={max_tokens}, live={live_count}"
        )
        return response

    # ── Query Mode (search + summarize) ───────────────────────

    def _query_mode(self, user_message: str) -> str:
        """Semantic search + AI summary."""
        engine = self._get_engine()
        profile = get_profile_manager().get_active()
        store = get_event_store()
        self._remember("user", user_message, "query")

        # Search (fast, no LLM)
        results = self._run_search(user_message)
        live_context, live_count, live_attempted = _live_context_for_prompt(user_message)
        if live_attempted and not live_context and not results:
            logger.warning("MemoryOS [QUERY]: live data requested but no internet results returned")
            return (
                "I could not retrieve live internet results for that query, "
                "and no local files matched. I will not answer it from stale "
                "model memory."
            )

        store.insert(AgentEvent(
            event_type=EventType.SEARCH.value,
            input_summary=user_message[:300],
            output_summary=f"{len(results)} local results, {live_count} live results",
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

        if results or live_context:
            local_part = f"Local file results:\n{raw_list}\n\n" if results else "No local files found.\n\n"
            live_part = f"{live_context}\n\n" if live_context else ""
            memory_part = f"Recent MemoryOS context:\n{self._context_block(limit=8, max_chars=2500)}\n\n"
            messages.append({
                "role": "user",
                "content": (
                    f"The user searched for: '{user_message}'\n"
                    f"{memory_part}{local_part}{live_part}"
                    "Answer concisely. Keep local file results and live public web "
                    "results clearly separate when both are present."
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
        if live_context:
            response = _normalize_verified_live_response(response, live_context)

        logger.info(
            f"MemoryOS [QUERY]: {elapsed}ms, {len(results)} local results, "
            f"{live_count} live results"
        )
        self._remember("assistant", response, "query")
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
        self._remember("user", user_message, "action")
        context = self._context_block(limit=14, max_chars=6500)
        contextual_goal = (
            "Use the recent MemoryOS context to resolve pronouns and follow-up "
            "requests. If the latest request says save/run/alter 'it' or 'the "
            "program', use the most recent code or artifact from context.\n\n"
            f"Recent MemoryOS context:\n{context}\n\n"
            f"Latest user request:\n{user_message}"
        )
        task = Task(goal=contextual_goal, mode="action")
        queue = get_task_queue()
        queue.enqueue(task)

        executor = self._get_executor()
        result = self._run_contextual_code_followup(user_message, task, executor)
        if result is None:
            result = self._run_coding_action(user_message, task, executor)
        if result is None:
            result = executor.run(task)

        queue.update(task)

        if self.on_task_update:
            self.on_task_update(task)

        # Sanitize: strip hallucinated tool-call syntax from output
        if result:
            result = re.sub(r'functions\.\w+:.*', '', result).strip()
        if not result:
            result = "Completed the requested action."

        self._remember("assistant", result, "action")
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
