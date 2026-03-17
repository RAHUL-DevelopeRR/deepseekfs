"""Smart First-Run + Incremental Indexer"""
import threading
from pathlib import Path
import app.config as config
from app.logger import logger
from core.indexing.index_builder import IndexBuilder


class StartupIndexer:
    """
    Runs on every app start:
    - FIRST RUN  → Full scan of all WATCH_PATHS
    - SUBSEQUENT → Incremental scan (only new/changed files)
    """

    def __init__(self, index_builder: IndexBuilder):
        self.index_builder = index_builder

    def is_first_run(self) -> bool:
        return not Path(config.FIRST_RUN_FLAG).exists()

    def mark_first_run_complete(self):
        Path(config.FIRST_RUN_FLAG).touch()

    def run_in_background(self):
        """Start indexing in a background thread — never blocks the UI"""
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
            logger.warning("No watch paths found. Nothing to index.")
            return

        if self.is_first_run():
            logger.info("🔍 FIRST RUN detected — full scan starting...")
            logger.info(f"Scanning paths: {paths}")
        else:
            logger.info("🔄 Incremental scan — checking for new files...")

        total = 0
        for path in paths:
            logger.info(f"Scanning: {path}")
            count = self.index_builder.index_directory(path, recursive=True)
            total += count

        if total > 0:
            self.index_builder.save()
            logger.info(f"✅ Indexing complete. {total} new files indexed.")
        else:
            logger.info("✅ No new files found. Index is up to date.")

        if self.is_first_run():
            self.mark_first_run_complete()
            logger.info("🏁 First-run flag set.")
