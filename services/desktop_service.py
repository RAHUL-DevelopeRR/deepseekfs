"""
DeepSeekFS – Desktop Service Adapter (v2.0)
===========================================
Thin wrapper that exposes the existing core/ modules to the PyQt6 UI
using **direct Python calls** — no HTTP, no sockets, no FastAPI.

This is the only new file that touches core/; everything else in
services/ and core/ is UNCHANGED.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List

import app.config as config
from app.logger import logger
from core.indexing.index_builder import get_index
from services.startup_indexer import StartupIndexer


class DesktopService:
    """
    Single facade used by the PyQt6 UI layer.
    All heavy lifting is delegated to core/ modules.
    """

    def __init__(self):
        # Warm up the FAISS index singleton so the first search is fast
        self._idx = get_index()
        self._lock = threading.Lock()
        logger.info("DesktopService: index singleton loaded")

    # ── Indexing ──────────────────────────────────────────────────────────────
    def run_indexing(
        self,
        on_status   : Callable[[str],      None] | None = None,
        on_progress : Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Run the same StartupIndexer logic that the web app used,
        but with live progress callbacks for the PyQt6 progress bar.

        Returns the number of NEW files added this session.
        """
        paths = config.WATCH_PATHS
        if not paths:
            if on_status:
                on_status("⚠️  No watch folders found on this machine.")
            return 0

        if on_status:
            on_status(f"📂  Detected {len(paths)} folder(s) to index…")

        # Auto-wipe sample-only index (same logic as StartupIndexer)
        si = StartupIndexer()
        if si._index_has_only_samples():
            si._wipe_index()

        idx   = get_index()
        total_new = 0

        for folder in paths:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue

            # Count files first so we can report percentage
            all_files = [
                f for f in folder_path.rglob("*")
                if f.is_file()
                and f.suffix.lower() in config.SUPPORTED_EXTENSIONS
                and f.stat().st_size <= config.MAX_FILE_SIZE_BYTES
            ]
            n_total = len(all_files)

            if on_status:
                on_status(f"  📂  {folder}  ({n_total} eligible files)")

            # Index one file at a time so we can report progress
            n_done = 0
            for fpath in all_files:
                with self._lock:
                    added = idx.index_file(str(fpath))
                total_new += added
                n_done += 1
                if on_progress and n_total > 0:
                    on_progress(n_done, n_total)

            # Persist after each folder
            if n_done > 0:
                idx.save()

        if si.is_first_run():
            si.mark_first_run_complete()

        if on_status:
            on_status(
                f"✅  Indexing done — {self.total_indexed():,} files in index • "
                f"{total_new} new this session"
            )
        return total_new

    # ── Search ────────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 15) -> List[dict]:
        """
        Direct call into core/search — no HTTP round-trip.
        Returns a list of result dicts (same schema the web API returned).
        """
        from core.search.search_engine import SearchEngine
        engine = SearchEngine(get_index())
        return engine.search(query, top_k=top_k, use_time_ranking=True)

    # ── Stats ─────────────────────────────────────────────────────────────────
    def total_indexed(self) -> int:
        """How many documents are currently in the FAISS index."""
        try:
            return len(get_index().metadata)
        except Exception:
            return 0
