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
INDEXED_ROOTS_FILE = STORAGE_DIR / "indexed_roots.json"

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
# Persistent user configuration
# ─────────────────────────────────────────────────────────────
class UserConfig:
    """JSON-persisted user preferences stored in storage/user_config.json."""

    CONFIG_PATH = STORAGE_DIR / "user_config.json"

    DEFAULTS = {
        "extra_watch_paths": [],
        "excluded_paths": [],
        "top_k": 20,
        "theme": "auto",
        "hotkey": "shift+space",
    }

    @classmethod
    def load(cls) -> dict:
        """Load config from disk, returning defaults for any missing keys."""
        config = dict(cls.DEFAULTS)
        if cls.CONFIG_PATH.exists():
            try:
                data = json.loads(cls.CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    config.update(data)
            except Exception:
                pass
        return config

    @classmethod
    def save(cls, config: dict):
        """Persist config to disk."""
        try:
            cls.CONFIG_PATH.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    @classmethod
    def get_all_watch_paths(cls) -> list:
        """Merge default user folders + user-configured extra paths.
        Validates all paths exist. Deduplicates by resolved path."""
        defaults = get_user_watch_paths()
        config = cls.load()
        extras = config.get("extra_watch_paths", [])
        excluded = set(config.get("excluded_paths", []))

        seen = set()
        merged = []
        for p in defaults + extras:
            try:
                norm = str(Path(p).resolve())
                if norm in seen or norm in excluded:
                    continue
                if not Path(p).exists():
                    continue
                seen.add(norm)
                merged.append(p)
            except Exception:
                continue
        return merged

    @classmethod
    def add_watch_path(cls, path: str) -> bool:
        """Add a user-specified watch path. Returns True if added."""
        config = cls.load()
        extras = config.get("extra_watch_paths", [])
        norm = str(Path(path).resolve())
        existing = {str(Path(p).resolve()) for p in extras}
        if norm in existing or not Path(path).exists():
            return False
        extras.append(str(path))
        config["extra_watch_paths"] = extras
        cls.save(config)
        return True

    @classmethod
    def remove_watch_path(cls, path: str) -> bool:
        """Remove a user-specified watch path. Returns True if removed."""
        config = cls.load()
        extras = config.get("extra_watch_paths", [])
        norm = str(Path(path).resolve())
        new_extras = [p for p in extras if str(Path(p).resolve()) != norm]
        if len(new_extras) == len(extras):
            return False
        config["extra_watch_paths"] = new_extras
        cls.save(config)
        return True


# Build WATCH_PATHS using UserConfig
WATCH_PATHS = UserConfig.get_all_watch_paths()

# Supported file types (expanded)
SUPPORTED_EXTENSIONS = {
    # Documents
    ".txt", ".pdf", ".docx", ".doc", ".md",
    ".pptx", ".xlsx", ".xls", ".html", ".htm",
    # Data
    ".json", ".csv", ".xml",
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".rs", ".go", ".java", ".cpp", ".c", ".h",
    ".cs", ".rb", ".php", ".swift", ".kt",
    # Config
    ".env", ".ini", ".toml", ".cfg", ".yaml", ".yml",
    # Notebooks
    ".ipynb",
    # Logs
    ".log",
    # Media (metadata only)
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
}

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
FAISS_INDEX_PATH = str(FAISS_INDEX_DIR / "index.bin")
METADATA_PATH = str(CACHE_DIR / "metadata.pkl")
INDEXED_PATHS_DB = str(CACHE_DIR / "indexed_paths.pkl")  # deprecated
SQLITE_DB_PATH = str(CACHE_DIR / "metadata.db")

# Search configuration
TOP_K = UserConfig.load().get("top_k", 20)
SIMILARITY_THRESHOLD = 0.3

# API configuration
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = False

# UI configuration
UI_TITLE = "DeepSeekFS - Semantic File Search"
UI_WIDTH = 1000
UI_HEIGHT = 700

# Max file size to index (100 GB)
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 * 1024
