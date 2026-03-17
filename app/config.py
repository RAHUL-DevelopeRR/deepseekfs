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

# Create directories
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# File watching
WATCH_PATHS = [
    str(BASE_DIR / "sample_documents"),  # Default test folder
]

# Supported file types
SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".docx", ".doc", 
    ".md", ".json", ".csv", ".py", ".js"
}

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast + accurate (384 dims)
EMBEDDING_DIM = 384
FAISS_INDEX_PATH = str(FAISS_INDEX_DIR / "index.bin")
METADATA_PATH = str(CACHE_DIR / "metadata.pkl")
EMBEDDINGS_CACHE_PATH = str(CACHE_DIR / "embeddings.db")

# Search configuration
TOP_K = 10  # Return top 10 results
SIMILARITY_THRESHOLD = 0.3

# API configuration
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

# UI configuration
UI_TITLE = "DeepSeekFS - Semantic File Search"
UI_WIDTH = 1000
UI_HEIGHT = 700
