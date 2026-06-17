"""Configuration Management"""
import json
import os
import platform
import re
import sys
from pathlib import Path

# dotenv is optional — not required in frozen/installed builds
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Paths ──────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    RUNTIME_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).parent.parent
    RUNTIME_DIR = BASE_DIR

_storage_override = os.environ.get("NEURON_STORAGE_DIR")
if _storage_override:
    STORAGE_DIR = Path(_storage_override)
elif getattr(sys, "frozen", False) and os.environ.get("NEURON_PORTABLE") != "1":
    STORAGE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Neuron" / "storage"
else:
    # Source checkouts and explicit portable builds keep app-local storage.
    STORAGE_DIR = RUNTIME_DIR / "storage"

try:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    STORAGE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Neuron" / "storage"
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Embedding configuration. BGE Small keeps the existing 384-dimensional FAISS
# footprint while improving retrieval quality over the legacy MiniLM baseline.
MODEL_NAME = os.getenv("NEURON_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("NEURON_EMBEDDING_DIM", "384"))
EMBEDDING_INDEX_SLUG = re.sub(r"[^a-z0-9]+", "_", MODEL_NAME.lower()).strip("_")

FAISS_INDEX_DIR = STORAGE_DIR / f"faiss_index_{EMBEDDING_INDEX_SLUG}"
CACHE_DIR = STORAGE_DIR / "cache"
FIRST_RUN_FLAG = STORAGE_DIR / ".first_run_complete"
CUSTOM_PATHS_FILE = STORAGE_DIR / "custom_watch_paths.json"
INDEXED_ROOTS_FILE = STORAGE_DIR / "indexed_roots.json"

# Create directories (safe — STORAGE_DIR is already verified writable)
try:
    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

FAISS_INDEX_PATH = str(FAISS_INDEX_DIR / "index.bin")

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
    ".idea", ".vscode", ".vs", ".codex", ".agents",
    # OS / system
    "Windows", "$Recycle.Bin", "ProgramData",
    "AppData", "System Volume Information",
    "Program Files", "Program Files (x86)", "PerfLogs",
    "Recovery", "Config.Msi",
    # Large app/database installs that are hostile to broad-drive scans
    "dbhome*", "oradata", "Oracle", "oracle",
    # Caches & build artefacts
    ".cache", ".tox", ".nox", ".mypy_cache",
    ".pytest_cache", "build", "dist",
    "__pypackages__",
    "webcache", "webcache_*",
    "Intermediate", "Saved", "DerivedDataCache", "Binaries",
    "target", ".gradle", ".idea", ".nuget",
}


def is_drive_root(path: str | Path) -> bool:
    """True for broad roots like C:/ or / that should not be live-watched."""
    try:
        p = Path(path).resolve()
        if platform.system().lower().startswith("win"):
            return bool(p.anchor) and str(p).rstrip("\\/").lower() == p.anchor.rstrip("\\/").lower()
        return p.parent == p
    except Exception:
        return False


def filter_live_watch_paths(paths: list) -> list:
    """Remove paths that are too broad or unsafe for recursive live watching."""
    safe = []
    for path in paths:
        if is_drive_root(path):
            continue
        safe.append(path)
    return safe

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
    ]

    # Windows machines can have redirected/OneDrive profile folders
    # where Path.home() does not match the real content roots.
    if platform.system().lower().startswith("win"):
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            up = Path(user_profile)
            candidates.extend(
                [
                    up / "Desktop",
                    up / "Documents",
                    up / "Downloads",
                    up / "Pictures",
                    up / "Videos",
                    up / "Music",
                ]
            )

        one_drive = os.environ.get("OneDrive")
        if one_drive:
            od = Path(one_drive)
            candidates.extend(
                [
                    od / "Desktop",
                    od / "Documents",
                    od / "Pictures",
                ]
            )

    seen = set()
    existing = []
    for p in candidates:
        try:
            rp = str(p.resolve())
            if rp in seen:
                continue
            if p.exists() and p.is_dir():
                seen.add(rp)
                existing.append(rp)
        except Exception:
            continue

    # Last-resort fallback so startup indexing never gets stuck at 0 paths.
    if not existing and home.exists():
        existing.append(str(home.resolve()))

    return existing


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
        "internet_enabled": False,
        "internet_max_results": 3,
        "auto_index_on_launch": False,
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
        if is_drive_root(norm):
            return False
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
    # Local executables and shell scripts are indexed by metadata/name only.
    # This lets exact filename searches like "ptytest3.exe" work without
    # trying to read binary contents.
    ".exe", ".msi", ".dll", ".lnk", ".bat", ".cmd", ".ps1",
    # Media (metadata only)
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
}

METADATA_ONLY_EXTENSIONS = {
    ".exe", ".msi", ".dll", ".lnk",
}

# Model configuration
METADATA_PATH = str(CACHE_DIR / "metadata.pkl")      # deprecated — use SQLITE_DB_PATH
INDEXED_PATHS_DB = str(CACHE_DIR / "indexed_paths.pkl")  # deprecated — use SQLITE_DB_PATH
SQLITE_DB_PATH = str(CACHE_DIR / f"metadata_{EMBEDDING_INDEX_SLUG}.db")

# Search configuration
TOP_K = UserConfig.load().get("top_k", 20)
SIMILARITY_THRESHOLD = 0.3

# ── Web-mode only settings (not used by the desktop app) ─────────────────────
# These are read by run.py / app/main.py when running as a FastAPI server.
# They have no effect in run_desktop.py.
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = False

# UI configuration
UI_TITLE = "NeuCockpit v1.0"
UI_WIDTH = 1000
UI_HEIGHT = 700

# Max file size to index (100 GB)
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 * 1024
