"""Offline Qwen Coder engine for code/file-operation planning."""
from __future__ import annotations

import os
import threading
from typing import Optional

import services.jinja2_patches  # noqa: F401
from app.logger import logger

DEFAULT_N_CTX = 4096


class CoderEngine:
    """Small llama.cpp-backed Qwen 2.5 Coder runtime."""

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = DEFAULT_N_CTX):
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._model = None
        self._lock = threading.Lock()
        self._load_error: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def load_model(self) -> bool:
        if self._model is not None:
            return True

        with self._lock:
            if self._model is not None:
                return True
            try:
                if self._model_path is None:
                    from services.model_manager import get_coder_model_path

                    model_path = get_coder_model_path()
                    if model_path is None:
                        raise FileNotFoundError("Qwen Coder model is not downloaded")
                    self._model_path = str(model_path)

                from llama_cpp import Llama

                n_threads = max(1, (os.cpu_count() or 4) // 2)
                self._model = Llama(
                    model_path=self._model_path,
                    n_ctx=self._n_ctx,
                    n_batch=256,
                    n_threads=n_threads,
                    n_gpu_layers=0,
                    verbose=False,
                    use_mmap=False,
                    use_mlock=False,
                )
                return True
            except Exception as exc:
                self._load_error = str(exc)
                logger.warning(f"CoderEngine: load failed: {exc}")
                return False

    def complete(self, prompt: str, max_tokens: int = 160) -> str:
        if not self.load_model():
            raise RuntimeError(self._load_error or "Coder model failed to load")

        with self._lock:
            result = self._model.create_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Qwen Coder running offline. Return concise, "
                            "structured answers for code and file-operation planning."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
        return result["choices"][0]["message"]["content"].strip()


_instance: Optional[CoderEngine] = None


def get_coder_engine() -> CoderEngine:
    global _instance
    if _instance is None:
        _instance = CoderEngine()
    return _instance
