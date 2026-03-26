"""Smart startup indexer — uses the global singleton index (v2.0)

Detects when WATCH_PATHS have changed since last indexing and
triggers a full re-index. Saves indexed roots to storage/indexed_roots.json
for comparison on next startup.
"""
import json
import threading
from pathlib import Path
from typing import Set
import app.config as config
from app.logger import logger
from core.indexing.index_builder import get_index


SAMPLE_DOCS_PATH = str(config.BASE_DIR / "sample_documents")


class StartupIndexer:
    """
    On every app start:
    - Detects if stored index has ONLY sample documents → wipes and re-indexes
    - Detects if WATCH_PATHS changed since last run → wipes and re-indexes
    - FIRST RUN → full scan of all WATCH_PATHS
    - SUBSEQUENT → incremental scan (only new/changed files)
    """

    def is_first_run(self) -> bool:
        return not Path(config.FIRST_RUN_FLAG).exists()

    def mark_first_run_complete(self):
        Path(config.FIRST_RUN_FLAG).touch()

    # ── Stale index detection ─────────────────────────────────
    def _index_has_only_samples(self) -> bool:
        """True if every indexed file is a sample/library file — needs re-scan."""
        idx = get_index()
        if len(idx.metadata) == 0:
            return False
        sample_root = str(config.BASE_DIR / "sample_documents")
        LIBRARY_MARKERS = (
            "site-packages", "\\Lib\\", "/lib/python",
            "\\venv\\", "/.venv/",
        )
        for m in idx.metadata:
            p = m["path"]
            if p.startswith(sample_root):
                continue
            if any(marker in p for marker in LIBRARY_MARKERS):
                continue
            return False  # found a real user file
        return True

    # ── Watch-path change detection ───────────────────────────
    def _load_indexed_roots(self) -> Set[str]:
        """Load the set of root paths that were indexed last time."""
        roots_file = config.INDEXED_ROOTS_FILE
        if not Path(roots_file).exists():
            return set()
        try:
            data = json.loads(Path(roots_file).read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()

    def _save_indexed_roots(self, paths: list):
        """Save current watch paths for comparison on next startup."""
        try:
            Path(config.INDEXED_ROOTS_FILE).write_text(
                json.dumps(paths, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Could not save indexed roots: {e}")

    def _watch_paths_changed(self) -> bool:
        """True if current WATCH_PATHS differ from last indexed roots."""
        last_roots = self._load_indexed_roots()
        if not last_roots:
            return False  # no record → let first_run logic decide
        current = {str(Path(p).resolve()) for p in config.WATCH_PATHS}
        return current != {str(Path(p).resolve()) for p in last_roots}

    # ── Wipe ──────────────────────────────────────────────────
    def _wipe_index(self, reason: str = "stale"):
        """Delete all index files so a fresh scan starts."""
        logger.info(f"Wiping index ({reason})...")
        for p in [
            config.FAISS_INDEX_PATH,
            config.METADATA_PATH,
            config.INDEXED_PATHS_DB,
            config.SQLITE_DB_PATH,
            str(config.FIRST_RUN_FLAG),
        ]:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        idx = get_index()
        idx._create_fresh_index()
        logger.info("Index wiped. Starting fresh scan.")

    # ── Run ───────────────────────────────────────────────────
    def run_in_background(self):
        thread = threading.Thread(
            target=self._run, name="StartupIndexer", daemon=True,
        )
        thread.start()
        return thread

    def _run(self):
        paths = config.WATCH_PATHS

        if not paths:
            logger.warning("No user folders found on this machine.")
            return

        logger.info(f"Detected user folders: {paths}")

        # Auto-wipe if index only has sample docs
        if self._index_has_only_samples():
            self._wipe_index("sample-only index detected")

        # Auto-wipe if watch paths changed since last index
        if self._watch_paths_changed():
            self._wipe_index("watch paths changed")

        if self.is_first_run():
            logger.info("FIRST RUN — full scan of all user folders...")
        else:
            logger.info("Incremental scan — checking for new files...")

        idx = get_index()
        total = 0
        for path in paths:
            if not Path(path).exists():
                logger.warning(f"Watch path does not exist, skipping: {path}")
                continue
            logger.info(f"  Scanning: {path}")
            count = idx.index_directory(path, recursive=True)
            total += count
            if count > 0:
                idx.save()

        logger.info(f"Indexing complete. {total} new files added.")

        if self.is_first_run():
            self.mark_first_run_complete()

        # Persist current watch paths for next comparison
        self._save_indexed_roots(paths)
