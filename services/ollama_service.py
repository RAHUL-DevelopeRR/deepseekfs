"""
Neuron — Ollama AI Intelligence Service
========================================
Local LLM integration for file summaries, Q&A, and smart actions.
Uses Ollama's REST API (http://localhost:11434).

Architecture:
- Semantic search uses all-MiniLM-L6-v2 (80MB, loaded in RAM at startup)
- Encyl uses llama3.2:3b via Ollama (~2GB, loaded on first request)
- Summary cache avoids re-processing the same file
"""
from __future__ import annotations

import json, time, os, hashlib, threading
from pathlib import Path
from typing import Optional, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError

from app.logger import logger

OLLAMA_URL = "http://localhost:11434"
MODEL      = "llama3.2:1b"
TIMEOUT    = 120  # seconds (first call has cold-start penalty)

# ── File content extraction (reuse existing parser) ──────────
def _read_file_content(path: str, max_chars: int = 4000) -> str:
    """Extract text from a file for AI analysis."""
    ext = Path(path).suffix.lower()
    text = ""
    try:
        if ext in {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
                   ".rs", ".go", ".java", ".cpp", ".c", ".h", ".cs",
                   ".rb", ".php", ".html", ".css", ".json", ".xml",
                   ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log",
                   ".env", ".sh", ".bat", ".csv", ".sql"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(max_chars)
        elif ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(path)
                for page in doc:
                    text += page.get_text()
                    if len(text) > max_chars: break
                doc.close()
            except Exception:
                pass
        elif ext in {".docx", ".doc"}:
            try:
                from docx import Document
                doc = Document(path)
                text = "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                pass
        elif ext in {".pptx"}:
            try:
                from pptx import Presentation
                prs = Presentation(path)
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            text += shape.text + "\n"
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"OllamaService: cannot read {path}: {e}")

    return text[:max_chars].strip()


class OllamaService:
    """Interface to local Ollama LLM for file intelligence.

    Latency optimization:
    - Summary cache: SHA256(path + mtime) → cached summary (no re-processing)
    - Pre-warm: Sends a tiny prompt on startup to load model into RAM
    - Keep-alive: Ollama keeps model in RAM for 5 min after last request
    """

    def __init__(self, model: str = MODEL):
        self._model = model
        self._available: Optional[bool] = None
        self._summary_cache: Dict[str, str] = {}  # hash → summary
        self._warmed = False

    # ── Health check ─────────────────────────────────────────
    def is_available(self) -> bool:
        """Check if Ollama server is running and model exists.
        Auto-starts 'ollama serve' if not running."""
        if self._available is not None:
            return self._available
        try:
            req = Request(f"{OLLAMA_URL}/api/tags", method="GET")
            resp = urlopen(req, timeout=3)
            data = json.loads(resp.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            self._available = any(self._model in m for m in models)
            if not self._available:
                logger.info(f"OllamaService: model '{self._model}' not found. Available: {models}")
            return self._available
        except Exception as e:
            logger.info(f"OllamaService: Ollama not reachable: {e} — attempting auto-start…")
            # ── Try to auto-start ollama serve ──
            if self._try_auto_start():
                return self._available
            self._available = False
            return False

    def _try_auto_start(self) -> bool:
        """Attempt to start 'ollama serve' automatically."""
        import subprocess as _sp, shutil
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            # Check common install paths on Windows
            for candidate in [
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
                r"C:\Program Files\Ollama\ollama.exe",
                r"C:\Program Files (x86)\Ollama\ollama.exe",
            ]:
                if os.path.isfile(candidate):
                    ollama_path = candidate
                    break
        if not ollama_path:
            logger.info("OllamaService: ollama binary not found on system")
            return False
        try:
            logger.info(f"OllamaService: auto-starting ollama serve via {ollama_path}")
            _sp.Popen(
                [ollama_path, "serve"],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                creationflags=_sp.CREATE_NO_WINDOW if hasattr(_sp, 'CREATE_NO_WINDOW') else 0,
            )
            # Wait for server to come up  (poll up to 15 seconds)
            for attempt in range(30):
                time.sleep(0.5)
                try:
                    req = Request(f"{OLLAMA_URL}/api/tags", method="GET")
                    resp = urlopen(req, timeout=2)
                    data = json.loads(resp.read())
                    models = [m.get("name", "") for m in data.get("models", [])]
                    self._available = any(self._model in m for m in models)
                    if self._available:
                        logger.info(f"OllamaService: auto-started successfully — model ready")
                    else:
                        logger.info(f"OllamaService: server up but model '{self._model}' not found. Available: {models}")
                    return self._available
                except Exception:
                    continue
            logger.warning("OllamaService: auto-start timed out after 15s")
            self._available = False
            return False
        except Exception as ex:
            logger.warning(f"OllamaService: auto-start failed: {ex}")
            self._available = False
            return False

    def reset_availability(self):
        """Force re-check on next call."""
        self._available = None

    # ── Pre-warm (load model into RAM) ───────────────────────
    def pre_warm(self):
        """Send a tiny request to load the model into GPU/RAM.
        Call this on app startup in a background thread.
        After this, subsequent requests are 3-5x faster."""
        if self._warmed:
            return
        def _warm():
            try:
                if not self.is_available():
                    return
                logger.info("Encyl: Pre-warming model (loading into RAM)...")
                t0 = time.time()
                self._generate("Say 'ready' in one word.", max_tokens=5)
                elapsed = time.time() - t0
                self._warmed = True
                logger.info(f"Encyl: Model warm — loaded in {elapsed:.1f}s")
            except Exception as e:
                logger.info(f"Encyl: Pre-warm failed: {e}")
        threading.Thread(target=_warm, daemon=True).start()

    # ── Cache key ────────────────────────────────────────────
    @staticmethod
    def _cache_key(path: str) -> str:
        """Hash path + modification time for cache lookup."""
        try:
            mtime = os.path.getmtime(path)
            raw = f"{path}|{mtime}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]
        except Exception:
            return ""

    # ── Core LLM call ────────────────────────────────────────
    def _generate(self, prompt: str, system: str = "", max_tokens: int = 300) -> str:
        """Send prompt to Ollama and return response text."""
        if not self.is_available():
            return ""
        try:
            payload = json.dumps({
                "model": self._model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.3,
                }
            }).encode("utf-8")

            req = Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urlopen(req, timeout=TIMEOUT)
            data = json.loads(resp.read())
            return data.get("response", "").strip()
        except Exception as e:
            logger.warning(f"OllamaService generate error: {e}")
            return ""

    # ── Public API ───────────────────────────────────────────

    def summarize_file(self, path: str) -> str:
        """Generate a 2-3 line summary of a file's content.
        Uses cache — same file (unchanged) returns instantly."""
        # Check cache first
        key = self._cache_key(path)
        if key and key in self._summary_cache:
            logger.info(f"Encyl: Cache hit for {Path(path).name}")
            return self._summary_cache[key]

        content = _read_file_content(path, max_chars=3000)
        if not content:
            return "Could not read file content."

        name = Path(path).name
        ext = Path(path).suffix.lower()
        prompt = f"""Summarize this file in 2-3 concise sentences.

File: {name}
Type: {ext}

Content:
{content}"""

        system = (
            "You are a file intelligence assistant. "
            "Give concise, useful summaries. "
            "Focus on what the file IS and what it CONTAINS. "
            "Do not say 'this file contains' — just describe the content directly."
        )
        result = self._generate(prompt, system, max_tokens=150)
        summary = result or "AI summary unavailable."

        # Cache the result
        if key and result:
            self._summary_cache[key] = summary
            logger.info(f"Encyl: Cached summary for {name} (key={key})")

        return summary

    def ask_about_files(self, question: str, file_contexts: list[dict]) -> str:
        """Answer a natural language question using file context from search results."""
        # Build context from top search results
        context_parts = []
        for i, f in enumerate(file_contexts[:5]):  # top 5 files
            path = f.get("path", "")
            name = f.get("name", Path(path).name)
            content = _read_file_content(path, max_chars=1500)
            if content:
                context_parts.append(f"--- File {i+1}: {name} ---\n{content[:1500]}")

        if not context_parts:
            return "No readable files found to answer your question."

        context = "\n\n".join(context_parts)
        prompt = f"""Based on the following files from the user's computer, answer their question.

Question: {question}

Files:
{context}

Answer concisely and reference specific file names when relevant."""

        system = (
            "You are Neuron AI, a local file intelligence assistant. "
            "Answer questions about the user's files based on the provided content. "
            "Be specific — mention file names and quote relevant parts. "
            "If you can't answer from the files, say so honestly."
        )
        return self._generate(prompt, system, max_tokens=400) or "AI could not generate a response."

    def suggest_tags(self, path: str) -> list[str]:
        """Auto-generate tags for a file."""
        content = _read_file_content(path, max_chars=2000)
        if not content:
            return []

        name = Path(path).name
        prompt = f"""Generate 3-5 short tags/categories for this file. Return ONLY comma-separated tags, nothing else.

File: {name}
Content:
{content[:2000]}"""

        system = "Return only comma-separated tags. Example: python, machine-learning, tutorial, data-science"
        result = self._generate(prompt, system, max_tokens=50)
        if result:
            return [t.strip().lower() for t in result.split(",") if t.strip()][:5]
        return []

    @property
    def cache_size(self) -> int:
        return len(self._summary_cache)


# ── Singleton ────────────────────────────────────────────────
_instance: Optional[OllamaService] = None

def get_ollama() -> OllamaService:
    global _instance
    if _instance is None:
        _instance = OllamaService()
    return _instance
