"""LLM Re-Ranker — uses local Llama via Ollama to re-rank search results.

Architecture:
    FAISS (fast, <5ms) → top-N candidates → LLM reads file content → re-scores

The LLM understands intent: "fibonacci python code" will match a file
containing recursive fibonacci even if the filename is "algo_test.py".

Trade-offs:
    - MiniLM alone: 80MB RAM, <5ms, good keyword/semantic match
    - MiniLM + Llama re-rank: +1.3GB RAM, +1-3s, deep code/content understanding
"""
from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

from app.logger import logger

OLLAMA_URL = "http://localhost:11434"
RERANK_MODEL = "llama3.2:1b"
RERANK_TIMEOUT = 30  # seconds


def _read_file_snippet(path: str, max_chars: int = 2000) -> str:
    """Read a file's content for LLM analysis (truncated for speed)."""
    ext = Path(path).suffix.lower()
    try:
        # Text-based files
        if ext in {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
                   ".rs", ".go", ".java", ".cpp", ".c", ".h", ".cs",
                   ".rb", ".php", ".html", ".css", ".json", ".xml",
                   ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log",
                   ".env", ".sh", ".bat", ".csv", ".sql", ".ipynb"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        elif ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                text = ""
                for page in doc[:3]:
                    text += page.get_text()
                    if len(text) > max_chars:
                        break
                doc.close()
                return text[:max_chars]
            except Exception:
                return ""
        elif ext in {".docx", ".doc"}:
            try:
                from docx import Document
                doc = Document(path)
                text = "\n".join([p.text for p in doc.paragraphs])
                return text[:max_chars]
            except Exception:
                return ""
    except Exception:
        pass
    return ""


class LLMReranker:
    """Re-ranks search results using a local LLM for deep content understanding.

    Only invoked when:
    1. Ollama is running locally
    2. The user has committed a search (pressed Enter)
    3. There are enough results to justify re-ranking

    Falls back gracefully — search always works without it.
    """

    def __init__(self, model: str = RERANK_MODEL):
        self._model = model
        self._available: Optional[bool] = None
        self._last_check: float = 0
        self._check_interval: float = 60.0  # re-check every 60s

    def is_available(self) -> bool:
        """Check if Ollama is running and the model exists. Cached for 60s."""
        now = time.time()
        if self._available is not None and (now - self._last_check) < self._check_interval:
            return self._available

        try:
            req = Request(f"{OLLAMA_URL}/api/tags", method="GET")
            resp = urlopen(req, timeout=2)
            data = json.loads(resp.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            self._available = any(self._model in m for m in models)
            self._last_check = now
            return self._available
        except Exception:
            self._available = False
            self._last_check = now
            return False

    def rerank(
        self,
        query: str,
        results: List[Dict],
        max_candidates: int = 8,
    ) -> List[Dict]:
        """Re-rank search results using LLM content understanding.

        Args:
            query: The user's search query
            results: List of search result dicts (must have 'path', 'name', 'combined_score')
            max_candidates: Max files to send to LLM (trade-off: more = slower but better)

        Returns:
            Re-ranked list of results (same format, updated scores)
        """
        if not self.is_available():
            return results

        if len(results) < 2:
            return results

        candidates = results[:max_candidates]
        t0 = time.time()

        # Build file snippets for the LLM
        file_entries = []
        for i, r in enumerate(candidates):
            snippet = _read_file_snippet(r["path"], max_chars=1500)
            if not snippet.strip():
                snippet = f"(Binary or empty file: {r['name']})"
            # Truncate for token efficiency
            snippet = snippet[:1200]
            file_entries.append(
                f"[File {i+1}] {r['name']} ({r['extension']})\n"
                f"Path: {r['path']}\n"
                f"Content preview:\n{snippet}\n"
            )

        files_text = "\n---\n".join(file_entries)

        prompt = (
            f"User is searching for: \"{query}\"\n\n"
            f"Here are {len(candidates)} files found. Score each file's relevance "
            f"to the user's search query from 0 to 10 (10 = perfect match).\n\n"
            f"Consider:\n"
            f"- Does the file content match what the user is looking for?\n"
            f"- For code searches: does the code implement what's described?\n"
            f"- For document searches: is the topic relevant?\n\n"
            f"{files_text}\n\n"
            f"Respond with ONLY a JSON array of scores, one per file. "
            f"Example: [8, 3, 9, 1, 5, 7, 2, 4]\n"
            f"No explanations, just the array."
        )

        system = (
            "You are a file relevance scorer. Given a user's search query and "
            "file contents, you score each file 0-10 for relevance. "
            "You understand code, documents, and data files deeply. "
            "Respond with ONLY a JSON array of integer scores."
        )

        try:
            payload = json.dumps({
                "model": self._model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "num_predict": 100,
                    "temperature": 0.1,
                }
            }).encode("utf-8")

            req = Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urlopen(req, timeout=RERANK_TIMEOUT)
            data = json.loads(resp.read())
            response_text = data.get("response", "").strip()

            # Parse the scores from LLM response
            scores = self._parse_scores(response_text, len(candidates))
            elapsed = time.time() - t0

            if scores:
                logger.info(
                    f"LLM Re-rank: '{query}' → scores={scores} ({elapsed:.1f}s)"
                )
                # Apply LLM scores as a multiplier on top of existing scores
                for i, result in enumerate(candidates):
                    llm_score = scores[i] / 10.0  # normalize to 0-1
                    original = result["combined_score"]
                    # Blend: 40% original FAISS score + 60% LLM score
                    result["combined_score"] = round(
                        0.40 * original + 0.60 * llm_score, 4
                    )
                    result["llm_score"] = round(llm_score, 4)

                # Re-sort by the blended score
                candidates.sort(key=lambda x: x["combined_score"], reverse=True)

                # Append any remaining results that weren't re-ranked
                reranked_paths = {r["path"] for r in candidates}
                remaining = [r for r in results if r["path"] not in reranked_paths]
                return candidates + remaining
            else:
                logger.warning(f"LLM Re-rank: could not parse scores from: {response_text}")
                return results

        except Exception as e:
            elapsed = time.time() - t0
            logger.warning(f"LLM Re-rank failed ({elapsed:.1f}s): {e}")
            return results

    @staticmethod
    def _parse_scores(text: str, expected_count: int) -> Optional[List[int]]:
        """Parse LLM response into a list of integer scores."""
        # Try direct JSON parse first
        try:
            # Find the JSON array in the response
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                scores = json.loads(text[start:end])
                if isinstance(scores, list) and len(scores) == expected_count:
                    return [max(0, min(10, int(s))) for s in scores]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: try to extract numbers
        import re
        numbers = re.findall(r'\b(\d+)\b', text)
        if len(numbers) >= expected_count:
            scores = [max(0, min(10, int(n))) for n in numbers[:expected_count]]
            return scores

        return None


# ── Singleton ────────────────────────────────────────────────
_reranker: Optional[LLMReranker] = None


def get_reranker() -> LLMReranker:
    global _reranker
    if _reranker is None:
        _reranker = LLMReranker()
    return _reranker
