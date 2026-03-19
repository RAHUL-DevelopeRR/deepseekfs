"""Smart startup indexer - uses the global singleton index"""
import threading
import shutil
from pathlib import Path
import app.config as config
from app.logger import logger
from core.indexing.index_builder import get_index


SAMPLE_DOCS_PATH = str(config.BASE_DIR / "sample_documents")


class StartupIndexer:
    """
    On every app start:
    - Detects if stored index has ONLY sample documents → wipes and re-indexes real folders
    - FIRST RUN → full scan of all WATCH_PATHS
    - SUBSEQUENT → incremental scan (only new/changed files)
    """

    def is_first_run(self) -> bool:
        return not Path(config.FIRST_RUN_FLAG).exists()

    def mark_first_run_complete(self):
        Path(config.FIRST_RUN_FLAG).touch()

    def _index_has_only_samples(self) -> bool:
        """Returns True if every indexed file is inside sample_documents/"""
        idx = get_index()
        if len(idx.metadata) == 0:
            return False  # Empty index is fine
        sample_root = str(config.BASE_DIR / "sample_documents")
        return all(m["path"].startswith(sample_root) for m in idx.metadata)

    def _wipe_index(self):
        """Delete all index files so a fresh scan starts"""
        logger.info("🗑️  Wiping stale sample-only index...")
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

        # Reinitialize the singleton with a clean slate
        idx = get_index()
        idx._create_fresh_index()
        logger.info("✅ Stale index wiped. Starting fresh scan.")

    def run_in_background(self):
        thread = threading.Thread(
            target=self._run,
            name="StartupIndexer",
            daemon=True
        )
        thread.start()
        return thread

    def _run(self):
        paths = config.WATCH_PATHS

        if not paths:
            logger.warning("⚠️  No user folders found on this machine. Nothing to index.")
            return

        logger.info(f"📂 Detected user folders: {paths}")

        # Auto-wipe if index only has sample docs
        if self._index_has_only_samples():
            self._wipe_index()

        if self.is_first_run():
            logger.info("🔍 FIRST RUN — full scan of all user folders...")
        else:
            logger.info("🔄 Incremental scan — checking for new files...")

        idx = get_index()
        total = 0
        for path in paths:
            logger.info(f"  Scanning: {path}")
            count = idx.index_directory(path, recursive=True)
            total += count
            if count > 0:
                idx.save()  # Save after each folder so progress is never lost

        logger.info(f"✅ Indexing complete. {total} new files added.")

        if self.is_first_run():
            self.mark_first_run_complete()
