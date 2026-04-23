"""
Neuron — Embedding-Based Intent Classifier
=============================================
Classifies user queries into: chat | query | action
using cosine similarity against pre-embedded example centroids.

No hardcoded keywords. No LLM inference. ~5ms per classification.

Architecture:
  1. Load example sentences from storage/intent_examples.json
  2. Embed all examples at startup using the existing ONNX embedder
  3. Compute centroid (mean vector) for each intent category
  4. At runtime: embed user query → cosine similarity → nearest centroid

This is the same technique used by Rasa, Dialogflow, and Amazon Lex.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from app.logger import logger
import app.config as config


_EXAMPLES_PATH = config.STORAGE_DIR / "intent_examples.json"
_VALID_INTENTS = {"chat", "query", "action"}

# Confidence threshold — below this, default to "chat" (safe fallback)
_MIN_CONFIDENCE = 0.25


class IntentClassifier:
    """Embedding-based intent classifier.
    
    Usage:
        clf = IntentClassifier()
        intent, confidence = clf.classify("find my resume")
        # → ("query", 0.82)
    
    Thread-safe: read-only after initialization.
    """

    def __init__(self, examples_path: Path = _EXAMPLES_PATH):
        self._centroids: Dict[str, np.ndarray] = {}
        self._ready = False
        self._load_time_ms = 0

        t0 = time.time()
        try:
            self._build_centroids(examples_path)
            self._ready = True
            self._load_time_ms = int((time.time() - t0) * 1000)
            logger.info(
                f"IntentClassifier: ready ({self._load_time_ms}ms, "
                f"{len(self._centroids)} intents)"
            )
        except Exception as e:
            logger.warning(f"IntentClassifier: failed to initialize: {e}")
            logger.warning("IntentClassifier: falling back to default 'chat'")

    def _build_centroids(self, examples_path: Path):
        """Load examples, embed them, compute centroids."""
        if not examples_path.exists():
            raise FileNotFoundError(f"Intent examples not found: {examples_path}")

        with open(examples_path, "r", encoding="utf-8") as f:
            examples = json.load(f)

        # Validate structure
        for intent in _VALID_INTENTS:
            if intent not in examples:
                raise ValueError(f"Missing intent '{intent}' in examples file")
            if len(examples[intent]) < 5:
                raise ValueError(
                    f"Intent '{intent}' needs at least 5 examples, "
                    f"got {len(examples[intent])}"
                )

        # Get the embedder (already loaded as singleton)
        from core.embeddings.embedder import get_embedder
        embedder = get_embedder()

        # Embed all examples and compute centroids
        for intent in _VALID_INTENTS:
            texts = examples[intent]
            vectors = embedder.encode(texts)  # (N, 384)
            
            # Centroid = mean of all vectors, then L2 normalize
            centroid = np.mean(vectors, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            
            self._centroids[intent] = centroid
            logger.info(
                f"IntentClassifier: '{intent}' centroid from "
                f"{len(texts)} examples"
            )

    def classify(self, text: str) -> Tuple[str, float]:
        """Classify a user query into an intent.
        
        Returns:
            (intent, confidence) where intent is 'chat'|'query'|'action'
            and confidence is 0.0-1.0 (cosine similarity).
            
        If the classifier isn't ready, returns ('chat', 0.0).
        """
        if not self._ready:
            return ("chat", 0.0)

        try:
            from core.embeddings.embedder import get_embedder
            embedder = get_embedder()

            # Embed the query
            query_vec = embedder.encode_single(text)
            norm = np.linalg.norm(query_vec)
            if norm > 0:
                query_vec = query_vec / norm

            # Cosine similarity against each centroid
            scores = {}
            for intent, centroid in self._centroids.items():
                similarity = float(np.dot(query_vec, centroid))
                scores[intent] = similarity

            # Pick the highest
            best_intent = max(scores, key=scores.get)
            best_score = scores[best_intent]

            # If confidence is too low, default to chat (safe)
            if best_score < _MIN_CONFIDENCE:
                logger.info(
                    f"IntentClassifier: low confidence ({best_score:.3f}), "
                    f"defaulting to 'chat'"
                )
                return ("chat", best_score)

            logger.info(
                f"IntentClassifier: '{text[:50]}' → {best_intent} "
                f"(confidence={best_score:.3f}, "
                f"scores={{{', '.join(f'{k}={v:.3f}' for k, v in scores.items())}}})"
            )
            return (best_intent, best_score)

        except Exception as e:
            logger.error(f"IntentClassifier: classification failed: {e}")
            return ("chat", 0.0)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def stats(self) -> dict:
        """Diagnostic info."""
        return {
            "ready": self._ready,
            "intents": list(self._centroids.keys()),
            "load_time_ms": self._load_time_ms,
        }


# ── Singleton ─────────────────────────────────────────────────
_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """Get the global intent classifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
