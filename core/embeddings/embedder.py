"""Sentence Transformer wrapper for embeddings.

Loads the bundled/local all-MiniLM-L6-v2 model first, then falls back to an
online load. If both fail, indexing/search continue with a deterministic
lexical fallback instead of crashing the desktop app.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Union

import numpy as np

import app.config as config
from app.logger import logger


# Force CPU-only mode and avoid common OpenMP duplicate DLL crashes on Windows.
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


def _find_local_model() -> str | None:
    """Return a usable local model directory when one is bundled or cached."""
    candidates = [
        config.STORAGE_DIR / "models" / config.MODEL_NAME,
        config.BASE_DIR / "storage" / "models" / config.MODEL_NAME,
        Path.home() / ".cache" / "huggingface" / "hub",
    ]

    for path in candidates:
        try:
            if not path.is_dir() or not any(path.iterdir()):
                continue
            if (path / "config.json").exists() or (path / "modules.json").exists():
                logger.info(f"Local embedding model found at: {path}")
                return str(path)
        except Exception:
            continue

    return None


class _FallbackEmbedder:
    """Small deterministic fallback when MiniLM cannot be loaded.

    Search quality is lower than transformer embeddings, but the app can still
    index files and return useful lexical matches instead of failing at startup.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def encode(self, texts: List[str]) -> np.ndarray:
        rows = []
        for text in texts:
            tokens = str(text).lower().split()
            vec = np.zeros(self.dim, dtype=np.float32)
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest, "little") % self.dim
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            rows.append(vec)
        return np.vstack(rows) if rows else np.empty((0, self.dim), dtype=np.float32)


class Embedder:
    """Generate embeddings using sentence-transformers, with a safe fallback."""

    def __init__(self, model_name: str = config.MODEL_NAME):
        self.model_name = model_name
        self.model = None
        self._fallback = _FallbackEmbedder(config.EMBEDDING_DIM)

        logger.info(f"Loading embedding model: {model_name}")

        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            logger.error(f"sentence-transformers import failed; using fallback: {exc}")
            return

        local_path = _find_local_model()
        sources = [local_path] if local_path else []
        sources.append(model_name)

        for source in sources:
            if not source:
                continue
            try:
                self.model = SentenceTransformer(source, device="cpu")
                logger.info(
                    "Embedding model ready from %s. Dimension: %s",
                    source,
                    self.model.get_sentence_embedding_dimension(),
                )
                return
            except Exception as exc:
                logger.warning(f"Could not load embedding model from {source}: {exc}")

        logger.warning(
            "Fallback embedder active (dim=%s). Search quality is reduced.",
            config.EMBEDDING_DIM,
        )

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Generate embeddings for one or more text strings."""
        if isinstance(texts, str):
            texts = [texts]

        if self.model is None:
            return self._fallback.encode(texts)

        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=True,
        )

    def encode_single(self, text: str) -> np.ndarray:
        """Generate an embedding for a single text string."""
        return self.encode([text])[0]


_embedder_instance: Embedder | None = None


def get_embedder() -> Embedder:
    """Get or create the process-wide embedder singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
