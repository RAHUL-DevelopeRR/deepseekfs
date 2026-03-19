"""Configuration Management"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = BASE_DIR / "storage"
FAISS_INDEX_DIR = STORAGE_DIR / "faiss_index"
CACHE_DIR = STORAGE_DIR / "cache"
FIRST_RUN_FLAG = STORAGE_DIR / ".first_run_complete"
CUSTOM_PATHS_FILE = STORAGE_DIR / "custom_watch_paths.json"

# Create directories
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Directories to SKIP during scanning (centralized)
# ─────────────────────────────────────────────────────────────
SKIP_DIRS = {
    # Python virtual environments & packaging
    "venv", ".venv", "env", ".env", "__pycache__",
    "site-packages", "dist-packages",
    "Lib", "lib", "Scripts", "bin",
    ".eggs", "*.egg-info",
    # Node / JS
    "node_modules", "bower_components",
    # VCS & IDE
    ".git", ".hg", ".svn",
    ".idea", ".vscode", ".vs",
    # OS / system
    "Windows", "$Recycle.Bin", "ProgramData",
    "AppData", "System Volume Information",
    # Caches & build artefacts
    ".cache", ".tox", ".nox", ".mypy_cache",
    ".pytest_cache", "build", "dist",
    "__pypackages__",
}

# ─────────────────────────────────────────────────────────────
# AUTO-DETECT real user folders (cross-platform)
# ─────────────────────────────────────────────────────────────
def get_user_watch_paths() -> list:
    """Return common user content folders that exist on this machine."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Videos",
        home / "Music",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
    ]
    return [str(p) for p in candidates if p.exists()]


# ─────────────────────────────────────────────────────────────
# Persist user-added folders across restarts
# ─────────────────────────────────────────────────────────────
def load_custom_paths() -> list:
    """Load user-added watch paths from disk."""
    if CUSTOM_PATHS_FILE.exists():
        try:
            data = json.loads(CUSTOM_PATHS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [p for p in data if Path(p).exists()]
        except Exception:
            pass
    return []


def save_custom_paths(paths: list):
    """Save the list of user-added watch paths to disk."""
    try:
        CUSTOM_PATHS_FILE.write_text(
            json.dumps(paths, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _build_watch_paths() -> list:
    """Merge default user folders + persisted custom folders (deduplicated)."""
    defaults = get_user_watch_paths()
    custom = load_custom_paths()
    seen = set()
    merged = []
    for p in defaults + custom:
        norm = str(Path(p).resolve())
        if norm not in seen:
            seen.add(norm)
            merged.append(p)
    return merged


WATCH_PATHS = _build_watch_paths()

# Supported file types
SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".docx", ".doc",
    ".md", ".json", ".csv", ".py", ".js",
    ".pptx", ".xlsx", ".xls", ".html",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"
}

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
FAISS_INDEX_PATH = str(FAISS_INDEX_DIR / "index.bin")
METADATA_PATH = str(CACHE_DIR / "metadata.pkl")
INDEXED_PATHS_DB = str(CACHE_DIR / "indexed_paths.pkl")  # duplicate guard (deprecated)
SQLITE_DB_PATH = str(CACHE_DIR / "metadata.db")           # NEW: replaces pkl files

# Search configuration
TOP_K = 10
SIMILARITY_THRESHOLD = 0.3

# API configuration
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = False  # Must be False when running in thread

# UI configuration
UI_TITLE = "DeepSeekFS - Semantic File Search"
UI_WIDTH = 1000
UI_HEIGHT = 700

# Max file size to index (100 GB)
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 * 1024
