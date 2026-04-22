"""
Neuron — Local LLM Engine (llama-cpp-python)
=============================================
Direct in-process GGUF model inference.
NO Ollama. NO server. NO network exposure.

Architecture:
- Uses llama-cpp-python to load SmolLM3-3B Q4_K_M GGUF
- Model loaded once, kept in RAM for session lifetime
- Thread-safe with lock (single inference at a time)
- Lazy loading: model loaded on first inference call
- SHA256 summary cache preserved from ollama_service.py

Replaces: services/ollama_service.py's dependency on Ollama REST API
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Iterator, List

# MUST be imported before llama_cpp — patches Jinja2 for SmolLM3 compatibility
import services.jinja2_patches  # noqa: F401

from app.logger import logger


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from model output.
    
    Handles three cases:
      1. Closed:   <think>...</think>  (normal)
      2. Unclosed: <think>... (model ran out of tokens)
      3. All-think: entire output is inside think tags
    """
    if not text:
        return text
    # 1) Remove closed <think>...</think> blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 2) Remove unclosed <think> to end-of-string (model ran out of tokens)
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    # 3) If everything was thinking, return a polite fallback
    return cleaned if cleaned else "I'm here to help. What would you like to do?"

# ── Configuration ─────────────────────────────────────────────
DEFAULT_N_CTX = 4096        # Context window (tokens)
DEFAULT_N_THREADS = 0       # 0 = auto-detect CPU cores
DEFAULT_TEMPERATURE = 0.3   # Low temp for consistent outputs
DEFAULT_MAX_TOKENS = 512    # Default generation length

# ── System Prompts ────────────────────────────────────────────
SYSTEM_SUMMARIZE = (
    "You are a file intelligence assistant. "
    "Give concise, useful summaries. "
    "Focus on what the file IS and what it CONTAINS. "
    "Do not say 'this file contains' — just describe the content directly."
)

SYSTEM_QA = (
    "You are Neuron AI, a local file intelligence assistant. "
    "Answer questions about the user's files based on the provided content. "
    "Be specific — mention file names and quote relevant parts. "
    "If you can't answer from the files, say so honestly."
)

SYSTEM_CHAT = (
    "You are Neuron MemoryOS, an intelligent local AI assistant. "
    "You help the user manage files, create content, search their computer, "
    "and automate tasks. You have access to tools for file operations, "
    "folder management, shell commands, and code execution. "
    "Be helpful, precise, and proactive. When the user asks you to do something, "
    "use the appropriate tool. Always confirm destructive operations before executing."
)

SYSTEM_AGENT = (
    "You are Neuron MemoryOS, a local AI assistant with file and system tools.\n"
    "You have access to these tools:\n"
    "{tool_descriptions}\n\n"
    "## How to use tools\n"
    "When you need a tool, respond with ONLY a JSON block:\n"
    '```json\n{{"tool": "tool_name", "args": {{"param": "value"}}}}\n```\n\n'
    "## When NOT to use tools\n"
    "For greetings, questions about yourself, general knowledge, or conversation "
    "— just respond directly in plain text. No tool call needed.\n\n"
    "## Examples\n"
    'User: "Hello!"\n'
    "Response: Hi! I'm MemoryOS. I can help you manage files, run commands, and automate tasks.\n\n"
    'User: "List my Downloads folder"\n'
    "Response:\n"
    '```json\n{{"tool": "folder_list", "args": {{"path": "C:/Users/rahul/Downloads"}}}}\n```\n\n'
    'User: "What can you do?"\n'
    "Response: I can search files, organize folders, create documents, run shell commands, and more.\n\n"
    "## Rules\n"
    "- Use REAL Windows paths (C:/Users/...), never /path/to/...\n"
    "- ONE tool per response. Wait for results before the next.\n"
    "- If a tool fails, try a different approach.\n"
    "- Think step by step for complex tasks.\n"
)


class LLMEngine:
    """Direct GGUF model inference via llama-cpp-python.
    
    Thread-safe singleton — one model in memory shared across 
    the entire application (UI, MemoryOS, Overlay).
    """
    
    def __init__(self, model_path: Optional[str] = None, n_ctx: int = DEFAULT_N_CTX):
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._model = None  # Llama instance (lazy loaded)
        self._lock = threading.Lock()
        self._loaded = False
        self._loading = False
        self._summary_cache: Dict[str, str] = {}
        self._load_error: Optional[str] = None
    
    @property
    def is_loaded(self) -> bool:
        """True if model is loaded and ready for inference."""
        return self._loaded and self._model is not None
    
    @property
    def load_error(self) -> Optional[str]:
        """Error message if model failed to load, else None."""
        return self._load_error
    
    def load_model(self, progress_cb=None) -> bool:
        """Load the GGUF model into RAM.
        
        Thread-safe — only one load at a time.
        Returns True if model loaded successfully.
        """
        if self._loaded:
            return True
        
        with self._lock:
            if self._loaded:  # double-check after acquiring lock
                return True
            if self._loading:
                return False
            self._loading = True
        
        try:
            # Resolve model path
            if self._model_path is None:
                from services.model_manager import get_llm_model_path, download_llm_model
                
                model_path = get_llm_model_path()
                if model_path is None:
                    logger.info("LLMEngine: Model not found, downloading...")
                    if progress_cb:
                        progress_cb(0.0, "Downloading AI model...")
                    model_path = download_llm_model(progress_cb)
                
                self._model_path = str(model_path)
            
            if not os.path.isfile(self._model_path):
                raise FileNotFoundError(f"Model file not found: {self._model_path}")
            
            # Load model 
            logger.info(f"LLMEngine: Loading model from {self._model_path}...")
            t0 = time.time()
            
            from llama_cpp import Llama
            
            # Auto-detect thread count
            n_threads = DEFAULT_N_THREADS
            if n_threads == 0:
                n_threads = max(1, (os.cpu_count() or 4) // 2)
            
            # Verify file isn't empty/corrupted
            file_size = os.path.getsize(self._model_path)
            if file_size < 1024 * 1024:  # Less than 1MB = corrupted
                raise ValueError(f"Model file too small ({file_size} bytes), likely corrupted.")
            
            logger.info(f"LLMEngine: File size={file_size/(1024*1024):.0f}MB, threads={n_threads}")
            
            # Performance optimizations:
            #   flash_attn  = faster attention computation
            #   type_k/v    = KV cache quantization (50% memory savings)
            #   n_batch=512 = faster prompt processing
            #   chat_format = native function calling (like GPT/Claude)
            load_kwargs = dict(
                model_path=self._model_path,
                n_batch=512,
                n_threads=n_threads,
                n_gpu_layers=0,
                verbose=False,
                use_mmap=False,
                use_mlock=False,
                flash_attn=True,
                type_k=1,     # q8_0 KV cache (key)
                type_v=1,     # q8_0 KV cache (value)
                chat_format="chatml-function-calling",
            )
            
            # First attempt with 2048 context
            try:
                self._model = Llama(n_ctx=min(self._n_ctx, 2048), **load_kwargs)
            except Exception as e1:
                logger.warning(f"LLMEngine: First load failed: {e1}, trying fallback...")
                load_kwargs["n_batch"] = 128
                load_kwargs["n_threads"] = max(1, n_threads // 2)
                self._model = Llama(n_ctx=512, **load_kwargs)
            
            elapsed = time.time() - t0
            size_mb = file_size / (1024 * 1024)
            logger.info(
                f"LLMEngine: Model loaded in {elapsed:.1f}s "
                f"({size_mb:.0f}MB, ctx={self._model.n_ctx()}, threads={n_threads})"
            )
            
            self._loaded = True
            self._load_error = None
            return True
            
        except ImportError:
            self._load_error = (
                "llama-cpp-python is not installed. "
                "Install it with: pip install llama-cpp-python"
            )
            logger.error(f"LLMEngine: {self._load_error}")
            return False
            
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"LLMEngine: Failed to load model: {e}")
            return False
            
        finally:
            self._loading = False
    
    def unload(self):
        """Release the model from memory."""
        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
            self._loaded = False
            logger.info("LLMEngine: Model unloaded")
    
    # ── Core Generation ───────────────────────────────────────
    
    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Generate a response from the LLM.
        
        Thread-safe — blocks if another generation is in progress.
        Auto-loads model on first call.
        """
        if not self._loaded:
            if not self.load_model():
                return f"[AI unavailable: {self._load_error or 'model not loaded'}]"
        
        with self._lock:
            try:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                response = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop or [],
                )
                
                content = response["choices"][0]["message"]["content"]
                return _strip_thinking(content.strip()) if content else ""
                
            except Exception as e:
                logger.error(f"LLMEngine: Generation error: {e}")
                return f"[AI error: {e}]"
    
    def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> Iterator[str]:
        """Stream tokens from the LLM one at a time.
        
        Yields individual tokens as they are generated.
        Used for real-time display in overlay/chat.
        """
        if not self._loaded:
            if not self.load_model():
                yield f"[AI unavailable: {self._load_error or 'model not loaded'}]"
                return
        
        with self._lock:
            try:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                stream = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )
                
                for chunk in stream:
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                        
            except Exception as e:
                logger.error(f"LLMEngine: Stream error: {e}")
                yield f"\n[AI error: {e}]"
    
    def chat(
        self,
        messages: List[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        tools_description: str = "",
    ) -> str:
        """Multi-turn chat with conversation history.
        
        messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
        """
        if not self._loaded:
            if not self.load_model():
                return f"[AI unavailable: {self._load_error or 'model not loaded'}]"
        
        with self._lock:
            try:
                # Pass messages through as-is — caller manages context
                response = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                content = response["choices"][0]["message"]["content"]
                return _strip_thinking(content.strip()) if content else ""
                
            except Exception as e:
                logger.error(f"LLMEngine: Chat error: {e}")
                return f"[AI error: {e}]"
    
    def chat_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> dict:
        """Native function calling — same API as GPT/Claude.
        
        Returns the full message dict which may contain:
          - "content": text response (if no tool call)
          - "tool_calls": [{"function": {"name": ..., "arguments": ...}}]
        
        The model autonomously decides whether to call a tool or respond.
        No system prompt hacks, no regex parsing.
        """
        if not self._loaded:
            if not self.load_model():
                return {"content": f"[AI unavailable: {self._load_error}]"}
        
        with self._lock:
            try:
                response = self._model.create_chat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                msg = response["choices"][0]["message"]
                
                # Strip thinking from content if present
                if msg.get("content"):
                    msg["content"] = _strip_thinking(msg["content"].strip())
                
                return msg
                
            except Exception as e:
                logger.error(f"LLMEngine: Tool call error: {e}")
                return {"content": f"[AI error: {e}]"}
    
    # ── High-Level API (compatible with OllamaService) ─────────
    
    @staticmethod
    def _cache_key(path: str) -> str:
        """Hash path + modification time for cache lookup."""
        try:
            mtime = os.path.getmtime(path)
            raw = f"{path}|{mtime}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]
        except Exception:
            return ""
    
    def summarize_file(self, path: str) -> str:
        """Generate a 2-3 line summary of a file's content.
        Uses cache — same file (unchanged) returns instantly.
        """
        key = self._cache_key(path)
        if key and key in self._summary_cache:
            logger.info(f"LLMEngine: Cache hit for {Path(path).name}")
            return self._summary_cache[key]
        
        # Reuse the file reader from ollama_service
        from services.ollama_service import _read_file_content
        content = _read_file_content(path, max_chars=3000)
        if not content:
            return "Could not read file content."
        
        name = Path(path).name
        ext = Path(path).suffix.lower()
        prompt = f"Summarize this file in 2-3 concise sentences.\n\nFile: {name}\nType: {ext}\n\nContent:\n{content}"
        
        result = self.generate(prompt, SYSTEM_SUMMARIZE, max_tokens=150)
        summary = result if result and not result.startswith("[AI") else "AI summary unavailable."
        
        if key and not result.startswith("[AI"):
            self._summary_cache[key] = summary
            logger.info(f"LLMEngine: Cached summary for {name} (key={key})")
        
        return summary
    
    def ask_about_files(self, question: str, file_contexts: list[dict]) -> str:
        """Answer a question using file context from search results."""
        from services.ollama_service import _read_file_content
        
        context_parts = []
        for i, f in enumerate(file_contexts[:5]):
            path = f.get("path", "")
            name = f.get("name", Path(path).name)
            content = _read_file_content(path, max_chars=1500)
            if content:
                context_parts.append(f"--- File {i+1}: {name} ---\n{content[:1500]}")
        
        if not context_parts:
            return "No readable files found to answer your question."
        
        context = "\n\n".join(context_parts)
        prompt = (
            f"Based on the following files from the user's computer, answer their question.\n\n"
            f"Question: {question}\n\nFiles:\n{context}\n\n"
            f"Answer concisely and reference specific file names when relevant."
        )
        
        result = self.generate(prompt, SYSTEM_QA, max_tokens=400)
        return result if result and not result.startswith("[AI") else "AI could not generate a response."
    
    def suggest_tags(self, path: str) -> list[str]:
        """Auto-generate tags for a file."""
        from services.ollama_service import _read_file_content
        
        content = _read_file_content(path, max_chars=2000)
        if not content:
            return []
        
        name = Path(path).name
        prompt = (
            f"Generate 3-5 short tags/categories for this file. "
            f"Return ONLY comma-separated tags, nothing else.\n\n"
            f"File: {name}\nContent:\n{content[:2000]}"
        )
        system = "Return only comma-separated tags. Example: python, machine-learning, tutorial, data-science"
        result = self.generate(prompt, system, max_tokens=50)
        if result and not result.startswith("[AI"):
            return [t.strip().lower() for t in result.split(",") if t.strip()][:5]
        return []
    
    @property
    def cache_size(self) -> int:
        return len(self._summary_cache)


# ── Singleton ────────────────────────────────────────────────
_engine: Optional[LLMEngine] = None
_engine_lock = threading.Lock()

def get_llm_engine() -> LLMEngine:
    """Get the global LLM engine singleton."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = LLMEngine()
    return _engine
