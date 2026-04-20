"""Sentence Transformer wrapper for embeddings (ONNX Runtime).

Uses ONNX Runtime for inference — no PyTorch dependency at runtime.
Same MiniLM model, same 384-dim embeddings, same search quality.
Falls back to a deterministic lexical embedder if ONNX model is missing.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Union

import numpy as np

import app.config as config
from app.logger import logger


# Suppress unnecessary warnings on Windows.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def _find_onnx_model() -> Path | None:
    """Locate the ONNX model directory (must contain model.onnx + tokenizer.json)."""
    candidates = [
        config.STORAGE_DIR / "models" / "onnx",
        config.BASE_DIR / "storage" / "models" / "onnx",
    ]
    for p in candidates:
        try:
            if p.is_dir() and (p / "model.onnx").exists() and (p / "tokenizer.json").exists():
                logger.info(f"ONNX model found at: {p}")
                return p
        except Exception:
            continue
    return None


def _find_local_model() -> str | None:
    """Return a usable local sentence-transformers model directory."""
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
    """Deterministic fallback when neither ONNX nor torch model is available."""

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


class _OnnxEmbedder:
    """ONNX Runtime-based embedder — same quality as sentence-transformers."""

    def __init__(self, model_dir: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.session = ort.InferenceSession(str(model_dir / "model.onnx"))
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=128)
        self.input_names = [i.name for i in self.session.get_inputs()]
        self.dim = 384  # MiniLM output dimension

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            encodings = self.tokenizer.encode_batch(batch)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
            if "token_type_ids" in self.input_names:
                feeds["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)

            outputs = self.session.run(None, feeds)
            hidden = outputs[0]  # (batch, seq, 384)

            # Mean pooling (same as sentence-transformers)
            mask_exp = attention_mask[:, :, np.newaxis].astype(np.float32)
            pooled = np.sum(hidden * mask_exp, axis=1) / np.clip(
                mask_exp.sum(axis=1), 1e-9, None
            )

            # L2 normalize
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / norms

            all_vecs.append(pooled)

        return np.vstack(all_vecs) if all_vecs else np.empty((0, self.dim), dtype=np.float32)


class Embedder:
    """Generate embeddings using ONNX, torch, or fallback — in that priority order."""

    def __init__(self, model_name: str = config.MODEL_NAME):
        self.model_name = model_name
        self.model = None  # Set to non-None when neural model loads
        self._backend = None  # _OnnxEmbedder, SentenceTransformer, or None
        self._fallback = _FallbackEmbedder(config.EMBEDDING_DIM)

        logger.info(f"Loading embedding model: {model_name}")

        # ── Priority 1: ONNX Runtime (lightweight, PyInstaller-safe) ──
        onnx_dir = _find_onnx_model()
        if onnx_dir:
            try:
                self._backend = _OnnxEmbedder(onnx_dir)
                self.model = self._backend  # Mark as neural
                logger.info(
                    "ONNX embedder ready (dim=%s). No torch needed.",
                    self._backend.dim,
                )
                return
            except Exception as exc:
                logger.warning(f"ONNX load failed: {exc}")

        # ── Priority 2: sentence-transformers + torch ──
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            logger.warning(f"sentence-transformers unavailable: {exc}")
            logger.warning(
                "Fallback embedder active (dim=%s). Search quality is reduced.",
                config.EMBEDDING_DIM,
            )
            return

        local_path = _find_local_model()
        sources = [local_path] if local_path else []
        sources.append(model_name)

        for source in sources:
            if not source:
                continue
            try:
                self._backend = SentenceTransformer(source, device="cpu")
                self.model = self._backend
                logger.info(
                    "Torch embedder ready from %s. Dimension: %s",
                    source,
                    self._backend.get_sentence_embedding_dimension(),
                )
                return
            except Exception as exc:
                logger.warning(f"Could not load from {source}: {exc}")

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

        if isinstance(self._backend, _OnnxEmbedder):
            return self._backend.encode(texts, batch_size=batch_size)

        # sentence-transformers path
        return self._backend.encode(
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
