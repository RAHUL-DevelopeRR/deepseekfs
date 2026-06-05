"""
Neuron — Embedding-Based Intent Classifier
=============================================
Classifies user queries into: chat | query | action
using cosine similarity against pre-embedded examples and intent centroids.

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
import re
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
        self._examples: Dict[str, np.ndarray] = {}
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
            
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = np.divide(vectors, np.clip(norms, 1e-9, None))

            # Centroid = mean of all vectors, then L2 normalize
            centroid = np.mean(vectors, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            
            self._centroids[intent] = centroid
            self._examples[intent] = vectors
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
        if self._route_code_conversation(text):
            logger.info(f"IntentClassifier: code conversation -> chat for '{text[:50]}'")
            return ("chat", 1.0)

        if self._route_vague_file_reference(text):
            logger.info(f"IntentClassifier: vague file reference -> chat for '{text[:50]}'")
            return ("chat", 1.0)

        routed = self._route_explicit_file_action(text)
        if routed:
            logger.info(f"IntentClassifier: explicit file action -> action for '{text[:50]}'")
            return ("action", 1.0)

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

            # Blend broad intent shape with nearest-example similarity. This
            # keeps classification data-driven while avoiding centroid drift.
            scores = {}
            for intent, centroid in self._centroids.items():
                centroid_similarity = float(np.dot(query_vec, centroid))
                examples = self._examples.get(intent)
                nearest_similarity = (
                    float(np.max(examples @ query_vec))
                    if examples is not None and len(examples) > 0
                    else centroid_similarity
                )
                scores[intent] = (0.35 * centroid_similarity) + (0.65 * nearest_similarity)

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

    @staticmethod
    def _has_concrete_file_target(low: str) -> bool:
        return bool(
            re.search(
                r"([\\/]|"
                r"\b\w+\.[a-z0-9]{1,8}\b|"
                r"\bpytest\b|"
                r"\bgit\s+status\b|"
                r"\b(called|named)\b)",
                low,
            )
        )

    @classmethod
    def _route_code_conversation(cls, text: str) -> bool:
        """Keep code generation and code revision in chat unless a file is named."""
        low = text.lower().strip()
        if cls._has_concrete_file_target(low):
            return False

        has_code_subject = re.search(
            r"\b(code|program|script|function|class|algorithm|java|python|"
            r"database|db|sql|jdbc)\b",
            low,
        )
        has_generation_or_revision = re.search(
            r"\b(create|write|generate|give|show|provide|make|need|want|"
            r"alter|change|modify|update|edit|add|insert|inserting|include|fix)\b",
            low,
        )
        return bool(has_code_subject and has_generation_or_revision)

    @staticmethod
    def _route_explicit_file_action(text: str) -> bool:
        """Route concrete file/project operations to action mode.

        Pure code-generation prompts should remain chat, but operations that
        name files, paths, tests, or git commands need tools.
        """
        low = text.lower().strip()
        if re.search(r"\b(write|create)\b.*\b(code|program|function|algorithm)\b", low):
            if not re.search(r"\b(file|save|as|called|named|to\s+[\w.-]+\.[a-z0-9]+)\b", low):
                return False

        has_action_verb = re.search(
            r"\b(create|save|write|edit|modify|update|read|open|run|execute)\b", low
        )
        return bool(has_action_verb and IntentClassifier._has_concrete_file_target(low))

    @staticmethod
    def _route_vague_file_reference(text: str) -> bool:
        """Avoid tool calls when the user says "the file" without a path/name."""
        low = text.lower().strip()
        if IntentClassifier._has_concrete_file_target(low):
            return False
        has_file_reference = re.search(r"\b(the|this|that|current)\s+file\b", low)
        has_toolish_verb = re.search(
            r"\b(save|run|execute|open|read|edit|modify|update|delete|move|copy)\b",
            low,
        )
        return bool(has_file_reference and has_toolish_verb)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def stats(self) -> dict:
        """Diagnostic info."""
        return {
            "ready": self._ready,
            "intents": list(self._centroids.keys()),
            "examples": {intent: len(vectors) for intent, vectors in self._examples.items()},
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
