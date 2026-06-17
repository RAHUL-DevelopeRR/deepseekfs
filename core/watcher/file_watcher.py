"""Watch file system for changes."""
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import app.config as config
from app.logger import logger
from core.indexing.index_builder import IndexBuilder, _is_skipped_dir, _is_skipped_file


def _is_skipped_path(path: str) -> bool:
    target = Path(path)
    if config.is_drive_root(target):
        return True
    try:
        resolved = target.resolve()
        base_dir = config.BASE_DIR.resolve()
        storage_dir = config.STORAGE_DIR.resolve()
        if resolved == base_dir or base_dir in resolved.parents:
            return True
        if resolved == storage_dir or storage_dir in resolved.parents:
            return True
    except Exception:
        pass
    if _is_skipped_file(target.name):
        return True
    return any(_is_skipped_dir(part) for part in target.parts)


class FileEventHandler(FileSystemEventHandler):
    """Handle file and folder events for the live index."""

    def __init__(self, index_builder: IndexBuilder):
        self.index_builder = index_builder

    def on_created(self, event):
        if event.is_directory:
            self._process_folder(event.src_path)
        else:
            self._process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)

    def on_deleted(self, event):
        if _is_skipped_path(event.src_path):
            return
        path = str(Path(event.src_path).resolve())
        if self.index_builder.remove_file(path):
            logger.info(f"Removed from index: {event.src_path}")

    def on_moved(self, event):
        if _is_skipped_path(event.src_path) or _is_skipped_path(event.dest_path):
            return
        old_path = str(Path(event.src_path).resolve())
        self.index_builder.remove_file(old_path)
        if event.is_directory:
            self._process_folder(event.dest_path)
        else:
            self._process_file(event.dest_path)
        logger.info(f"Path moved: {event.src_path} -> {event.dest_path}")

    def _process_folder(self, folder_path: str):
        if _is_skipped_path(folder_path):
            return
        logger.info(f"New folder detected: {folder_path}")
        if self.index_builder.add_folder(folder_path):
            self.index_builder.save()

    def _process_file(self, file_path: str):
        """Process file if supported, then evaluate watch hooks."""
        if _is_skipped_path(file_path):
            return
        ext = Path(file_path).suffix.lower()
        if ext not in config.SUPPORTED_EXTENSIONS:
            return

        logger.info(f"New file detected: {file_path}")
        if self.index_builder.add_file(file_path):
            self.index_builder.save()

        try:
            from services.watch_rules import get_watch_hooks

            get_watch_hooks().evaluate(file_path, "created")
        except Exception:
            pass


class FileWatcher:
    """Monitor configured folders for new files."""

    def __init__(self, index_builder: IndexBuilder):
        self.observer = Observer()
        self.event_handler = FileEventHandler(index_builder)
        self.watch_paths = config.filter_live_watch_paths(config.WATCH_PATHS)

    def start(self):
        scheduled = 0
        skipped = set(config.WATCH_PATHS) - set(self.watch_paths)
        for path in sorted(skipped):
            logger.warning(f"Skipping live watcher for broad drive root: {path}")

        for path in self.watch_paths:
            if _is_skipped_path(path) or not Path(path).exists():
                logger.info(f"Skipping watcher path: {path}")
                continue
            try:
                self.observer.schedule(self.event_handler, path, recursive=True)
                scheduled += 1
                logger.info(f"Watching: {path}")
            except Exception as e:
                logger.error(f"Could not watch {path}: {e}")

        if scheduled:
            self.observer.start()
            logger.info(f"File watcher started ({scheduled} roots)")
        else:
            logger.warning("File watcher not started: no safe watch roots")

    def stop(self):
        if not self.observer.is_alive():
            return
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")
