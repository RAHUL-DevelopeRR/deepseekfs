"""Backward-compatibility shim — redirects to the unified LLM engine.

The separate Qwen 0.5B coder model has been replaced by a single
Qwen 2.5 Coder 3B Instruct that handles both general chat AND code.
This module is kept so that ``scripts/manual_smoke/qwen_coder_smoke.py``
and any future callers of ``get_coder_engine()`` continue to work.
"""
from __future__ import annotations

from typing import Optional

from app.logger import logger


class CoderEngine:
    """Thin wrapper around LLMEngine for code-specific completions."""

    def __init__(self):
        self._engine = None

    def _ensure_engine(self):
        if self._engine is None:
            from services.llm_engine import get_llm_engine
            self._engine = get_llm_engine()

    @property
    def is_loaded(self) -> bool:
        self._ensure_engine()
        return self._engine.is_loaded

    @property
    def load_error(self) -> Optional[str]:
        self._ensure_engine()
        return self._engine.load_error

    def complete(self, prompt: str, max_tokens: int = 160) -> str:
        """Generate a code/structured completion using the unified model."""
        self._ensure_engine()
        return self._engine.generate(
            prompt,
            system=(
                "You are Qwen Coder running offline. Return concise, "
                "structured answers for code and file-operation planning."
            ),
            max_tokens=max_tokens,
            temperature=0.2,
        )


_instance: Optional[CoderEngine] = None


def get_coder_engine() -> CoderEngine:
    global _instance
    if _instance is None:
        _instance = CoderEngine()
    return _instance
