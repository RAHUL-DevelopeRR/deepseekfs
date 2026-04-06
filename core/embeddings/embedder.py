"""Sentence Transformer Wrapper for Embeddings (v4.7)

Loads the all-MiniLM-L6-v2 model from a local cache first (bundled with
the installer), falling back to HuggingFace download only if needed.
"""

# ── Force CPU-only mode & prevent Windows DLL conflicts ──────────
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
from typing import List, Union
from pathlib import Path
import app.config as config
from app.logger import logger


def _find_local_model() -> str | None:
    """Look for a pre-cached model directory (avoids download on first run)."""
    candidates = [
        # Bundled with installer in storage/models/
        config.STORAGE_DIR / "models" / config.MODEL_NAME,
        # Project-level (dev)
        config.BASE_DIR / "storage" / "models" / config.MODEL_NAME,
        # HuggingFace cache (already downloaded previously)
        Path.home() / ".cache" / "huggingface" / "hub",
    ]
    for p in candidates:
        if p.is_dir() and any(p.iterdir()):
            # Check it has model files (config.json or modules.json)
            if (p / "config.json").exists() or (p / "modules.json").exists():
                logger.info(f"Local model found at: {p}")
                return str(p)
    return None


class Embedder:
    """Generate embeddings using sentence-transformers"""

    def __init__(self, model_name: str = config.MODEL_NAME):
        logger.info(f"Loading model: {model_name}")

        # Try local model first (no internet needed)
        local_path = _find_local_model()
        model_source = local_path if local_path else model_name

        if not local_path:
            # Only bypass SSL when we actually need to download
            logger.info("No local model cache — downloading from HuggingFace")
            os.environ["CURL_CA_BUNDLE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""
            os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass

        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_source, device="cpu")
        self.model_name = model_name

        # Restore SSL settings after download
        if not local_path:
            for key in ["CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"]:
                os.environ.pop(key, None)

        logger.info(f"Model loaded. Embedding dim: {self.model.get_sentence_embedding_dimension()}")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Generate embeddings for texts"""
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=True,
        )

    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.encode([text])[0]


# Global embedder instance
_embedder_instance = None

def get_embedder() -> Embedder:
    """Get or create embedder singleton"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
