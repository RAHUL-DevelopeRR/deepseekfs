"""Configuration Management"""
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

# Create directories
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# AUTO-DETECT real user folders (cross-platform)
# ─────────────────────────────────────────────────────────────
def get_user_watch_paths() -> list:
    home = Path.home()
    candidates = [
        home / "Downloads",
    ]
    return [str(p) for p in candidates if p.exists()]


WATCH_PATHS = get_user_watch_paths()

# Supported file types
SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".docx", ".doc",
    ".md", ".json", ".csv", ".py", ".js",
    ".pptx", ".xlsx", ".xls", ".html"
}

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
FAISS_INDEX_PATH = str(FAISS_INDEX_DIR / "index.bin")
METADATA_PATH = str(CACHE_DIR / "metadata.pkl")
INDEXED_PATHS_DB = str(CACHE_DIR / "indexed_paths.pkl")  # duplicate guard

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

# Max file size to index (5 MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
