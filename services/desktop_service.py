"""
DeepSeekFS – Desktop Service Adapter (v3.0)
===========================================
Thin wrapper that exposes the existing core/ modules to the PyQt6 UI
using direct Python calls — no HTTP, no sockets, no FastAPI.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List

import app.config as config
from app.config import UserConfig
from app.logger import logger
import os
from core.indexing.index_builder import get_index
from services.startup_indexer import StartupIndexer


class DesktopService:
    """
    Single facade used by the PyQt6 UI layer.
    All heavy lifting is delegated to core/ modules.
    """

    def __init__(self):
        self._idx = get_index()
        self._lock = threading.Lock()
        logger.info("DesktopService: index singleton loaded")

        from core.watcher.file_watcher import FileWatcher
        self.watcher = FileWatcher(self._idx)
        self.watcher.start()

    # ── Indexing ─────────────────────────────────────────────
    def run_indexing(
        self,
        on_status:   Callable[[str],      None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Run indexing with live progress callbacks. Returns new file count."""
        paths = config.WATCH_PATHS
        if not paths:
            if on_status:
                on_status("No watch folders found on this machine.")
            return 0

        if on_status:
            on_status(f"Detected {len(paths)} folder(s) to index…")

        si = StartupIndexer()
        if si._index_has_only_samples():
            si._wipe_index("sample-only index")
        if si._watch_paths_changed():
            si._wipe_index("watch paths changed")

        idx = get_index()
        total_new = 0

        for folder in paths:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue

            all_files = []
            for root, dirs, files in os.walk(folder_path):
                try:
                    target_dir = Path(root).resolve()
                    base_dir = config.BASE_DIR.resolve()
                    if target_dir == base_dir or base_dir in target_dir.parents:
                        dirs.clear()
                        continue
                except Exception:
                    pass

                for skip in list(config.SKIP_DIRS):
                    if skip in dirs:
                        dirs.remove(skip)

                for fname in files:
                    ext = Path(fname).suffix.lower()
                    if ext in config.SUPPORTED_EXTENSIONS:
                        fpath = os.path.join(root, fname)
                        try:
                            if os.path.getsize(fpath) <= config.MAX_FILE_SIZE_BYTES:
                                all_files.append(Path(fpath))
                        except Exception:
                            pass

            n_total = len(all_files)
            if on_status:
                on_status(f"Scanning: {folder}  ({n_total} files)")

            n_done = 0
            for fpath in all_files:
                with self._lock:
                    added = 1 if idx.add_file(str(fpath)) else 0
                total_new += added
                n_done += 1
                if on_progress and n_total > 0:
                    on_progress(n_done, n_total)

            if n_done > 0:
                idx.save()

        if si.is_first_run():
            si.mark_first_run_complete()
        si._save_indexed_roots(paths)

        if on_status:
            on_status(
                f"Indexing done — {self.total_indexed():,} files in index · "
                f"{total_new} new this session"
            )
        return total_new

    # ── Search ───────────────────────────────────────────────
    def search(self, query: str, top_k: int = 20) -> List[dict]:
        """Direct call into core/search — no HTTP round-trip."""
        from core.search.semantic_search import SemanticSearch
        engine = SemanticSearch()
        return engine.search(query, top_k=top_k, use_time_ranking=True)

    # ── Stats ────────────────────────────────────────────────
    def total_indexed(self) -> int:
        try:
            return len(get_index().metadata)
        except Exception:
            return 0

    # ── Access tracking ──────────────────────────────────────
    def record_file_open(self, path: str):
        """Record that a user opened a file (for access-frequency scoring)."""
        try:
            get_index().record_open(path)
        except Exception as e:
            logger.warning(f"Could not record open for {path}: {e}")

    # ── Watch paths management ───────────────────────────────
    def get_watch_paths(self) -> list:
        """Return current validated watch paths."""
        return UserConfig.get_all_watch_paths()

    def add_watch_path(self, path: str) -> bool:
        """Add a user-specified watch path."""
        result = UserConfig.add_watch_path(path)
        if result:
            # Update the module-level WATCH_PATHS
            config.WATCH_PATHS = UserConfig.get_all_watch_paths()
        return result

    def remove_watch_path(self, path: str) -> bool:
        """Remove a user-specified watch path."""
        result = UserConfig.remove_watch_path(path)
        if result:
            config.WATCH_PATHS = UserConfig.get_all_watch_paths()
        return result

    # ── Config ───────────────────────────────────────────────
    def get_config(self) -> dict:
        return UserConfig.load()

    def save_config(self, cfg: dict):
        UserConfig.save(cfg)
        config.WATCH_PATHS = UserConfig.get_all_watch_paths()
