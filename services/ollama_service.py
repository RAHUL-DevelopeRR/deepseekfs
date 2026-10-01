"""
Neuron — AI Intelligence Service (Compatibility Shim)
======================================================
This module was previously the Ollama REST API integration.
It is now a thin compatibility wrapper around LLMEngine
(llama-cpp-python direct GGUF inference).

ALL existing UI code continues to work unchanged.

Migration:
- Old: OllamaService → HTTP → Ollama Server → llama.cpp → model
- New: OllamaService → LLMEngine → llama-cpp-python → model (in-process)
"""
from __future__ import annotations

from typing import Optional, Dict

from app.logger import logger


# ── File content extraction (preserved from original) ─────────
def _read_file_content(path: str, max_chars: int = 4000) -> str:
    """Extract text from a file for AI analysis."""
    try:
        from services.document_reader import read_file_content

        return read_file_content(path, max_chars=max_chars)
    except Exception as e:
        logger.warning(f"OllamaService: cannot read {path}: {e}")
        return ""


class OllamaService:
    """Compatibility wrapper — delegates all work to LLMEngine.
    
    Drop-in replacement for the old Ollama REST API-based service.
    All existing UI code calls these same methods without any changes.
    """

    def __init__(self, model: str = ""):
        # model parameter kept for API compatibility but ignored
        # (LLMEngine uses its own model configuration)
        self._engine = None

    def _get_engine(self):
        """Lazy-load the LLM engine."""
        if self._engine is None:
            from services.llm_engine import get_llm_engine
            self._engine = get_llm_engine()
        return self._engine

    # ── Health check ─────────────────────────────────────────
    def is_available(self) -> bool:
        """Check if the AI engine is ready.
        
        Old behavior: checked Ollama REST API
        New behavior: checks if GGUF model is loaded or available
        """
        engine = self._get_engine()
        if engine.is_loaded:
            return True
        # Try to load if not loaded yet
        from services.model_manager import is_llm_model_available
        return is_llm_model_available()

    def _try_auto_start(self) -> bool:
        """Legacy method — no longer needed (no Ollama server to start).
        Kept for compatibility. Now just loads the model."""
        return self.is_available()

    def reset_availability(self):
        """Force re-check on next call."""
        # No-op in new architecture (model state is always known)
        pass

    # ── Pre-warm (load model into RAM) ───────────────────────
    def pre_warm(self):
        """Compatibility hook for old callers.
        
        Old behavior: sent tiny prompt to Ollama to load model
        New behavior: the desktop entry point preloads the local GGUF before
        PyQt starts. Loading llama.cpp later from a background UI-era thread is
        intentionally disabled because it has produced native access violations.
        """
        try:
            engine = self._get_engine()
            if engine.is_loaded:
                logger.info("Encyl: model already loaded by startup preload")
            else:
                logger.info("Encyl: background pre-warm disabled; model loads via startup or first use")
        except Exception as e:
            logger.info(f"Encyl: Pre-warm status check failed: {e}")

    # ── Public API (unchanged signatures) ─────────────────────

    def summarize_file(self, path: str) -> str:
        """Generate a 2-3 line summary of a file's content."""
        return self._get_engine().summarize_file(path)

    def ask_about_files(self, question: str, file_contexts: list[dict]) -> str:
        """Answer a natural language question using file context."""
        return self._get_engine().ask_about_files(question, file_contexts)

    def suggest_tags(self, path: str) -> list[str]:
        """Auto-generate tags for a file."""
        return self._get_engine().suggest_tags(path)

    @property
    def cache_size(self) -> int:
        return self._get_engine().cache_size


# ── Singleton ────────────────────────────────────────────────
_instance: Optional[OllamaService] = None

def get_ollama() -> OllamaService:
    global _instance
    if _instance is None:
        _instance = OllamaService()
    return _instance
