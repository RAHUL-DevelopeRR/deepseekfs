"""
DeepSeekFS – Desktop Service Layer
Wraps the core indexing/search/file-open logic for the PyQt6 UI.
"""

from __future__ import annotations
import os
import sys
import platform
import subprocess
import threading
from pathlib import Path
from typing import Callable, List, Optional

# ── Lazy import of core modules ───────────────────────────────────────────────
def _load_core():
    """Import the project-specific core modules."""
    try:
        from core.embeddings.model import get_embedding_model
        from core.indexing.faiss_store import FaissStore
        from core.ingestion.file_reader import read_file
        from core.search.ranker import rank_results
        return get_embedding_model, FaissStore, read_file, rank_results
    except ImportError as e:
        raise RuntimeError(
            f"Core modules not found. Make sure you run from the project root.\n{e}"
        )


# ── Service class ─────────────────────────────────────────────────────────────
class DesktopSearchService:
    """Single-instance service that manages indexing & search for the desktop app."""

    def __init__(self):
        get_model, FaissStore, self._read_file, self._rank = _load_core()
        self._model = get_model()
        self._store = FaissStore()
        self._watch_paths: List[str] = []
        self._lock = threading.Lock()

    # ── Indexing ──────────────────────────────────────────────────────────────
    def start_indexing(
        self,
        paths: List[str],
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Index files under *paths*, reporting progress via callbacks."""
        all_files: List[Path] = []
        for p in paths:
            all_files.extend(Path(p).rglob("*"))
        all_files = [f for f in all_files if f.is_file()]

        total = len(all_files)
        if total == 0:
            if on_done:
                on_done(False, "No files found in the selected folder(s).")
            return

        for i, filepath in enumerate(all_files, 1):
            try:
                text = self._read_file(str(filepath))
                if text.strip():
                    embedding = self._model.encode(text[:512])
                    with self._lock:
                        self._store.add(str(filepath), embedding)
            except Exception:
                pass  # Skip unreadable files silently

            if on_progress:
                pct = int((i / total) * 100)
                on_progress(pct, f"Indexed {i}/{total}: {filepath.name}")

        self._watch_paths.extend(paths)
        if on_done:
            on_done(True, f"Indexing complete. {total} file(s) processed.")

    # ── Search ────────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """Return ranked search results for *query*."""
        query_vec = self._model.encode(query)
        with self._lock:
            raw = self._store.search(query_vec, top_k=top_k)
        return self._rank(query, raw)

    # ── File operations ───────────────────────────────────────────────────────
    def open_file(self, path: str) -> None:
        """Open a file with the OS-default application."""
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            raise RuntimeError(f"Could not open file: {e}")

    # ── Index management ──────────────────────────────────────────────────────
    def get_index_stats(self) -> dict:
        """Return basic statistics about the current FAISS index."""
        with self._lock:
            count = self._store.count() if hasattr(self._store, "count") else "N/A"
        return {
            "indexed_files": count,
            "watch_paths": self._watch_paths,
            "model": getattr(self._model, "model_name", "unknown"),
        }

    def rebuild_index(self) -> None:
        """Wipe and rebuild the FAISS index from the currently watched paths."""
        with self._lock:
            self._store.reset()
        paths = list(self._watch_paths)
        self._watch_paths.clear()
        self.start_indexing(paths)


# ── Singleton helper ──────────────────────────────────────────────────────────
_instance: Optional[DesktopSearchService] = None


def get_service() -> DesktopSearchService:
    """Return (or lazily create) the global DesktopSearchService instance."""
    global _instance
    if _instance is None:
        _instance = DesktopSearchService()
    return _instance


def reset_service() -> None:
    """Destroy the current singleton (useful for testing)."""
    global _instance
    _instance = None
