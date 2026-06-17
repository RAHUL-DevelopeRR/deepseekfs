"""Embedding model wrapper for Neuron semantic search.

Primary model: BAAI/bge-small-en-v1.5.

BGE Small improves semantic retrieval over the old all-MiniLM-L6-v2 baseline
while preserving the 384-dimensional vector footprint, so the FAISS/HNSW index
stays compact. The legacy ONNX MiniLM model can still be used explicitly as a
compatibility fallback by setting NEURON_ALLOW_LEGACY_MINILM_FALLBACK=1.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List, Union

import numpy as np

import app.config as config
from app.logger import logger


os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")


def _model_leaf() -> str:
    parts = [part for part in config.MODEL_NAME.replace("\\", "/").split("/") if part]
    return parts[-1] if parts else config.MODEL_NAME


def _find_legacy_onnx_model() -> Path | None:
    if "minilm" not in config.MODEL_NAME.lower() and os.getenv("NEURON_ALLOW_LEGACY_MINILM_FALLBACK", "0") != "1":
        return None

    candidates = [
        config.STORAGE_DIR / "models" / "onnx",
        config.BASE_DIR / "storage" / "models" / "onnx",
    ]
    for path in candidates:
        try:
            if path.is_dir() and (path / "model.onnx").exists() and (path / "tokenizer.json").exists():
                logger.info("Legacy ONNX embedding model found at: %s", path)
                return path
        except Exception:
            continue
    return None


def _find_bge_onnx_model() -> tuple[Path, Path] | None:
    """Locate the bundled BGE ONNX model and tokenizer directory."""
    if "bge" not in config.MODEL_NAME.lower():
        return None

    leaf = _model_leaf()
    env_dir = os.getenv("NEURON_BGE_ONNX_DIR") or os.getenv("NEURON_EMBEDDING_ONNX_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            config.STORAGE_DIR / "models" / config.MODEL_NAME,
            config.STORAGE_DIR / "models" / leaf,
            config.BASE_DIR / "storage" / "models" / config.MODEL_NAME,
            config.BASE_DIR / "storage" / "models" / leaf,
            config.RUNTIME_DIR / "storage" / "models" / config.MODEL_NAME,
            config.RUNTIME_DIR / "storage" / "models" / leaf,
        ]
    )

    prefer_quantized = os.getenv("NEURON_EMBEDDING_ONNX_QUANTIZED", "0").lower() in {"1", "true", "yes"}
    names = ["model_quantized.onnx", "model.onnx"] if prefer_quantized else ["model.onnx", "model_quantized.onnx"]
    for model_dir in candidates:
        try:
            if not model_dir.is_dir() or not (model_dir / "tokenizer.json").exists():
                continue
            for name in names:
                for model_path in [model_dir / "onnx" / name, model_dir / name]:
                    if model_path.exists():
                        logger.info("Bundled BGE ONNX model found at: %s", model_path)
                        return model_path, model_dir
        except Exception:
            continue
    return None


def _find_local_sentence_transformer() -> str | None:
    leaf = _model_leaf()
    candidates = [
        config.STORAGE_DIR / "models" / config.MODEL_NAME,
        config.STORAGE_DIR / "models" / leaf,
        config.BASE_DIR / "storage" / "models" / config.MODEL_NAME,
        config.BASE_DIR / "storage" / "models" / leaf,
        Path.home() / ".cache" / "huggingface" / "hub",
    ]
    for path in candidates:
        try:
            if not path.is_dir() or not any(path.iterdir()):
                continue
            if (path / "config.json").exists() or (path / "modules.json").exists():
                logger.info("Local embedding model found at: %s", path)
                return str(path)
        except Exception:
            continue
    return None


class _FallbackEmbedder:
    """Deterministic lexical fallback when neural embeddings are unavailable."""

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


class _OnnxMiniLmEmbedder:
    """Legacy ONNX Runtime MiniLM embedder."""

    def __init__(self, model_dir: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.session = ort.InferenceSession(str(model_dir / "model.onnx"))
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=128)
        self.input_names = [i.name for i in self.session.get_inputs()]
        self.dim = 384

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
            hidden = outputs[0]
            mask_exp = attention_mask[:, :, np.newaxis].astype(np.float32)
            pooled = np.sum(hidden * mask_exp, axis=1) / np.clip(mask_exp.sum(axis=1), 1e-9, None)
            pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
            all_vecs.append(pooled)

        return np.vstack(all_vecs) if all_vecs else np.empty((0, self.dim), dtype=np.float32)


class _OnnxBgeEmbedder:
    """BGE Small ONNX embedder using CLS pooling and L2 normalization."""

    def __init__(self, model_path: Path, tokenizer_dir: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=int(os.getenv("NEURON_EMBEDDING_MAX_TOKENS", "512")))
        self.input_names = [i.name for i in self.session.get_inputs()]
        self.dim = config.EMBEDDING_DIM

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            batch = [str(text) for text in texts[i : i + batch_size]]
            encodings = self.tokenizer.encode_batch(batch)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            feeds = {}
            if "input_ids" in self.input_names:
                feeds["input_ids"] = input_ids
            if "attention_mask" in self.input_names:
                feeds["attention_mask"] = attention_mask
            if "token_type_ids" in self.input_names:
                type_ids = [e.type_ids if e.type_ids else [0] * len(e.ids) for e in encodings]
                feeds["token_type_ids"] = np.array(type_ids, dtype=np.int64)

            output = self.session.run(None, feeds)[0]
            if output.ndim == 3:
                pooled = output[:, 0, :]
            else:
                pooled = output
            pooled = pooled.astype(np.float32, copy=False)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.clip(norms, 1e-9, None)
            all_vecs.append(pooled)

        return np.vstack(all_vecs) if all_vecs else np.empty((0, self.dim), dtype=np.float32)


class Embedder:
    """Generate embeddings using BGE, optional legacy ONNX, or lexical fallback."""

    def __init__(self, model_name: str = config.MODEL_NAME):
        self.model_name = model_name
        self.model = None
        self._backend = None
        self._fallback = _FallbackEmbedder(config.EMBEDDING_DIM)

        logger.info("Loading embedding model: %s", model_name)

        bge_onnx = _find_bge_onnx_model()
        if bge_onnx:
            try:
                model_path, tokenizer_dir = bge_onnx
                self._backend = _OnnxBgeEmbedder(model_path, tokenizer_dir)
                self.model = self._backend
                logger.info("BGE ONNX embedder ready. Dimension: %s", self._backend.dim)
                return
            except Exception as exc:
                logger.warning("Bundled BGE ONNX load failed: %s", exc)

        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            logger.warning("sentence-transformers unavailable: %s", exc)
            self._try_legacy_or_fallback()
            return

        local_path = _find_local_sentence_transformer()
        sources = [local_path] if local_path else []
        sources.append(model_name)

        for source in sources:
            if not source:
                continue
            try:
                self._backend = SentenceTransformer(source, device="cpu")
                self.model = self._backend
                dim = int(self._backend.get_sentence_embedding_dimension())
                if dim != config.EMBEDDING_DIM:
                    logger.warning(
                        "Embedding dimension mismatch: model=%s config=%s. Existing FAISS index may need rebuild.",
                        dim,
                        config.EMBEDDING_DIM,
                    )
                logger.info("Sentence-transformer embedder ready from %s. Dimension: %s", source, dim)
                return
            except Exception as exc:
                logger.warning("Could not load embedding model from %s: %s", source, exc)

        self._try_legacy_or_fallback()

    def _try_legacy_or_fallback(self) -> None:
        onnx_dir = _find_legacy_onnx_model()
        if onnx_dir:
            try:
                self._backend = _OnnxMiniLmEmbedder(onnx_dir)
                self.model = self._backend
                logger.warning(
                    "Legacy MiniLM ONNX fallback active. Install %s for primary BGE search.",
                    config.MODEL_NAME,
                )
                return
            except Exception as exc:
                logger.warning("Legacy ONNX load failed: %s", exc)

        logger.warning("Lexical fallback embedder active (dim=%s). Search quality is reduced.", config.EMBEDDING_DIM)

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]

        if self.model is None:
            return self._fallback.encode(texts)

        if isinstance(self._backend, (_OnnxMiniLmEmbedder, _OnnxBgeEmbedder)):
            return self._backend.encode(texts, batch_size=batch_size)

        return self._backend.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


_embedder_instance: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
