"""Watch file system for changes"""
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import app.config as config
from app.logger import logger
from core.indexing.index_builder import IndexBuilder

class FileEventHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self, index_builder: IndexBuilder):
        self.index_builder = index_builder
    
    def on_created(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)
    
    def _process_file(self, file_path: str):
        """Process file if supported"""
        ext = Path(file_path).suffix.lower()
        if ext in config.SUPPORTED_EXTENSIONS:
            logger.info(f"New file detected: {file_path}")
            if self.index_builder.add_file(file_path):
                self.index_builder.save()

class FileWatcher:
    """Monitor file system for new files"""
    
    def __init__(self, index_builder: IndexBuilder):
        self.observer = Observer()
        self.event_handler = FileEventHandler(index_builder)
        self.watch_paths = config.WATCH_PATHS
    
    def start(self):
        """Start watching"""
        # Watchdog crashes on C:\ root due to Permission/OS limits. 
        # Only watch the user's home directory live.
        safe_path = str(Path.home())
        try:
            self.observer.schedule(self.event_handler, safe_path, recursive=True)
            logger.info(f"Watching: {safe_path}")
        except Exception as e:
            logger.error(f"Could not watch {safe_path}: {e}")
        
        self.observer.start()
        logger.info("File watcher started")
    
    def stop(self):
        """Stop watching"""
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")
