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
from core.activity import (
    log_event, get_recent_events, get_recent_files,
    get_revisit_suggestions, get_daily_stats, get_streak_days,
)


class DesktopService:
    """
    Single facade used by the PyQt6 UI layer.
    All heavy lifting is delegated to core/ modules.
    Initialization is lazy — the embedding model and file watcher
    load in the background so the UI starts instantly.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._idx = None
        self._init_error = None
        self._ready = threading.Event()
        self.watcher = None
        logger.info("DesktopService: starting background initialization…")
        # Kick off heavy init in background so UI + hotkey register instantly
        t = threading.Thread(target=self._bg_init, daemon=True, name="svc-init")
        t.start()

    def _bg_init(self):
        """Background thread: loads index (embedding model) + starts file watcher."""
        try:
            self._idx = get_index()
            logger.info("DesktopService: index singleton loaded (background)")

            from services.startup_indexer import StartupIndexer
            si = StartupIndexer()
            si.run_in_background()

            from core.watcher.file_watcher import FileWatcher
            self.watcher = FileWatcher(self._idx)
            self.watcher.start()
        except Exception as e:
            logger.error(f"DesktopService background init failed: {e}")
            self._init_error = str(e)
        finally:
            self._ready.set()

    def _ensure_ready(self):
        """Wait for background init if not yet done."""
        self._ready.wait(timeout=120)
        if self._idx is None:
            try:
                self._idx = get_index()
            except Exception as e:
                logger.error(f"DesktopService._ensure_ready failed: {e}")
                self._init_error = str(e)

    # ── Indexing ─────────────────────────────────────────────
    def run_indexing(
        self,
        on_status:   Callable[[str],      None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Run indexing with live progress callbacks. Returns new file count."""
        self._ensure_ready()
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
                try:
                    with self._lock:
                        added = 1 if idx.add_file(str(fpath)) else 0
                    total_new += added
                except Exception as e:
                    logger.warning(f"Error indexing {fpath}: {e}")
                    added = 0
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
    def search(self, query: str, top_k: int = 20, use_llm_rerank: bool = False) -> List[dict]:
        """Direct call into core/search — no HTTP round-trip."""
        self._ensure_ready()
        from core.search.semantic_search import SemanticSearch
        # BUG1-FIX: reuse the already-loaded index instead of creating a new SemanticSearch instance
        engine = SemanticSearch(index=self._idx)
        results = engine.search(query, top_k=top_k, use_time_ranking=True,
                                use_llm_rerank=use_llm_rerank)

        # Log search activity
        log_event(event_type="search", query_text=query)

        return results

    # ── Stats ────────────────────────────────────────────────
    def total_indexed(self) -> int:
        """Return indexed file count.
        
        Reads from SQLite directly if the index singleton isn't
        loaded yet — this is the fix for the '0 files indexed' bug.
        The old code returned 0 when _idx was None (still loading
        model), even though the DB already had hundreds of files.
        """
        # Fast path: index is loaded
        if self._idx is not None:
            try:
                return self._idx._db.count()
            except Exception:
                pass

        # Slow path: index not ready, read SQLite directly
        try:
            import sqlite3
            db_path = config.SQLITE_DB_PATH
            from pathlib import Path
            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                cnt = conn.execute('SELECT COUNT(*) FROM files').fetchone()[0]
                conn.close()
                return cnt
        except Exception:
            pass

        return 0

    # ── Access tracking ──────────────────────────────────────
    def record_file_open(self, path: str):
        """Record that a user opened a file (for access-frequency scoring)."""
        try:
            get_index().record_open(path)
            # Log file open activity
            log_event(event_type="open_file", file_path=path)
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

    # ── Activity tracking (Memory OS features) ───────────────
    def get_recent_files(self, limit: int = 5) -> List[dict]:
        """Get recently accessed files for 'Jump back in' suggestions."""
        return get_recent_files(limit)

    def get_recent_events(self, limit: int = 100, event_type: str | None = None) -> List[dict]:
        """Get most recent activity events (for activity search / Memory Lane)."""
        return get_recent_events(limit, event_type)

    def get_revisit_suggestions(self, query: str, exclude_days: int = 2, limit: int = 3) -> List[dict]:
        """Get 'You might want to revisit' suggestions.

        Tokenises the query by whitespace and matches each token
        against file paths in the activity log.  Files accessed
        within ``exclude_days`` are filtered out so we only surface
        slightly-older, contextually-relevant files.
        """
        tokens = query.lower().split()
        return get_revisit_suggestions(tokens, exclude_days, limit)

    def get_daily_stats(self, date=None):
        """Get activity statistics for a day (defaults to today)."""
        from datetime import datetime
        if date is None:
            date = datetime.now()
        return get_daily_stats(date)

    def get_streak_days(self) -> int:
        """Get current continuity streak."""
        return get_streak_days()
